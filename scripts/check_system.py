import importlib.util
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from src.routines.db import init_db

REQUIRED_MODULES = [
    "faster_whisper",
    "fastapi",
    "uvicorn",
    "numpy",
    "ollama",
    "pydantic",
    "pydantic_settings",
    "pythoncom",
    "sounddevice",
    "win32com.client",
]

OPTIONAL_MODULES = [
    "PIL",
    "pyautogui",
    "pygetwindow",
]


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_modules() -> bool:
    ok = True
    for name in REQUIRED_MODULES:
        found = module_available(name)
        print(f"[{'OK' if found else 'ERROR'}] modulo requerido: {name}")
        ok = ok and found

    for name in OPTIONAL_MODULES:
        found = module_available(name)
        print(f"[{'OK' if found else 'WARN'}] modulo opcional pantalla/GUI: {name}")
    return ok


def check_database() -> bool:
    init_db()
    expected = {
        "brain_facts",
        "brain_interactions",
        "context_events",
        "execution_logs",
        "learned_commands",
        "semantic_memories",
        "user_preferences",
        "detected_routines",
    }
    with sqlite3.connect(settings.DB_PATH) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    present = {row[0] for row in rows}
    missing = expected - present
    if missing:
        print(f"[ERROR] faltan tablas en DB: {', '.join(sorted(missing))}")
        return False
    print(f"[OK] base de datos inicializada: {settings.DB_PATH}")
    return True


def main() -> int:
    print("=== V.ANSHEE System Check ===")
    modules_ok = check_modules()
    db_ok = check_database()
    return 0 if modules_ok and db_ok else 1


if __name__ == "__main__":
    sys.exit(main())
