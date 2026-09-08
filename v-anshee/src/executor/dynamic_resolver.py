import json
import sqlite3
import ollama
from config.settings import settings
from src.executor.app_indexer import AppIndexer

KNOWN_TARGETS = {
    # Servicios Web
    "chatgpt": ("https://chatgpt.com", "url"),
    "chat gpt": ("https://chatgpt.com", "url"),
    "claude": ("https://claude.ai", "url"),
    "youtube": ("https://youtube.com", "url"),
    "github": ("https://github.com", "url"),
    "gmail": ("https://mail.google.com", "url"),
    # Protocolos de Apps Nativas en Windows
    "steam": ("steam://open/main", "protocol"),
    "discord": ("discord://", "protocol"),
    "spotify": ("spotify://", "protocol"),
    "calculadora": ("calc.exe", "app"),
    "calc": ("calc.exe", "app"),
    "cmd": ("cmd.exe", "app"),
    "terminal": ("wt.exe", "app")
}

class DynamicResolver:
    def __init__(self):
        self.db_path = settings.DB_PATH
        self.indexer = AppIndexer()
        self._init_db()

    def _init_db(self):
        """Inicializa automáticamente la tabla de memoria de comandos si fue eliminada."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learned_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE NOT NULL,
                execution_target TEXT NOT NULL,
                command_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def get_learned_command(self, keyword: str) -> str | None:
        self._init_db()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT execution_target FROM learned_commands WHERE keyword = ?", (keyword.lower(),))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def save_learned_command(self, keyword: str, execution_target: str, command_type: str = "app"):
        self._init_db()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO learned_commands (keyword, execution_target, command_type)
            VALUES (?, ?, ?)
        """, (keyword.lower(), execution_target, command_type))
        conn.commit()
        conn.close()

    def forget_command(self, target: str) -> bool:
        self._init_db()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if target in ["last", "anterior", "eso", "none"]:
            cursor.execute("DELETE FROM learned_commands WHERE id = (SELECT MAX(id) FROM learned_commands)")
        else:
            cursor.execute("DELETE FROM learned_commands WHERE keyword LIKE ?", (f"%{target.lower()}%",))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted_count > 0

    def resolve(self, target: str) -> tuple[str | None, str]:
        target_clean = target.lower().strip()

        if target_clean in KNOWN_TARGETS:
            return KNOWN_TARGETS[target_clean]

        learned = self.get_learned_command(target_clean)
        if learned:
            cmd_type = "url" if learned.startswith("http") or "://" in learned else "app"
            return learned, cmd_type

        local_path = self.indexer.find_app(target_clean)
        if local_path:
            return local_path, "app"

        return self._infer_with_llm(target_clean)

    def _infer_with_llm(self, target: str) -> tuple[str | None, str]:
        prompt = (
            f"El usuario quiere ejecutar '{target}' en Windows.\n"
            "Responde en JSON estricto con el target adecuado:\n"
            "- Si es app/protocolo: {\"execution_target\": \"steam://\", \"type\": \"protocol\"}\n"
            "- Si es web: {\"execution_target\": \"https://target.com\", \"type\": \"url\"}\n"
            "- Si es ejecutable: {\"execution_target\": \"target.exe\", \"type\": \"app\"}\n"
        )
        try:
            response = ollama.chat(
                model=settings.OLLAMA_MODEL,
                messages=[{"role": "system", "content": prompt}],
                format="json"
            )
            data = json.loads(response["message"]["content"])
            return data.get("execution_target"), data.get("type", "app")
        except Exception:
            return None, "unknown"