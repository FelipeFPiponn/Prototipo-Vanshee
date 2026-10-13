import os
import re
import difflib
from pathlib import Path
from src.executor.steam_indexer import SteamIndexer

class AppIndexer:
    def __init__(self):
        self.app_index: dict[str, str] = {}
        self.steam_indexer = SteamIndexer()
        self.refresh_index()

    def _get_search_directories(self) -> list[Path]:
        """Obtiene las rutas estándar donde Windows almacena accesos directos de programas."""
        dirs = [
            Path(os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")),
            Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")),
            Path(os.path.expandvars(r"%USERPROFILE%\Desktop")),
            Path(r"C:\Users\Public\Desktop"),
        ]
        return [d for d in dirs if d.exists()]

    def refresh_index(self):
        """Escanea el sistema y construye un índice local de aplicaciones y juegos."""
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
        
        print(f"[AppIndexer] Se indexaron {len(self.app_index)} aplicaciones y juegos del equipo.")

    def find_app(self, target_name: str) -> str | None:
        """Busca una aplicación o juego por coincidencia exacta, alias, subcadena o aproximada (fuzzy)."""
        target = target_name.lower().strip()
        if not target:
            return None

        alias_map = {
            "vscode": "visual studio code",
            "vs code": "visual studio code",
            "visual code": "visual studio code",
            "code": "visual studio code",
            "antigravity": "antigravity ide",
            "codex": "visual studio code",
            "opencode": "visual studio code",
            "navegador": "chrome",
            "browser": "chrome",
            "terminal": "windows terminal",
            "cmd": "símbolo del sistema",
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