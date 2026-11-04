import sqlite3
from datetime import datetime
from config.settings import settings
from src.routines.db import init_db

class RoutineEngine:
    def __init__(self):
        self.db_path = settings.DB_PATH
        self._init_db()

    def _init_db(self):
        init_db()

    def save_preference(self, pref_key: str, pref_value: str):
        """Guarda o actualiza una preferencia aprendida del usuario."""
        from src.routines.db import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_preferences (pref_key, pref_value)
                VALUES (?, ?)
                ON CONFLICT(pref_key) DO UPDATE SET
                    pref_value = excluded.pref_value,
                    updated_at = CURRENT_TIMESTAMP
            """, (pref_key, pref_value))
        print(f"[Aprendizaje Humano] V.ANSHEE asimiló preferencia por voz: '{pref_key}' -> '{pref_value}'")

    def get_preference(self, pref_key: str) -> str | None:
        """Recupera una preferencia aprendida previamente."""
        from src.routines.db import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("SELECT pref_value FROM user_preferences WHERE pref_key = ?", (pref_key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def log_execution(self, full_command: str):
        """Registra la ejecución para análisis de hábitos."""
        now = datetime.now()
        from src.routines.db import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO execution_logs (full_command, raw_text, intent, target, day_of_week, hour_of_day)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (full_command.lower().strip(), full_command.lower().strip(), "EXECUTE", full_command.lower().strip(), now.weekday(), now.hour))
            
            # Verificar si la combinación se repite con frecuencia (Minería de Hábitos)
            self._analyze_patterns(cursor, full_command.lower().strip(), now.hour)

    def _analyze_patterns(self, cursor: sqlite3.Cursor, command: str, current_hour: int):
        """Si un comando/secuencia se repite >= 3 veces cerca de la misma hora, se marca como Rutina."""
        cursor.execute("""
            SELECT COUNT(*) FROM execution_logs
            WHERE full_command = ? AND hour_of_day BETWEEN ? AND ?
        """, (command, max(0, current_hour - 1), min(23, current_hour + 1)))
        
        count = cursor.fetchone()[0]
        if count >= 3:
            print(f"[RoutineEngine] ¡Patrón detectado! El comando '{command}' es habitual a las ~{current_hour}:00 h.")
            cursor.execute("""
                INSERT INTO detected_routines (routine_name, sequence_json, trigger_hour, frequency)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(routine_name) DO UPDATE SET
                    frequency = frequency + 1,
                    trigger_hour = excluded.trigger_hour,
                    updated_at = CURRENT_TIMESTAMP
            """, (f"Rutina_{command[:20]}", command, current_hour, count))

    def get_suggested_routine(self) -> str | None:
        """Devuelve una sugerencia de rutina si la hora actual coincide con un hábito aprendido."""
        current_hour = datetime.now().hour
        from src.routines.db import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT sequence_json FROM detected_routines
                WHERE trigger_hour BETWEEN ? AND ?
                ORDER BY frequency DESC LIMIT 1
            """, (max(0, current_hour - 1), min(23, current_hour + 1)))
            row = cursor.fetchone()
            return row[0] if row else None
