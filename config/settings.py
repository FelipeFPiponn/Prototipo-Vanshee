import os
import sys
from typing import Any
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "V.ANSHEE Core"
    DEBUG: bool = True
    
    # Audio & Wake-Word
    WAKE_WORD: str = "v_anshee"
    STT_MODEL_SIZE: str = "small"  # whisper local model size (small, medium)
    
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
    AUDIO_THRESHOLD_RMS: float = 45.0
    AUDIO_INPUT_DEVICE: int | None = None
    AUDIO_DEVICE_NAME: str = ""
    TTS_VOICE: str = "es-ES-ElviraNeural"
    TTS_ENGINE: str = "edge-tts"
    WAKE_WORD_ENABLED: bool = True
    AUTOSTART_ENABLED: bool = False

    class Config:
        env_file = str(BASE_DIR / ".env")

settings = Settings()

def save_setting(key: str, value: Any):
    """Guarda una variable de configuración en memoria y la persiste de forma segura en .env."""
    import re
    if not re.match(r"^[A-Za-z0-9_]+$", str(key)):
        raise ValueError(f"Clave de configuración inválida: '{key}'")

    setattr(settings, key, value)
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        env_path.touch()

    try:
        import dotenv
        val_str = str(value).replace("\r", "").replace("\n", "")
        dotenv.set_key(str(env_path), key, val_str, quote_mode="always")
    except Exception as e:
        print(f"[Settings] Error guardando {key} en {env_path}: {e}")