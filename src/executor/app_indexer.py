import os
import re
import time
import threading
import difflib
from pathlib import Path
from typing import Optional
from src.executor.steam_indexer import SteamIndexer

class AppIndexer:
    _instance: Optional["AppIndexer"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, cache_ttl_seconds: int = 3600):
        if getattr(self, "_initialized", False):
            return
        self.cache_ttl = cache_ttl_seconds
        self._last_scan = 0.0
        self.app_index: dict[str, str] = {}
        self.steam_indexer = SteamIndexer()
        self.refresh_index(force=True)
        self._initialized = True

    def _get_search_directories(self) -> list[Path]:
        """Obtiene las rutas estándar donde Windows almacena accesos directos de programas."""
        dirs = [
            Path(os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")),
            Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")),
            Path(os.path.expandvars(r"%USERPROFILE%\Desktop")),
            Path(os.path.expandvars(r"%PUBLIC%\Desktop")),
        ]
        return [d for d in dirs if d.exists()]

    def refresh_index(self, force: bool = False):
        """Escanea el sistema y construye un índice local de aplicaciones y juegos."""
        now = time.time()
        if not force and (now - self._last_scan) < self.cache_ttl and len(self.app_index) > 0:
            return
        self._last_scan = now
        self.app_index.clear()
        
        # 1. Escanear accesos directos locales (.lnk, .exe, .url)
        for search_dir in self._get_search_directories():
            for filepath in search_dir.rglob("*"):
                ext = filepath.suffix.lower()
                if ext in [".lnk", ".exe"]:
                    # Limpieza del nombre de la aplicación
                    clean_name = filepath.stem.lower()
                    clean_name = (
                        clean_name.replace(" - acceso directo", "")
                        .replace(" - shortcut", "")
                        .strip()
                    )
                    if clean_name and clean_name not in self.app_index:
                        self.app_index[clean_name] = str(filepath)
                elif ext == ".url":
                    clean_name = filepath.stem.lower()
                    clean_name = (
                        clean_name.replace(" - acceso directo", "")
                        .replace(" - shortcut", "")
                        .strip()
                    )
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                if line.strip().lower().startswith("url="):
                                    target_uri = line.split("=", 1)[1].strip()
                                    if target_uri and clean_name not in self.app_index:
                                        self.app_index[clean_name] = target_uri
                                    break
                    except Exception:
                        pass
        
        # 2. Integrar juegos de Steam detectados dinámicamente
        self.steam_indexer.refresh()
        for alias, uri in self.steam_indexer.alias_map.items():
            if alias not in self.app_index:
                self.app_index[alias] = uri

        # 3. Aplicaciones y utilidades nativas de Windows
        system_apps = {
            "bloc de notas": "notepad.exe",
            "notepad": "notepad.exe",
            "calculadora": "calc.exe",
            "calculator": "calc.exe",
            "explorador": "explorer.exe",
            "explorador de archivos": "explorer.exe",
            "archivos": "explorer.exe",
            "administrador de tareas": "taskmgr.exe",
            "task manager": "taskmgr.exe",
            "panel de control": "control.exe",
            "configuracion": "ms-settings:",
            "ajustes": "ms-settings:",
            "paint": "mspaint.exe",
            "recortes": "snippingtool.exe",
            "cmd": "cmd.exe",
            "simbolo del sistema": "cmd.exe",
            "terminal": "wt.exe",
            "powershell": "powershell.exe",
        }
        for name, cmd in system_apps.items():
            if name not in self.app_index:
                self.app_index[name] = cmd

        # 4. Comprobación directa de ejecutables conocidos
        common_candidates = {
            "discord": [
                os.path.expandvars(r"%LocalAppData%\Discord\Update.exe --processStart Discord.exe"),
                os.path.expandvars(r"%LocalAppData%\Programs\Discord\Discord.exe"),
            ],
            "opera gx": [
                os.path.expandvars(r"%LocalAppData%\Programs\Opera GX\launcher.exe"),
                os.path.expandvars(r"%ProgramFiles%\Opera GX\launcher.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Opera GX\launcher.exe"),
            ],
            "chrome": [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ],
            "brave": [
                os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            ],
            "edge": [
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            ],
            "spotify": [
                os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
                os.path.expandvars(r"%LocalAppData%\Microsoft\WindowsApps\Spotify.exe"),
                os.path.expandvars(r"%USERPROFILE%\AppData\Roaming\Spotify\Spotify.exe"),
            ],
            "vscode": [
                os.path.expandvars(r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code\Code.exe"),
            ]
        }
        for app_name, paths in common_candidates.items():
            if app_name not in self.app_index:
                for p in paths:
                    expanded = os.path.expandvars(p)
                    base_exe = expanded.split(" --")[0]
                    if os.path.exists(base_exe):
                        self.app_index[app_name] = expanded
                        break
        
        print(f"[AppIndexer] Se indexaron {len(self.app_index)} aplicaciones y juegos del equipo.")

    def find_app(self, target_name: str) -> str | None:
        """Busca una aplicación o juego por coincidencia exacta, alias, subcadena o aproximada (fuzzy)."""
        target = target_name.lower().strip()
        if not target:
            return None

        def _resolve_browser():
            if any("opera" in k for k in self.app_index):
                return "opera gx"
            if "chrome" in self.app_index:
                return "chrome"
            if "brave" in self.app_index:
                return "brave"
            return "edge"

        alias_map = {
            "vscode": "visual studio code",
            "vs code": "visual studio code",
            "visual code": "visual studio code",
            "code": "visual studio code",
            "antigravity": "antigravity ide",
            "codex": "visual studio code",
            "opencode": "visual studio code",
            "navegador": _resolve_browser(),
            "browser": _resolve_browser(),
            "terminal": "terminal",
            "cmd": "cmd",
            "notepad": "bloc de notas",
            "calc": "calculadora",
            "calculator": "calculadora",
            "archivos": "explorador de archivos",
            "taskmgr": "administrador de tareas",
        }
        search_target = alias_map.get(target, target)

        # 1. Coincidencia exacta (por alias o nombre directo)
        if search_target in self.app_index:
            return self.app_index[search_target]
        if target in self.app_index:
            return self.app_index[target]

        # 2. Búsqueda directa en SteamIndexer
        steam_match = self.steam_indexer.find_game(search_target)
        if steam_match:
            return steam_match["uri"]

        # 3. Coincidencia por subcadena (ej: "steam" dentro de "steam.lnk")
        for app_name, path in self.app_index.items():
            if len(search_target) >= 3 and (search_target in app_name or app_name in search_target):
                return path

        # 4. Coincidencia borrosa / aproximada (Fuzzy Matching con filtro)
        matches = difflib.get_close_matches(search_target, self.app_index.keys(), n=1, cutoff=0.72)
        if matches:
            best_match = matches[0]
            print(f"[AppIndexer] Coincidencia aproximada hallada: '{target_name}' -> '{best_match}'")
            return self.app_index[best_match]

        return None