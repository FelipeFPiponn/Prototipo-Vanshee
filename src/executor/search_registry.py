import os
import json
import sqlite3
import urllib.parse
import webbrowser
import winreg
from dataclasses import dataclass, field, asdict
from typing import Optional

from config.settings import settings
from src.routines.db import init_db
from src.executor.window_manager import WindowManager
from src.utils.query_cleaner import clean_search_term


@dataclass
class SearchProvider:
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    app_uri: Optional[str] = None            # Ej: "spotify:search:{query}" o "steam://store/search/?term={query}"
    web_url: Optional[str] = None            # Ej: "https://open.spotify.com/search/{query}"
    window_keywords: list[str] = field(default_factory=list)
    process_names: list[str] = field(default_factory=list)
    prefer_desktop: bool = True
    in_app_shortcut: Optional[str] = None   # Ej: "ctrl+k"


class SearchProviderRegistry:
    """Registro genérico y extensible de búsqueda en aplicaciones y servicios web."""

    DEFAULT_PROVIDERS = [
        SearchProvider(
            id="spotify",
            name="Spotify",
            aliases=["spotify", "spoty", "musica", "cancion", "canciones"],
            app_uri="spotify:search:{query}",
            web_url="https://open.spotify.com/search/{query}",
            window_keywords=["spotify"],
            process_names=["spotify.exe", "spotify"],
            prefer_desktop=True,
        ),
        SearchProvider(
            id="youtube",
            name="YouTube",
            aliases=["youtube", "yt", "videos", "videos de", "video"],
            app_uri=None,
            web_url="https://www.youtube.com/results?search_query={query}",
            window_keywords=["youtube"],
            process_names=[],
            prefer_desktop=False,
        ),
        SearchProvider(
            id="steam",
            name="Steam",
            aliases=["steam", "juegos", "tienda steam"],
            app_uri="steam://store/search/?term={query}",
            web_url="https://store.steampowered.com/search/?term={query}",
            window_keywords=["steam"],
            process_names=["steam.exe", "steam"],
            prefer_desktop=True,
        ),
        SearchProvider(
            id="google",
            name="Google",
            aliases=["google", "web", "internet", "buscador", "navegador", "brave", "chrome"],
            app_uri=None,
            web_url="https://www.google.com/search?q={query}",
            window_keywords=["google", "nueva pestaña", "new tab"],
            process_names=[],
            prefer_desktop=False,
        ),
        SearchProvider(
            id="github",
            name="GitHub",
            aliases=["github", "repositorio", "repositorios", "codigo"],
            app_uri=None,
            web_url="https://github.com/search?q={query}",
            window_keywords=["github"],
            process_names=[],
            prefer_desktop=False,
        ),
        SearchProvider(
            id="netflix",
            name="Netflix",
            aliases=["netflix", "series", "peliculas"],
            app_uri="netflix://search?q={query}",
            web_url="https://www.netflix.com/search?q={query}",
            window_keywords=["netflix"],
            process_names=["netflix.exe"],
            prefer_desktop=True,
        ),
    ]

    def __init__(self, db_path=None):
        self.db_path = db_path or settings.DB_PATH
        init_db()
        self.providers: dict[str, SearchProvider] = {}
        self._load_defaults()
        self._load_learned_providers()

    def _load_defaults(self):
        for p in self.DEFAULT_PROVIDERS:
            self.providers[p.id] = p

    def _load_learned_providers(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT target_key, provider_json FROM learned_search_providers")
            for row in cursor.fetchall():
                data = json.loads(row[1])
                provider = SearchProvider(**data)
                self.providers[row[0]] = provider
            conn.close()
        except Exception as e:
            print(f"[SearchRegistry Warning] Error cargando proveedores aprendidos: {e}")

    def save_learned_provider(self, provider: SearchProvider):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO learned_search_providers (target_key, provider_json)
                VALUES (?, ?)
                """,
                (provider.id, json.dumps(asdict(provider)))
            )
            conn.commit()
            conn.close()
            self.providers[provider.id] = provider
            print(f"[SearchRegistry] Nuevo proveedor aprendido y guardado: '{provider.name}'")
        except Exception as e:
            print(f"[SearchRegistry Error] No se pudo guardar proveedor: {e}")

    def is_protocol_registered(self, protocol_uri: str) -> bool:
        """Comprueba en el Registro de Windows si el esquema URI (ej: 'spotify:', 'steam:') está registrado."""
        if not protocol_uri:
            return False
        protocol_name = protocol_uri.split(":")[0].strip().lower()
        if not protocol_name:
            return False

        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_CLASSES_ROOT):
            try:
                with winreg.OpenKey(root, protocol_name) as key:
                    winreg.QueryValueEx(key, "URL Protocol")
                    return True
            except Exception:
                try:
                    with winreg.OpenKey(root, f"Software\\Classes\\{protocol_name}") as key:
                        winreg.QueryValueEx(key, "URL Protocol")
                        return True
                except Exception:
                    pass
        return False

    def is_app_installed_or_running(self, provider: SearchProvider, window_manager: WindowManager, app_indexer=None) -> bool:
        """Determina si la aplicación de escritorio está disponible en el sistema (ejecutándose o instalada)."""
        # 1. Ventana ya abierta
        if window_manager and provider.window_keywords:
            if window_manager.find_window(provider.id, additional_keywords=provider.window_keywords):
                return True

        # 2. Protocolo nativo registrado en Windows
        if provider.app_uri and self.is_protocol_registered(provider.app_uri):
            return True

        # 3. Aplicación local indexada (.lnk o .exe)
        if app_indexer:
            for alias in [provider.id, provider.name] + provider.aliases:
                if app_indexer.find_app(alias):
                    return True

        return False

    def get_provider(self, target: str) -> Optional[SearchProvider]:
        """Encuentra el proveedor adecuado por coincidencia de id o alias."""
        clean = target.lower().strip()
        if clean in self.providers:
            return self.providers[clean]

        for p in self.providers.values():
            if clean in p.aliases or any(a in clean for a in p.aliases):
                return p
            if p.id in clean:
                return p

        return None

    def infer_and_register_with_llm(self, target: str) -> Optional[SearchProvider]:
        """Aprende de forma autónoma una nueva regla de búsqueda mediante Ollama."""
        try:
            import ollama
            prompt = (
                f"El usuario quiere buscar contenido en el servicio o aplicación '{target}' en Windows OS.\n"
                "Genera la plantilla de búsqueda en JSON estricto con los siguientes campos:\n"
                "- id: identificador corto en minúsculas (ej: 'twitch', 'amazon')\n"
                "- name: nombre legible de la app (ej: 'Twitch')\n"
                "- aliases: lista de posibles alias\n"
                "- app_uri: esquema URI de Windows con marcador {{query}} si existe (ej: 'spotify:search:{{query}}') o null\n"
                "- web_url: URL web con marcador {{query}} (ej: 'https://www.twitch.tv/search?term={{query}}')\n"
                "- window_keywords: lista de palabras clave que suelen aparecer en el título de ventana\n"
                "- prefer_desktop: true si suele usarse como app de escritorio, false si es principalmente web\n"
            )
            response = ollama.chat(
                model=settings.OLLAMA_MODEL,
                messages=[{"role": "system", "content": prompt}],
                format="json"
            )
            data = json.loads(response["message"]["content"])
            data["prefer_desktop"] = bool(data.get("prefer_desktop", False))
            provider = SearchProvider(**data)
            self.save_learned_provider(provider)
            return provider
        except Exception as e:
            print(f"[SearchRegistry] Inferencia con LLM no disponible o falló: {e}")
            return None

    def dispatch_search(
        self,
        target: str,
        query: str,
        window_manager: Optional[WindowManager] = None,
        app_indexer=None
    ) -> tuple[bool, str]:
        """Despacha la búsqueda de forma genérica, priorizando apps instaladas/abiertas y reutilización de pestañas."""
        wm = window_manager or WindowManager()
        clean_target = target.lower().strip()

        # 1. Obtener o inferir el proveedor de búsqueda
        provider = self.get_provider(clean_target)
        if not provider:
            provider = self.infer_and_register_with_llm(clean_target)

        # Si aún no hay proveedor, crear uno genérico web (Google)
        if not provider:
            provider = self.providers.get("google")

        # Limpieza de prefijos de relleno ('canciones de', 'videos de', comillas, signos '+')
        clean_query = clean_search_term(query)
        encoded_query = urllib.parse.quote(clean_query)

        # 2. Priorización de Aplicación de Escritorio
        if provider.prefer_desktop and self.is_app_installed_or_running(provider, wm, app_indexer):
            # Traer al frente la ventana si ya está abierta
            existing_win = wm.find_window(provider.id, additional_keywords=provider.window_keywords)
            if existing_win:
                wm.focus_window(existing_win["hwnd"])

            # Ejecutar mediante protocolo nativo de Windows (ej: spotify:search:queen)
            if provider.app_uri:
                # Para Spotify y protocolos URI que aceptan espacios directamente, usamos clean_query
                # para evitar que el cliente de escritorio convierta '%20' en caracteres '+' literales.
                if provider.id == "spotify" or "?" not in provider.app_uri:
                    desktop_query = clean_query
                else:
                    desktop_query = encoded_query

                target_uri = provider.app_uri.format(query=desktop_query)
                try:
                    os.startfile(target_uri)
                    msg = f"Buscando '{clean_query}' en la aplicación de {provider.name}."
                    print(f"[SearchRegistry Desktop] {msg} -> {target_uri}")
                    return True, msg
                except Exception as e:
                    print(f"[SearchRegistry Error] Falló os.startfile('{target_uri}'): {e}")

        # 3. Priorización de Pestaña / Ventana Web ya abierta (ej: YouTube, Google)
        web_template = provider.web_url or f"https://www.google.com/search?q={{query}}"
        final_url = web_template.format(query=encoded_query)

        existing_web_win = wm.find_window(provider.id, additional_keywords=provider.window_keywords)
        if existing_web_win:
            wm.focus_window(existing_web_win["hwnd"])
            # Reutilizar pestaña activa cargando la URL en la barra de direcciones
            if wm.navigate_active_browser_tab(final_url):
                msg = f"Reutilizando pestaña de {provider.name} para buscar '{clean_query}'."
                print(f"[SearchRegistry Tab Reuse] {msg}")
                return True, msg

        # 4. Apertura en navegador (nueva pestaña/ventana)
        try:
            webbrowser.open_new_tab(final_url)
            msg = f"Buscando '{clean_query}' en {provider.name}."
            print(f"[SearchRegistry Web] {msg} -> {final_url}")
            return True, msg
        except Exception as e:
            err_msg = f"No pude abrir el navegador para la búsqueda en {provider.name}: {e}"
            print(f"[SearchRegistry Error] {err_msg}")
            return False, err_msg
