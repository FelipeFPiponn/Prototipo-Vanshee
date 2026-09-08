# src/routines/db.py
import sqlite3
from config.settings import settings

def init_db():
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_text TEXT NOT NULL,
            intent TEXT NOT NULL,
            target TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            day_of_week INTEGER,
            hour_of_day INTEGER
        )
    """)
    conn.commit()
    conn.close()

# src/routines/routine_logger.py
import sqlite3
from datetime import datetime
from config.settings import settings
from src.nlu.intent_parser import ParsedCommand

class RoutineLogger:
    def __init__(self):
        self.db_path = settings.DB_PATH

    def log_execution(self, raw_text: str, command: ParsedCommand):
        now = datetime.now()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO execution_logs (raw_text, intent, target, day_of_week, hour_of_day)
            VALUES (?, ?, ?, ?, ?)
            """,
            (raw_text, command.intent, command.target, now.weekday(), now.hour)
        )
        conn.commit()
        conn.close()
        print(f"[Routine Logger] Ejecución guardada para análisis temporal.")