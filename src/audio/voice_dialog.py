import json
import ollama
from config.settings import settings
from src.audio.tts_engine import TTSEngine
from src.audio.recorder import AudioRecorder
from src.audio.stt_whisper import WhisperSTT

class VoiceDialog:
    def __init__(self, tts: TTSEngine | None = None, recorder: AudioRecorder | None = None, stt: WhisperSTT | None = None):
        self.tts = tts or TTSEngine()
        self.recorder = recorder or AudioRecorder()
        self.stt = stt or WhisperSTT()

    def ask_voice(self, question: str, listen_seconds: int = 20) -> str:
        """Sintetiza la pregunta por voz al usuario y entra en Pausa Activa escuchando su respuesta por voz."""
        # 1. Hablar la pregunta
        self.tts.speak(question, block=True)
        import time
        time.sleep(0.4)

        # 2. Escuchar la respuesta del usuario en Pausa Activa con VAD
        print("\n[V.ANSHEE 🎙️ Pausa Activa: Esperando respuesta por voz...]")
        recorder = AudioRecorder(max_wait_sec=listen_seconds)
        audio_file = recorder.record()

        # 3. Transcribir la respuesta con Whisper
        transcription = self.stt.transcribe(audio_file)
        print(f"[Tu respuesta por voz]: '{transcription}'")
        return transcription.strip()

    def parse_voice_answer(self, param_name: str, question: str, user_voice_text: str, options: list[str] | None = None) -> str:
        """Utiliza el modelo LLM NLU para extraer el parámetro exacto a partir de la respuesta por voz."""
        if not user_voice_text:
            return ""

        prompt = (
            f"El sistema le preguntó al usuario: '{question}'.\n"
            f"El usuario respondió por voz: '{user_voice_text}'.\n"
            f"Extrae el valor del parámetro '{param_name}'.\n"
        )
        if options:
            prompt += f"Opciones válidas permitidas: {options}.\n"

        prompt += (
            "Devuelve un JSON estricto:\n"
            '{"extracted_value": "valor_extraido"}'
        )

        try:
            response = ollama.chat(
                model=settings.OLLAMA_MODEL,
                messages=[{"role": "system", "content": prompt}],
                format="json"
            )
            data = json.loads(response["message"]["content"])
            return str(data.get("extracted_value", "")).strip().lower()
        except Exception as e:
            print(f"[VoiceDialog Warning] Falló extracción NLU: {e}")
            return user_voice_text.strip().lower()
