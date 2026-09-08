import os
import tempfile
import wave
import sounddevice as sd

class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, duration: int = 5):
        self.sample_rate = sample_rate
        self.duration = duration

    def record(self) -> str:
        """Captura audio desde el micrófono predeterminado y genera un archivo WAV temporal."""
        print(f"\n[AudioRecorder] Escuchando instrucción por {self.duration} segundos...")
        
        recording = sd.rec(
            int(self.duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16"
        )
        sd.wait()
        
        temp_path = os.path.join(tempfile.gettempdir(), "vanshee_input.wav")
        
        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit PCM (2 bytes por muestra)
            wf.setframerate(self.sample_rate)
            wf.writeframes(recording.tobytes())
            
        print(f"[AudioRecorder] Captura guardada en: {temp_path}")
        return temp_path