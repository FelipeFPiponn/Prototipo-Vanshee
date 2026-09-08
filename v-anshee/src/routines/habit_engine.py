import sqlite3
from datetime import datetime
from config.settings import settings

class HabitEngine:
    def __init__(self):
        self.db_path = settings.DB_PATH
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Verificar si la tabla existe y tiene la columna 'full_command'
        cursor.execute("PRAGMA table_info(execution_logs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Si la tabla existía con el esquema anterior, la rehace con el esquema nuevo
        if columns and "full_command" not in columns:
            cursor.execute("DROP TABLE execution_logs")
            
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_command TEXT NOT NULL,
                day_of_week INTEGER NOT NULL,
                hour_of_day INTEGER NOT NULL,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detected_routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                routine_name TEXT UNIQUE,
                sequence_json TEXT NOT NULL,
                trigger_hour INTEGER,
                frequency INTEGER DEFAULT 1
            )
        """)
        conn.commit()
        conn.close()

    def log_execution(self, full_command: str):
        now = datetime.now()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO execution_logs (full_command, day_of_week, hour_of_day)
            VALUES (?, ?, ?)
        """, (full_command.lower().strip(), now.weekday(), now.hour))
        conn.commit()
        
        self._analyze_patterns(cursor, full_command.lower().strip(), now.hour)
        conn.commit()
        conn.close()

    def _analyze_patterns(self, cursor: sqlite3.Cursor, command: str, current_hour: int):
        cursor.execute("""
            SELECT COUNT(*) FROM execution_logs
            WHERE full_command = ? AND hour_of_day BETWEEN ? AND ?
        """, (command, max(0, current_hour - 1), min(23, current_hour + 1)))
        
        count = cursor.fetchone()[0]
        if count >= 3:
            print(f"[HabitEngine] Patrón de rutina registrado para '{command}' a las ~{current_hour}:00 hrs.")
            cursor.execute("""
                INSERT INTO detected_routines (routine_name, sequence_json, trigger_hour, frequency)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(routine_name) DO UPDATE SET
                    frequency = frequency + 1,
                    trigger_hour = excluded.trigger_hour
            """, (f"Rutina_{command[:20]}", command, current_hour, count))

    def get_suggested_routine(self) -> str | None:
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