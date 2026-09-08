import sqlite3
import sys
from pathlib import Path

# Agregar raíz del proyecto al path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.settings import settings

def reset_database():
    db_path = settings.DB_PATH
    if not Path(db_path).exists():
        print(f"[DB Clean] No se encontró la base de datos en {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Reset de tablas
    cursor.execute("DROP TABLE IF EXISTS learned_commands")
    cursor.execute("DROP TABLE IF EXISTS execution_logs")
    cursor.execute("DROP TABLE IF EXISTS detected_routines")
    
    conn.commit()
    conn.close()
    print("[DB Clean] Base de datos restablecida con éxito. Las tablas se recrearán al iniciar el sistema.")

if __name__ == "__main__":
    reset_database()