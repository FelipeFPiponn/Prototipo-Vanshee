# scripts/clean_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "vanshee.db"

def clean_memory(keyword: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if keyword:
        cursor.execute("DELETE FROM learned_commands WHERE keyword LIKE ?", (f"%{keyword.lower()}%",))
        print(f"[DB Maintenance] Registros eliminados para la palabra clave: '{keyword}'")
    else:
        cursor.execute("DELETE FROM learned_commands")
        print("[DB Maintenance] Memoria adaptativa (learned_commands) limpiada por completo.")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Para limpiar únicamente el comando corrupto actual:
    clean_memory("chatgpt")
    clean_memory("chat")
    clean_memory("steam")
    
    # Para resetear toda la memoria de aprendizaje deshaz el comentario de abajo:
    # clean_memory()