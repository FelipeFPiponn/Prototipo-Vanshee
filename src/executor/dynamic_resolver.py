import json
import sqlite3
import ollama
from config.settings import settings
from src.executor.app_indexer import AppIndexer
from src.routines.db import init_db

import re
import urllib.parse
from src.executor.steam_indexer import SteamIndexer

WEB_SERVICES = {
    # Búsqueda y hardware / e-commerce
    "solotodo": "https://www.solotodo.cl",
    "solo todo": "https://www.solotodo.cl",
    "solotodo.cl": "https://www.solotodo.cl",
    "pcfactory": "https://www.pcfactory.cl",
    "pc factory": "https://www.pcfactory.cl",
    "spdigital": "https://www.spdigital.cl",
    "sp digital": "https://www.spdigital.cl",
    "mercadolibre": "https://www.mercadolibre.cl",
    "mercado libre": "https://www.mercadolibre.cl",
    "amazon": "https://www.amazon.com",
    "aliexpress": "https://www.aliexpress.com",
    # IA y Productividad
    "chatgpt": "https://chatgpt.com",
    "chat gpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "deepseek": "https://chat.deepseek.com",
    "notion": "https://www.notion.so",
    "canva": "https://www.canva.com",
    # Redes y Multimedia
    "youtube": "https://youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "twitch": "https://www.twitch.tv",
    "reddit": "https://www.reddit.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "whatsapp": "https://web.whatsapp.com",
    "whatsapp web": "https://web.whatsapp.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "wikipedia": "https://es.wikipedia.org",
}

class DynamicResolver:
    def __init__(self):
        self.db_path = settings.DB_PATH
        init_db()
        self.indexer = AppIndexer()
        self.steam_indexer = self.indexer.steam_indexer

    def get_learned_command(self, keyword: str) -> str | None:
        from src.routines.db import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("SELECT execution_target FROM learned_commands WHERE keyword = ?", (keyword.lower(),))
            row = cursor.fetchone()
        if not row:
            return None
        target = row[0]
        if "\\" in target or "/" in target or "%" in target:
            from src.utils.path_resolver import normalize_user_path
            norm_p = normalize_user_path(target)
            if norm_p.exists():
                return str(norm_p)
            return None
        return target

    def save_learned_command(self, keyword: str, execution_target: str, command_type: str = "app"):
        from src.utils.path_resolver import to_portable_path
        portable_target = to_portable_path(execution_target) if ("\\" in execution_target or "/" in execution_target) else execution_target
        from src.routines.db import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO learned_commands (keyword, execution_target, command_type)
                VALUES (?, ?, ?)
            """, (keyword.lower(), portable_target, command_type))
        print(f"[Aprendizaje] V.ANSHEE aprendió: '{keyword}' -> '{portable_target}'")

    def forget_command(self, target: str) -> bool:
        target_clean = target.lower().strip()
        from src.routines.db import get_db_cursor
        with get_db_cursor() as cursor:
            if target_clean in ["last", "previous", "anterior", "eso", "none", "ultimo"]:
                cursor.execute("DELETE FROM learned_commands WHERE id = (SELECT MAX(id) FROM learned_commands)")
            else:
                cursor.execute("DELETE FROM learned_commands WHERE keyword LIKE ?", (f"%{target_clean}%",))
            deleted_count = cursor.rowcount
        return deleted_count > 0

    def resolve(self, target: str) -> tuple[str | None, str]:
        target_clean = target.lower().strip()

        # 0. Juegos de Steam detectados dinámicamente
        steam_game = self.steam_indexer.find_game(target_clean)
        if steam_game:
            return steam_game["uri"], "protocol"

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

        # Normalización de prefijos como 'la pagina de', 'el sitio de', 'la web de'
        clean_name = re.sub(r"^(?:la\s+|el\s+)?(?:pagina|página|web|sitio|portal)\s+(?:de\s+|web\s+de\s+)?", "", target_clean).strip()

        # Servicios Web conocidos
        if target_clean in WEB_SERVICES:
            return WEB_SERVICES[target_clean], "url"
        if clean_name in WEB_SERVICES:
            return WEB_SERVICES[clean_name], "url"

        # 1. Buscar en aplicaciones locales indexadas primero (.lnk, .exe, .url)
        local_path = self.indexer.find_app(target_clean)
        if not local_path and clean_name != target_clean:
            local_path = self.indexer.find_app(clean_name)

        # Fallback para navegadores si 'chrome' o 'navegador' no está instalado como tal
        if not local_path and target_clean in ["chrome", "google chrome", "navegador", "browser"]:
            local_path = (self.indexer.find_app("brave") or 
                          self.indexer.find_app("edge") or 
                          self.indexer.find_app("microsoft edge") or 
                          self.indexer.find_app("msedge"))

        if local_path:
            if local_path.startswith("steam://") or "://" in local_path and not local_path.startswith("http"):
                return local_path, "protocol"
            if local_path.startswith("http://") or local_path.startswith("https://"):
                return local_path, "url"
            return local_path, "app"


        # 2. Buscar en comandos aprendidos previamente en DB
        learned = self.get_learned_command(target_clean) or self.get_learned_command(clean_name)
        if learned:
            if learned.startswith("http://") or learned.startswith("https://"):
                cmd_type = "url"
            elif "://" in learned:
                cmd_type = "protocol"
            else:
                cmd_type = "app"
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
