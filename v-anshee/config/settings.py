import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "V.ANSHEE Core"
    DEBUG: bool = True
    
    # Audio & Wake-Word
    WAKE_WORD: str = "v_anshee"
    PORCUPINE_ACCESS_KEY: str = os.getenv("PORCUPINE_ACCESS_KEY", "")
    STT_MODEL_SIZE: str = "small"  # whisper local model size
    
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

    class Config:
        env_file = ".env"

settings = Settings()