import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "V.ANSHEE Core"
    DEBUG: bool = True
    
    # Audio & Wake-Word
    WAKE_WORD: str = "v_anshee"
    STT_MODEL_SIZE: str = "medium"  # whisper local model size (small, medium)
    
    # NLU / LLM Config
    LLM_PROVIDER: str = "ollama"  # "ollama" o "openai"
    OLLAMA_MODEL: str = "llama3.2"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Storage
    DB_PATH: Path = BASE_DIR / "data" / "vanshee.db"
    
    # App Execution Mappings (Windows)
    APP_MAPPINGS: dict = {
        "vs code": "code",
        "vscode": "code",
        "visual studio code": "code",
        "navegador": "chrome",
        "chrome": "chrome",
        "terminal": "wt",
        "cmd": "cmd"
    }

    # Web Dashboard & Voice Settings
    WEB_HOST: str = "127.0.0.1"
    WEB_PORT: int = 8000
    ENABLE_VOICE_VERIFICATION: bool = False
    AUDIO_THRESHOLD_RMS: float = 100.0
    AUDIO_INPUT_DEVICE: int | None = None
    AUDIO_DEVICE_NAME: str = ""
    TTS_VOICE: str = "es-ES-ElviraNeural"
    TTS_ENGINE: str = "edge-tts"
    WAKE_WORD_ENABLED: bool = True
    AUTOSTART_ENABLED: bool = False

    class Config:
        env_file = ".env"

settings = Settings()