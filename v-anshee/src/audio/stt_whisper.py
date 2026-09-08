from faster_whisper import WhisperModel

class WhisperSTT:
    def __init__(self, model_size: str = "small"):
        print(f"[STT] Cargando modelo Faster-Whisper ({model_size})...")
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio_path: str) -> str:
        segments, _ = self.model.transcribe(audio_path, language="es")
        text = " ".join([segment.text for segment in segments]).strip()
        return text