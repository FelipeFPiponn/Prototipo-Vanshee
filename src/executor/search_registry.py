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
from src.utils.query_cleaner import clean_search_term, is_first_result_requested


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
        self.last_search: Optional[dict] = None
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

    def _resolve_direct_youtube_video(self, clean_query: str) -> Optional[str]:
        """Obtiene de forma ultra-rápida la URL directa del primer video de YouTube para auto-reproducción."""
        if not clean_query:
            return None
        import urllib.request
        import re
        try:
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean_query)}"
            req = urllib.request.Request(
                search_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
                if video_ids:
                    return f"https://www.youtube.com/watch?v={video_ids[0]}"
        except Exception as e:
            print(f"[SearchRegistry YouTube AutoPlay Warning] {e}")
        return None

    def dispatch_search(
        self,
        target: str,
        query: str,
        window_manager: Optional[WindowManager] = None,
        app_indexer=None,
        raw_text: Optional[str] = None
    ) -> tuple[bool, str]:
        """Despacha la búsqueda de forma genérica, priorizando apps instaladas/abiertas, servicios web directos y reutilización de pestañas."""
        from src.executor.dynamic_resolver import WEB_SERVICES

        wm = window_manager or WindowManager()
        clean_target = target.lower().strip()

        # 1. Obtener o inferir el proveedor de búsqueda
        provider = self.get_provider(clean_target)
        if not provider:
            provider = self.infer_and_register_with_llm(clean_target)

        # Si aún no hay proveedor, crear uno genérico web (Google)
        if not provider:
            provider = self.providers.get("google")

        # Limpieza de prefijos y sufijos de relleno
        clean_query = clean_search_term(query)
        encoded_query = urllib.parse.quote(clean_query)

        # 2. Priorización de Aplicación de Escritorio
        if provider.prefer_desktop and self.is_app_installed_or_running(provider, wm, app_indexer):
            # Traer al frente la ventana si ya está abierta
            existing_win = wm.find_window(provider.id, additional_keywords=provider.window_keywords)
            if existing_win:
                wm.focus_window(existing_win["hwnd"])

            # Ejecutar mediante protocolo nativo de Windows (ej: spotify:search:lana%20del%20rey)
            if provider.app_uri:
                target_uri = provider.app_uri.format(query=encoded_query)
                try:
                    os.startfile(target_uri)
                    is_playback_request = (provider.id == "spotify") or any(w in (raw_text or query).lower() for w in ["pon", "reproduce", "cancion", "canción", "toca", "play", "musica", "música"])
                    msg = f"Reproduciendo '{clean_query}' en Spotify." if provider.id == "spotify" else (f"Reproduciendo '{clean_query}' en {provider.name}." if is_playback_request else f"Buscando '{clean_query}' en la aplicación de {provider.name}.")
                    print(f"[SearchRegistry Desktop] {msg} -> {target_uri}")

                    # Si es Spotify de escritorio, dar foco a la ventana y reproducir la primera coincidencia
                    if provider.id == "spotify":
                        try:
                            import time
                            import pyautogui
                            time.sleep(0.5)
                            win = wm.find_window("spotify")
                            if win:
                                wm.focus_window(win["hwnd"])
                                time.sleep(0.15)
                                pyautogui.press("down")
                                time.sleep(0.1)
                                pyautogui.press("enter")
                        except Exception as e:
                            print(f"[SearchRegistry Spotify AutoPlay Error] {e}")

                    return True, msg
                except Exception as e:
                    print(f"[SearchRegistry Error] Falló os.startfile('{target_uri}'): {e}")

        # 3. Resolución de URL de destino (Servicio Web Directo vs Primer Enlace vs Búsqueda Estándar)
        first_result_wanted = is_first_result_requested(raw_text or query)
        query_key = clean_query.lower().strip()

        # Si se busca una plataforma/marca conocida en un buscador web (ej: "solotodo", "solo todo", "chatgpt", "github")
        if provider.id in ["google", "web", "navegador", "buscador", "internet", "brave", "chrome", "edge", "firefox"] and query_key in WEB_SERVICES:
            final_url = WEB_SERVICES[query_key]
            action_description = f"Navegando directamente a {clean_query.title()} ({final_url})."
        elif provider.id == "youtube":
            direct_video = self._resolve_direct_youtube_video(clean_query)
            final_url = direct_video if direct_video else f"https://www.youtube.com/results?search_query={encoded_query}"
            action_description = f"Reproduciendo '{clean_query}' en {provider.name}."
        elif first_result_wanted and provider.id in ["google", "web", "navegador", "buscador", "internet", "brave", "chrome", "edge", "firefox"]:
            # Redirección directa al primer resultado usando el parámetro de Google I'm Feeling Lucky (&btnI=1)
            final_url = f"https://www.google.com/search?q={encoded_query}&btnI=1"
            action_description = f"Abriendo el primer resultado para '{clean_query}' en el navegador."
        else:
            web_template = provider.web_url or "https://www.google.com/search?q={query}"
            final_url = web_template.format(query=encoded_query)
            action_description = f"Buscando '{clean_query}' en {provider.name}."

        # 4. Registrar la última búsqueda para permitir comandos contextuales ("abre el primer link", "reproduce la primera canción")
        import time
        self.last_search = {
            "provider_id": provider.id,
            "provider_name": provider.name,
            "clean_query": clean_query,
            "final_url": final_url,
            "timestamp": time.time()
        }

        # 5. Priorización de Pestaña / Ventana Web ya abierta
        existing_web_win = wm.find_window(provider.id, additional_keywords=provider.window_keywords)
        if existing_web_win:
            wm.focus_window(existing_web_win["hwnd"])
            # Reutilizar pestaña activa cargando la URL en la barra de direcciones
            if wm.navigate_active_browser_tab(final_url):
                msg = f"Reutilizando pestaña de {provider.name} para: {action_description}"
                print(f"[SearchRegistry Tab Reuse] {msg}")
                return True, msg

        # 6. Apertura en navegador (nueva pestaña/ventana)
        try:
            webbrowser.open_new_tab(final_url)
            msg = action_description
            print(f"[SearchRegistry Web] {msg} -> {final_url}")
            return True, msg
        except Exception as e:
            err_msg = f"No pude abrir el navegador para la búsqueda en {provider.name}: {e}"
            print(f"[SearchRegistry Error] {err_msg}")
            return False, err_msg

    def open_first_result_of_last_search(
        self,
        action_type: str = "open_first_link",
        window_manager: Optional[WindowManager] = None
    ) -> tuple[bool, str]:
        """Abre el primer resultado de la búsqueda previa o interactúa con el primer elemento de la pantalla activa."""
        from src.executor.dynamic_resolver import WEB_SERVICES

        wm = window_manager or WindowManager()
        import time

        # 1. Si existe una búsqueda previa reciente (< 10 minutos)
        if self.last_search and (time.time() - self.last_search.get("timestamp", 0)) < 600:
            provider_id = self.last_search.get("provider_id", "")
            query = self.last_search.get("clean_query", "")

            # Caso A: YouTube ("reproduce el primer video / canción")
            if action_type in ["play_first", "play"] or provider_id == "youtube":
                direct_video = self._resolve_direct_youtube_video(query)
                if direct_video:
                    existing_win = wm.find_window("youtube", additional_keywords=["youtube"])
                    if existing_win:
                        wm.focus_window(existing_win["hwnd"])
                        wm.navigate_active_browser_tab(direct_video)
                    else:
                        webbrowser.open_new_tab(direct_video)
                    msg = f"Reproduciendo '{query}' en YouTube."
                    print(f"[SearchRegistry Contextual] {msg} -> {direct_video}")
                    return True, msg

            # Caso B: Spotify ("reproduce la primera canción")
            elif provider_id == "spotify" or action_type in ["play_first", "play"]:
                spotify_win = wm.find_window("spotify")
                if spotify_win:
                    wm.focus_window(spotify_win["hwnd"])
                    time.sleep(0.15)
                    try:
                        import pyautogui
                        pyautogui.press("enter")
                    except Exception:
                        pass
                    msg = f"Reproduciendo primer resultado en Spotify para '{query}'."
                    print(f"[SearchRegistry Contextual] {msg}")
                    return True, msg

            # Caso C: Google / Navegador ("abre el primer link / resultado")
            if provider_id in ["google", "web", "navegador", "brave", "chrome", "edge", "firefox"] or action_type == "open_first_link":
                query_key = query.lower().strip()
                if query_key in WEB_SERVICES:
                    url = WEB_SERVICES[query_key]
                else:
                    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&btnI=1"

                browser_win = wm.find_window("google", additional_keywords=["google", "chrome", "brave", "edge", "firefox", "nueva pestaña", "new tab"])
                if browser_win:
                    wm.focus_window(browser_win["hwnd"])
                    wm.navigate_active_browser_tab(url)
                else:
                    webbrowser.open_new_tab(url)
                msg = f"Abriendo el primer resultado para '{query}' en el navegador."
                print(f"[SearchRegistry Contextual] {msg} -> {url}")
                return True, msg

        # 2. Fallback: Interactuar con la ventana activa en primer plano
        active_windows = wm.get_open_windows()
        if active_windows:
            top_win = active_windows[0]
            top_title = top_win.get("title", "").lower()

            if any(b in top_title for b in ["chrome", "brave", "edge", "firefox", "google", "youtube"]):
                wm.focus_window(top_win["hwnd"])
                time.sleep(0.1)
                try:
                    import pyautogui
                    if action_type in ["play_first", "play"]:
                        pyautogui.press("enter")
                        msg = "Reproduciendo el contenido principal en el navegador."
                    else:
                        pyautogui.press("tab")
                        pyautogui.press("enter")
                        msg = "Navegando al primer enlace de la página activa."
                    return True, msg
                except Exception as e:
                    print(f"[SearchRegistry Fallback Error] {e}")

            elif "spotify" in top_title:
                wm.focus_window(top_win["hwnd"])
                time.sleep(0.1)
                try:
                    import pyautogui
                    pyautogui.press("enter")
                    return True, "Reproduciendo pista en Spotify."
                except Exception:
                    pass

        return False, "No encontré una búsqueda reciente ni una ventana activa para abrir el primer resultado."
