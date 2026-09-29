import json
import sqlite3
import ollama
from config.settings import settings
from src.executor.app_indexer import AppIndexer
from src.routines.db import init_db

WEB_SERVICES = {
    "chatgpt": "https://chatgpt.com",
    "chat gpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "youtube": "https://youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com"
}

import urllib.parse

STEAM_GAMES = {
    "cs2": "steam://rungameid/730",
    "cs 2": "steam://rungameid/730",
    "counter strike": "steam://rungameid/730",
    "counter strike 2": "steam://rungameid/730",
    "counter-strike 2": "steam://rungameid/730",
    "dota 2": "steam://rungameid/570",
    "dota": "steam://rungameid/570",
    "pubg": "steam://rungameid/578080",
    "apex": "steam://rungameid/1172470",
    "apex legends": "steam://rungameid/1172470",
    "gta v": "steam://rungameid/271590",
    "gta 5": "steam://rungameid/271590",
}

class DynamicResolver:
    def __init__(self):
        self.db_path = settings.DB_PATH
        init_db()
        self.indexer = AppIndexer()

    def get_learned_command(self, keyword: str) -> str | None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT execution_target FROM learned_commands WHERE keyword = ?", (keyword.lower(),))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def save_learned_command(self, keyword: str, execution_target: str, command_type: str = "app"):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO learned_commands (keyword, execution_target, command_type)
            VALUES (?, ?, ?)
        """, (keyword.lower(), execution_target, command_type))
        conn.commit()
        conn.close()
        print(f"[Aprendizaje] V.ANSHEE aprendió: '{keyword}' -> '{execution_target}'")

    def forget_command(self, target: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        target_clean = target.lower().strip()
        if target_clean in ["last", "previous", "anterior", "eso", "none", "ultimo"]:
            cursor.execute("DELETE FROM learned_commands WHERE id = (SELECT MAX(id) FROM learned_commands)")
        else:
            cursor.execute("DELETE FROM learned_commands WHERE keyword LIKE ?", (f"%{target_clean}%",))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted_count > 0

    def resolve(self, target: str) -> tuple[str | None, str]:
        target_clean = target.lower().strip()

        # 0. Juegos de Steam conocidos por obviedad
        if target_clean in STEAM_GAMES:
            return STEAM_GAMES[target_clean], "protocol"

        # Búsquedas inteligentes en YouTube / Google por obviedad
        if "youtube" in target_clean and len(target_clean) > 7:
            query = target_clean.replace("youtube", "").replace("buscan", "").replace("busca en", "").replace("buscar en", "").replace("busca", "").replace("en", "").strip()
            if query:
                encoded_q = urllib.parse.quote(query)
                return f"https://www.youtube.com/results?search_query={encoded_q}", "url"
        
        if "google" in target_clean or target_clean.startswith("busca "):
            query = target_clean.replace("google", "").replace("busca en", "").replace("buscar en", "").replace("busca", "").strip()
            if query:
                encoded_q = urllib.parse.quote(query)
                return f"https://www.google.com/search?q={encoded_q}", "url"

        if target_clean in WEB_SERVICES:
            return WEB_SERVICES[target_clean], "url"

        # 1. Buscar en aplicaciones locales indexadas primero
        local_path = self.indexer.find_app(target_clean)
        if local_path:
            return local_path, "app"

        # 2. Buscar en comandos aprendidos previamente en DB
        learned = self.get_learned_command(target_clean)
        if learned:
            cmd_type = "url" if learned.startswith("http") else "app"
            return learned, cmd_type

        return self._infer_with_llm(target_clean)

    def _infer_with_llm(self, target: str) -> tuple[str | None, str]:
        prompt = (
            f"El usuario quiere ejecutar o acceder a '{target}' en Windows.\n"
            "Determina el target correcto en un JSON estricto:\n"
            "- Si es web/IA: {\"execution_target\": \"https://chatgpt.com\", \"type\": \"url\"}\n"
            "- Si es protocolo de app: {\"execution_target\": \"steam://\", \"type\": \"protocol\"}\n"
            "- Si es comando de sistema: {\"execution_target\": \"calc.exe\", \"type\": \"app\"}\n"
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
