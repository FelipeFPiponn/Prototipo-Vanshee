import time
import queue
import threading
from typing import Callable, Optional
import numpy as np

from src.audio.stt_whisper import WhisperSTT


class StreamingSTT:
    """Motor de transcripción progresiva en tiempo real (Streaming Speech-to-Text).
    
    Procesa fragmentos de audio incrementalmente mientras el usuario habla,
    emitiendo texto provisional (partial) y consolidado (final) con latencia mínima.
    """

    def __init__(
        self,
        whisper_stt: Optional[WhisperSTT] = None,
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
        partial_interval_sec: float = 0.35,
    ):
        self.stt = whisper_stt or WhisperSTT()
        self.on_partial = on_partial
        self.on_final = on_final
        self.partial_interval_sec = partial_interval_sec

        self.audio_buffer: list[np.ndarray] = []
        self.last_partial_time = 0.0
        self.is_active = False
        self._lock = threading.Lock()

        # Cola y worker en segundo plano para no bloquear el flujo de audio
        self._partial_queue = queue.Queue(maxsize=2)
        self._worker_running = True
        self._worker_thread = threading.Thread(target=self._partial_worker, daemon=True)
        self._worker_thread.start()

    def _partial_worker(self):
        """Hilo de fondo que computa transcripciones parciales sin frenar el flujo de audio."""
        while self._worker_running:
            try:
                audio_slice = self._partial_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            try:
                # Transcripción rápida con beam_size=1
                segments, _ = self.stt.model.transcribe(
                    audio_slice,
                    language="es",
                    beam_size=1,
                    temperature=0.0,
                    vad_filter=False
                )
                text = " ".join([s.text for s in segments]).strip()
                if text and self.on_partial:
                    self.on_partial(text)
            except Exception as e:
                pass

    def on_speech_start(self):
        """Invocado cuando Silero VAD detecta inicio de habla."""
        with self._lock:
            self.audio_buffer.clear()
            self.last_partial_time = time.time()
            self.is_active = True

    def feed_chunk(self, chunk: np.ndarray, speech_prob: float):
        """Recibe un bloque de audio de ~32ms."""
        with self._lock:
            if not self.is_active:
                return

            self.audio_buffer.append(chunk)
            now = time.time()

            # Cada ~350ms, enviar fragmento acumulado a inferencia parcial si hay suficiente audio (>0.4s)
            if (now - self.last_partial_time) >= self.partial_interval_sec:
                self.last_partial_time = now
                total_samples = sum(len(c) for c in self.audio_buffer)
                if total_samples >= (16000 * 0.4):
                    audio_f32 = np.concatenate(self.audio_buffer, axis=0)
                    if audio_f32.dtype == np.int16:
                        audio_f32 = audio_f32.astype(np.float32) / 32768.0

                    # Intentar encolar sin bloquear si el worker está ocupado
                    try:
                        self._partial_queue.put_nowait(audio_f32)
                    except queue.Full:
                        pass

    def finalize_utterance(self, full_audio: np.ndarray) -> str:
        """Invocado al terminar la frase para generar la transcripción definitiva de alta precisión."""
        with self._lock:
            self.is_active = False
            self.audio_buffer.clear()
            # Limpiar la cola de parciales pendientes
            while not self._partial_queue.empty():
                try:
                    self._partial_queue.get_nowait()
                except queue.Empty:
                    break

        # Transcripción final completa con prompts y VAD post-filtro
        final_text = self.stt.transcribe(full_audio)

        if self.on_final:
            try:
                self.on_final(final_text)
            except Exception as e:
                print(f"[StreamingSTT on_final Error]: {e}")

        return final_text

    def close(self):
        """Detiene el hilo worker."""
        self._worker_running = False
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.3)
