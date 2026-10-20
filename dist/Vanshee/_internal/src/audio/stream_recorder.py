import time
import queue
import threading
from typing import Callable, Optional
import numpy as np
import sounddevice as sd

from config.settings import settings
from src.audio.vad_engine import SileroVAD


class StreamRecorder:
    """Grabador de audio en flujo continuo (Streaming) con detección VAD en tiempo real.
    
    Emite eventos asíncronos cuando el usuario empieza a hablar, durante el habla y al finalizar,
    permitiendo transcripción progresiva y tiempo de respuesta inferior a 300ms.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_samples: int = 512,
        silence_timeout_sec: float = 0.30,
        speech_threshold: float = 0.45,
        device_index: Optional[int] = None,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_chunk: Optional[Callable[[np.ndarray, float], None]] = None,
        on_speech_end: Optional[Callable[[np.ndarray], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples
        self.silence_timeout_sec = silence_timeout_sec
        self.speech_threshold = speech_threshold
        self.device_index = device_index if device_index is not None else getattr(settings, "AUDIO_INPUT_DEVICE", None)

        self.on_speech_start = on_speech_start
        self.on_speech_chunk = on_speech_chunk
        self.on_speech_end = on_speech_end

        self.vad = SileroVAD()
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.stream: Optional[sd.InputStream] = None
        self.worker_thread: Optional[threading.Thread] = None

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_running:
            self.audio_queue.put(indata[:, 0].copy())

    def _process_loop(self):
        pre_speech_buffer = []
        max_pre_buffer = 10  # ~320ms de buffer previo
        speech_started = False
        silence_start_time = None
        current_utterance = []

        while self.is_running:
            try:
                chunk = self.audio_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            is_sp, prob = self.vad.is_speech(chunk, threshold=self.speech_threshold)

            if not speech_started:
                pre_speech_buffer.append(chunk)
                if len(pre_speech_buffer) > max_pre_buffer:
                    pre_speech_buffer.pop(0)

                if is_sp:
                    speech_started = True
                    silence_start_time = None
                    current_utterance = list(pre_speech_buffer)
                    pre_speech_buffer.clear()
                    if self.on_speech_start:
                        try:
                            self.on_speech_start()
                        except Exception as e:
                            print(f"[StreamRecorder Callback Error on_speech_start]: {e}")
            else:
                current_utterance.append(chunk)
                if self.on_speech_chunk:
                    try:
                        self.on_speech_chunk(chunk, prob)
                    except Exception as e:
                        print(f"[StreamRecorder Callback Error on_speech_chunk]: {e}")

                if not is_sp:
                    if silence_start_time is None:
                        silence_start_time = time.time()
                    elif (time.time() - silence_start_time) >= self.silence_timeout_sec:
                        # Fin de frase detectado
                        full_utterance = np.concatenate(current_utterance, axis=0)
                        speech_started = False
                        silence_start_time = None
                        current_utterance = []
                        self.vad.reset()

                        if self.on_speech_end and len(full_utterance) >= (self.sample_rate * 0.25):
                            try:
                                self.on_speech_end(full_utterance)
                            except Exception as e:
                                print(f"[StreamRecorder Callback Error on_speech_end]: {e}")
                else:
                    silence_start_time = None

    def start(self):
        """Inicia la captura continua de audio en segundo plano."""
        if self.is_running:
            return

        self.is_running = True
        self.vad.reset()
        self.stream = sd.InputStream(
            device=self.device_index,
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk_samples,
            callback=self._audio_callback
        )
        self.stream.start()
        self.worker_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.worker_thread.start()
        print(f"[StreamRecorder] Captura continua activa en dispositivo #{self.device_index or 'Default'}.")

    def stop(self):
        """Detiene la captura de audio."""
        self.is_running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=0.5)
        print("[StreamRecorder] Captura continua detenida.")
