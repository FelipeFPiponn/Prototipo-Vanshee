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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Historial de ejecuciones completas con contexto temporal
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_command TEXT,
                raw_text TEXT,
                intent TEXT,
                target TEXT,
                day_of_week INTEGER NOT NULL DEFAULT 0,
                hour_of_day INTEGER NOT NULL DEFAULT 0,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("PRAGMA table_info(execution_logs)")
        cols = [c[1] for c in cursor.fetchall()]
        if "full_command" not in cols:
            cursor.execute("ALTER TABLE execution_logs ADD COLUMN full_command TEXT DEFAULT ''")

        # Tabla de preferencias aprendidas del usuario
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                pref_key TEXT PRIMARY KEY,
                pref_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detected_routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                routine_name TEXT UNIQUE NOT NULL,
                sequence_json TEXT NOT NULL,
                trigger_hour INTEGER NOT NULL,
                frequency INTEGER NOT NULL DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def save_preference(self, pref_key: str, pref_value: str):
        """Guarda o actualiza una preferencia aprendida del usuario."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_preferences (pref_key, pref_value)
            VALUES (?, ?)
            ON CONFLICT(pref_key) DO UPDATE SET
                pref_value = excluded.pref_value,
                updated_at = CURRENT_TIMESTAMP
        """, (pref_key, pref_value))
        conn.commit()
        conn.close()
        print(f"[Aprendizaje Humano] V.ANSHEE asimiló preferencia por voz: '{pref_key}' -> '{pref_value}'")

    def get_preference(self, pref_key: str) -> str | None:
        """Recupera una preferencia aprendida previamente."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT pref_value FROM user_preferences WHERE pref_key = ?", (pref_key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def log_execution(self, full_command: str):
        """Registra la ejecución para análisis de hábitos."""
        now = datetime.now()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO execution_logs (full_command, raw_text, intent, target, day_of_week, hour_of_day)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (full_command.lower().strip(), full_command.lower().strip(), "EXECUTE", full_command.lower().strip(), now.weekday(), now.hour))
        conn.commit()
        
        # Verificar si la combinación se repite con frecuencia (Minería de Hábitos)
        self._analyze_patterns(cursor, full_command.lower().strip(), now.hour)
        conn.commit()
        conn.close()

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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sequence_json FROM detected_routines
            WHERE trigger_hour BETWEEN ? AND ?
            ORDER BY frequency DESC LIMIT 1
        """, (max(0, current_hour - 1), min(23, current_hour + 1)))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
