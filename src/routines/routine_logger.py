import sqlite3
from datetime import datetime
from config.settings import settings
from src.nlu.intent_parser import ActionStep, ParsedPipeline
from src.routines.db import init_db


class RoutineLogger:
    def __init__(self):
        self.db_path = settings.DB_PATH
        init_db()

    def log_execution(self, raw_text: str, command: ActionStep | ParsedPipeline):
        now = datetime.now()
        if isinstance(command, ParsedPipeline):
            intent = "PIPELINE"
            target = " | ".join(step.target for step in command.steps)
        else:
            intent = command.intent
            target = command.target

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO execution_logs (full_command, raw_text, intent, target, day_of_week, hour_of_day)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (raw_text, raw_text, intent, target, now.weekday(), now.hour)
        )
        conn.commit()
        conn.close()
        print("[Routine Logger] Ejecución guardada para análisis temporal.")
