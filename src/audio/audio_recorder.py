import io
import sounddevice as sd
import soundfile as sf

class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels

    def record_seconds(self, seconds: int = 4) -> bytes:
        """Captura audio del micrófono y lo devuelve como buffer de bytes en formato WAV."""
        print("[AudioRecorder] Escuchando instrucción...")
        
        # Grabación directa usando CFFI nativo (sin depender de MSVC)
        audio_data = sd.rec(
            int(seconds * self.sample_rate),
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16'
        )
        sd.wait()  # Bloquea hasta completar los segundos de grabación
        print("[AudioRecorder] Captura finalizada.")

        # Conversión a buffer WAV en memoria
        wav_buffer = io.BytesIO()
        sf.write(wav_buffer, audio_data, self.sample_rate, format='WAV')
        return wav_buffer.getvalue()