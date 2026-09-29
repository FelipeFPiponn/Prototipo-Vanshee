import os
import time
import wave
import tempfile
import numpy as np
import sounddevice as sd
from config.settings import settings

class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        max_wait_sec: float = 20.0,
        silence_timeout_sec: float = 1.4,
        threshold_rms: float | None = None,
        duration: float | None = None,
        device_index: int | None = None,
    ):
        self.sample_rate = sample_rate
        self.max_wait_sec = duration if duration is not None else max_wait_sec
        self.silence_timeout_sec = silence_timeout_sec
        self.threshold_rms = threshold_rms if threshold_rms is not None else getattr(settings, "AUDIO_THRESHOLD_RMS", 180.0)
        self.device_index = device_index if device_index is not None else getattr(settings, "AUDIO_INPUT_DEVICE", None)

    def record(self) -> str:
        """
        Captura audio con calibración dinámica de ruido y Pausa Activa a nivel sistema:
        - Calibra el ruido de fondo ambiental durante 0.25s.
        - Entra en Pausa Activa esperando pacientemente a que el usuario empiece a hablar.
        - Captura la línea de voz completa sin importar la duración.
        - Finaliza automáticamente solo cuando el usuario guarda silencio durante 1.4s.
        """
        chunk_duration = 0.05  # 50 ms por bloque
        chunk_size = int(self.sample_rate * chunk_duration)
        
        # 1. Calibración automática del nivel de ruido ambiental
        try:
            ambient_samples = sd.rec(int(self.sample_rate * 0.25), samplerate=self.sample_rate, channels=1, dtype="int16", device=self.device_index)
            sd.wait()
            ambient_rms = float(np.sqrt(np.mean(ambient_samples.astype(np.float32) ** 2)))
        except Exception:
            ambient_rms = 50.0

        # Umbral dinámico inteligente para filtrar ventiladores, eco o ruido de fondo
        dynamic_threshold = max(self.threshold_rms, ambient_rms * 1.8 + 80.0)

        print(f"\n[AudioRecorder 🎙️ Calibración (Ruido base: {ambient_rms:.0f} | Umbral voz: {dynamic_threshold:.0f})]")
        print(f"[AudioRecorder ⏸️ Pausa Activa: Esperando a que hables (hasta {self.max_wait_sec:.0f}s)...]")

        recorded_chunks = []
        pre_speech_buffer = []  # Buffer circular para conservar el inicio del comando (~400ms)
        max_pre_buffer = 8

        speech_started = False
        silence_start_time = None
        start_wait_time = time.time()

        def audio_callback(indata, frames, time_info, status):
            nonlocal speech_started, silence_start_time, recorded_chunks, pre_speech_buffer
            
            audio_chunk = indata.copy()
            rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))

            if not speech_started:
                pre_speech_buffer.append(audio_chunk)
                if len(pre_speech_buffer) > max_pre_buffer:
                    pre_speech_buffer.pop(0)

                # Transición a voz detectada solo si supera la voz calibrada
                if rms > dynamic_threshold:
                    speech_started = True
                    print("[AudioRecorder 🔴 Voz humana detectada, grabando respuesta completa...]")
                    recorded_chunks.extend(pre_speech_buffer)
                    pre_speech_buffer.clear()
            else:
                recorded_chunks.append(audio_chunk)
                if rms < dynamic_threshold:
                    if silence_start_time is None:
                        silence_start_time = time.time()
                else:
                    silence_start_time = None  # Usuario sigue hablando, reiniciar temporizador

        try:
            with sd.InputStream(device=self.device_index, samplerate=self.sample_rate, channels=1, dtype="int16", blocksize=chunk_size, callback=audio_callback):
                while True:
                    time.sleep(0.05)
                    now = time.time()

                    # Si se detectó voz y transcurrieron 1.4s de silencio continuo -> finalizar
                    if speech_started and silence_start_time is not None:
                        if (now - silence_start_time) >= self.silence_timeout_sec:
                            print("[AudioRecorder ⏹️ Silencio final detectado. Procesando respuesta hablada...]")
                            break

                    # Límite de Pausa Activa si el usuario no habla en absoluto
                    if not speech_started and (now - start_wait_time) >= self.max_wait_sec:
                        print("[AudioRecorder ⏳ Pausa activa finalizada sin detectar respuesta hablada.]")
                        break
        except Exception as e:
            print(f"[AudioRecorder Error]: {e}")

        temp_path = os.path.join(tempfile.gettempdir(), "vanshee_input.wav")

        if not recorded_chunks:
            empty_data = np.zeros(int(self.sample_rate * 0.5), dtype=np.int16)
            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(empty_data.tobytes())
            return temp_path

        full_audio = np.concatenate(recorded_chunks, axis=0)

        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(full_audio.tobytes())

        print(f"[AudioRecorder] Respuesta capturada ({len(full_audio)/self.sample_rate:.1f}s) en: {temp_path}")
        return temp_path