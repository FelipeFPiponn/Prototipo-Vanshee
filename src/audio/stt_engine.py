import io
from faster_whisper import WhisperModel
from config.settings import settings

class STTEngine:
    def __init__(self):
        # Carga el modelo cuantizado en CPU/GPU según disponibilidad
        print(f"[STT] Cargando modelo Whisper ({settings.STT_MODEL_SIZE})...")
        self.model = WhisperModel(
            settings.STT_MODEL_SIZE, 
            device="cpu", 
            compute_type="int8"
        )

    def transcribe(self, audio_bytes: bytes) -> str:
        """Convierte los bytes del buffer WAV a texto en español."""
        audio_stream = io.BytesIO(audio_bytes)
        segments, _ = self.model.transcribe(
            audio_stream, 
            beam_size=5, 
            language="es"
        )
        text = " ".join([segment.text for segment in segments])
        return text.strip()