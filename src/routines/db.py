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
            full_command TEXT,
            raw_text TEXT,
            intent TEXT,
            target TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            day_of_week INTEGER,
            hour_of_day INTEGER
        )
    """)
    cursor.execute("PRAGMA table_info(execution_logs)")
    cols = [c[1] for c in cursor.fetchall()]
    if "full_command" not in cols:
        cursor.execute("ALTER TABLE execution_logs ADD COLUMN full_command TEXT DEFAULT ''")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detected_routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            routine_name TEXT UNIQUE NOT NULL,
            sequence_json TEXT NOT NULL,
            trigger_hour INTEGER NOT NULL,
            frequency INTEGER NOT NULL DEFAULT 1,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            pref_key TEXT PRIMARY KEY,
            pref_value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS context_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT,
            window_title TEXT,
            action_hint TEXT,
            user_command TEXT,
            assistant_response TEXT,
            confidence REAL DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brain_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_text TEXT NOT NULL,
            app_name TEXT,
            window_title TEXT,
            plan_summary TEXT,
            response_text TEXT,
            success INTEGER NOT NULL DEFAULT 0,
            confidence REAL DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brain_facts (
            fact_key TEXT PRIMARY KEY,
            fact_value TEXT NOT NULL,
            source TEXT,
            confidence REAL DEFAULT 1.0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semantic_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'interaction',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            importance REAL NOT NULL DEFAULT 0.5,
            success INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_used_at DATETIME
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_search_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_key TEXT UNIQUE NOT NULL,
            provider_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
