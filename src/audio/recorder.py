import os
import time
import wave
import tempfile
import numpy as np
import sounddevice as sd
from typing import Optional, Union

from config.settings import settings
from src.audio.vad_engine import SileroVAD


class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        max_wait_sec: float = 20.0,
        silence_timeout_sec: float = 0.35,  # Reducido de 1.4s a 0.35s gracias a Silero VAD
        threshold_rms: float | None = None,
        duration: float | None = None,
        device_index: int | None = None,
    ):
        self.sample_rate = sample_rate
        self.max_wait_sec = duration if duration is not None else max_wait_sec
        self.silence_timeout_sec = silence_timeout_sec
        self.threshold_rms = threshold_rms if threshold_rms is not None else getattr(settings, "AUDIO_THRESHOLD_RMS", 140.0)
        self.device_index = device_index if device_index is not None else getattr(settings, "AUDIO_INPUT_DEVICE", None)
        try:
            self.vad = SileroVAD()
        except Exception as e:
            print(f"[AudioRecorder Warning] No se pudo cargar Silero VAD: {e}. Se usará detector RMS.")
            self.vad = None

    def record_array(self) -> np.ndarray:
        """Captura audio con Silero VAD y retorna directamente el array numpy int16 en memoria RAM."""
        chunk_samples = 512  # 32ms a 16kHz exacto para Silero VAD
        
        if self.vad:
            self.vad.reset()

        recorded_chunks = []
        pre_speech_buffer = []  # Buffer circular previo (~320ms)
        max_pre_buffer = 10

        speech_started = False
        silence_start_time = None
        start_wait_time = time.time()

        def audio_callback(indata, frames, time_info, status):
            nonlocal speech_started, silence_start_time, recorded_chunks, pre_speech_buffer
            
            chunk = indata[:, 0].copy()
            
            # Evaluación con Silero VAD o fallback a RMS
            if self.vad:
                is_sp, prob = self.vad.is_speech(chunk, threshold=0.45)
            else:
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                is_sp = (rms > self.threshold_rms)

            if not speech_started:
                pre_speech_buffer.append(chunk)
                if len(pre_speech_buffer) > max_pre_buffer:
                    pre_speech_buffer.pop(0)

                if is_sp:
                    speech_started = True
                    print("[AudioRecorder 🔴 Voz detectada (Silero VAD), capturando comando...]")
                    recorded_chunks.extend(pre_speech_buffer)
                    pre_speech_buffer.clear()
            else:
                recorded_chunks.append(chunk)
                if not is_sp:
                    if silence_start_time is None:
                        silence_start_time = time.time()
                else:
                    silence_start_time = None  # Usuario sigue hablando

        try:
            with sd.InputStream(
                device=self.device_index,
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=chunk_samples,
                callback=audio_callback
            ):
                while True:
                    time.sleep(0.02)
                    now = time.time()

                    # Fin de frase rápido con Silero VAD (~300ms de silencio)
                    if speech_started and silence_start_time is not None:
                        if (now - silence_start_time) >= self.silence_timeout_sec:
                            print(f"[AudioRecorder ⏹️ Fin de frase detectado en {self.silence_timeout_sec*1000:.0f}ms. Procesando...]")
                            break

                    # Límite de espera si el usuario no habla
                    if not speech_started and (now - start_wait_time) >= self.max_wait_sec:
                        print("[AudioRecorder ⏳ Tiempo de espera agotado sin detectar voz.]")
                        break
        except Exception as e:
            print(f"[AudioRecorder Error]: {e}")

        if not recorded_chunks:
            return np.zeros(int(self.sample_rate * 0.3), dtype=np.int16)

        return np.concatenate(recorded_chunks, axis=0)

    def record(self) -> str:
        """Captura audio y lo retorna como ruta a archivo temporal .wav para retrocompatibilidad."""
        audio_array = self.record_array()
        temp_path = os.path.join(tempfile.gettempdir(), "vanshee_input.wav")

        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_array.tobytes())

        print(f"[AudioRecorder] Audio guardado ({len(audio_array)/self.sample_rate:.2f}s) en: {temp_path}")
        return temp_path