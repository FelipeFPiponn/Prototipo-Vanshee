import os
import re
import time
import wave
import tempfile
import threading
import queue
from collections import deque
import numpy as np
import sounddevice as sd
from typing import Callable, Optional

from config.settings import settings
from src.audio.audio_coordinator import register_wake_detector, is_tts_playing

WAKE_PATTERN = re.compile(
    r"\b(banshee|vanshee|v_anshee|v-anshee|banchi|vanchi|vanche|banche|banji|vanji|bansi|vansi|oye banshee|oye vanshee)\b",
    re.IGNORECASE
)

class WakeWordDetector:
    """
    Detector continuo de palabra de activación ("Banshee" / "Vanshee") en segundo plano.
    Utiliza un flujo continuo de audio sin reinicios, cola de procesamiento en hilo secundario
    y ventana de comando activo para máxima fluidez y cero pérdida de voz.
    """

    def __init__(
        self,
        stt_engine=None,
        on_wake_detected: Optional[Callable[[str, str], None]] = None,
        on_state_change: Optional[Callable[[str], None]] = None,
        sample_rate: int = 16000,
        threshold_rms: float | None = None,
        device_index: int | None = None,
    ):
        self.stt_engine = stt_engine
        self.on_wake_detected = on_wake_detected
        self.on_state_change = on_state_change
        self.sample_rate = sample_rate
        self.threshold_rms = threshold_rms if threshold_rms is not None else getattr(settings, "AUDIO_THRESHOLD_RMS", 100.0)
        self.device_index = device_index if device_index is not None else getattr(settings, "AUDIO_INPUT_DEVICE", None)

        self._running = False
        self._listen_thread: Optional[threading.Thread] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue(maxsize=10)
        self._paused = False
        self._active_command_until: float = 0.0
        self._last_trigger_time: float = 0.0

        # Registrar en el coordinador de audio
        register_wake_detector(self)

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._transcription_worker, daemon=True, name="WakeWordWorker")
        self._worker_thread.start()

        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True, name="WakeWordAudioStream")
        self._listen_thread.start()
        print(f"[WakeWord] Detector continuo de 'Banshee' activo (Dispositivo: {self.device_index}, Umbral: {self.threshold_rms} RMS).")

    def stop(self):
        self._running = False
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=2.0)
        print("[WakeWord] Detector detenido.")

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def trigger_manual_listen(self):
        """Activa una ventana de escucha activa directa por 7 segundos."""
        self._active_command_until = time.time() + 7.0
        print("[WakeWord] Modo de escucha activa forzado por 7 segundos.")

    def update_settings(self, threshold_rms: float | None = None, device_index: int | None = None):
        if threshold_rms is not None:
            self.threshold_rms = threshold_rms
            print(f"[WakeWord] Umbral RMS actualizado a: {self.threshold_rms}")
        if device_index is not None and device_index != self.device_index:
            self.device_index = device_index
            print(f"[WakeWord] Dispositivo de entrada cambiado a: {self.device_index}. Reiniciando stream...")
            # Forzar reinicio del stream con el nuevo dispositivo
            self._restart_stream()

    def _restart_stream(self):
        self.stop()
        time.sleep(0.3)
        self.start()

    def _extract_command_after_wake(self, text: str) -> tuple[bool, str]:
        """
        Verifica si contiene la palabra clave o si estamos en ventana de comando activo.
        """
        clean = re.sub(r"[^\w\s]", " ", text.lower()).strip()
        clean = re.sub(r"\s+", " ", clean)

        # 1. Verificar palabra de activación explícita
        match = WAKE_PATTERN.search(clean)
        if match:
            trailing = clean[match.end():].strip()
            return True, trailing

        # 2. Si estamos dentro de la ventana de escucha activa tras decir "¿Dime?"
        if time.time() < self._active_command_until and len(clean) >= 3:
            return True, clean

        return False, ""

    def _transcription_worker(self):
        """Hilo dedicado a procesar los audios sin congelar el flujo del micrófono."""
        while self._running:
            try:
                audio_bytes = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if not self.stt_engine:
                continue

            temp_wav = os.path.join(tempfile.gettempdir(), f"wake_phrase_{int(time.time()*1000)}.wav")
            try:
                with wave.open(temp_wav, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(audio_bytes)

                text = self.stt_engine.transcribe(temp_wav)
                now = time.time()
                if text and (now - self._last_trigger_time) > 1.8:
                    is_wake, command = self._extract_command_after_wake(text)
                    if is_wake:
                        self._last_trigger_time = now
                        print(f"\n[Banshee Detectado]: '{text}' (Comando: '{command}')")

                        # Pausar temporalmente para que no capte la respuesta TTS
                        self._paused = True
                        try:
                            if not command:
                                self._active_command_until = now + 7.0
                            else:
                                self._active_command_until = 0.0

                            if self.on_wake_detected:
                                self.on_wake_detected(text, command)
                        finally:
                            time.sleep(0.4)
                            self._paused = False
            except Exception as e:
                print(f"[WakeWord Worker Error]: {e}")
            finally:
                try:
                    if os.path.exists(temp_wav):
                        os.remove(temp_wav)
                except Exception:
                    pass

    def _listen_loop(self):
        """Mantiene un InputStream persistente y fluido en sounddevice."""
        chunk_duration = 0.1  # 100 ms por bloque
        chunk_size = int(self.sample_rate * chunk_duration)

        speech_chunks = []
        preroll_chunks = deque(maxlen=4)  # 400ms de pre-buffer
        has_speech = False
        silence_frames = 0
        max_silence_frames = 10  # ~1.0 segundo de silencio para cerrar frase naturalmente
        max_total_chunks = 70    # ~7.0 segundos de comando continuo

        def stream_callback(indata, frames, time_info, status):
            nonlocal has_speech, silence_frames, speech_chunks

            # Si Banshee está hablando o está pausado, ignorar el audio entrante
            if is_tts_playing() or self._paused:
                speech_chunks.clear()
                preroll_chunks.clear()
                has_speech = False
                silence_frames = 0
                return

            chunk = indata.copy()
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            current_trigger = max(40.0, self.threshold_rms)

            if not has_speech:
                preroll_chunks.append(chunk)
                # Detección de inicio de voz
                if rms >= current_trigger:
                    has_speech = True
                    speech_chunks.extend(preroll_chunks)
                    speech_chunks.append(chunk)
                    silence_frames = 0
            else:
                speech_chunks.append(chunk)
                # Detección de silencio con histéresis (65% del umbral de activación)
                if rms < (current_trigger * 0.65):
                    silence_frames += 1
                else:
                    silence_frames = 0

                # Cierre de frase
                if silence_frames >= max_silence_frames or len(speech_chunks) >= max_total_chunks:
                    if len(speech_chunks) >= 4:  # Mínimo 400ms
                        full_audio = np.concatenate(speech_chunks, axis=0)
                        try:
                            self._audio_queue.put_nowait(full_audio.tobytes())
                        except queue.Full:
                            pass
                    speech_chunks.clear()
                    has_speech = False
                    silence_frames = 0

        while self._running:
            try:
                with sd.InputStream(
                    device=self.device_index,
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=chunk_size,
                    callback=stream_callback
                ):
                    # El stream se mantiene abierto continuamente sin destruirse
                    while self._running:
                        time.sleep(0.1)
            except Exception as e:
                if self._running:
                    print(f"[WakeWord Stream Error]: {e}. Reintentando en 1s...")
                    time.sleep(1.0)
