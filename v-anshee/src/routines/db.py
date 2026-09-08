import sqlite3
from config.settings import settings

def init_db():
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    
    # Historico de ejecuciones para analisis de rutinas
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
    
    # Memoria dinamica de comandos aprendidos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            execution_target TEXT NOT NULL,
            command_type TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()