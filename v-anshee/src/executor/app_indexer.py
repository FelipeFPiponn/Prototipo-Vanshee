import os
import difflib
from pathlib import Path

class AppIndexer:
    def __init__(self):
        self.app_index: dict[str, str] = {}
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
        """Escanea el sistema y construye un índice local de aplicaciones."""
        self.app_index.clear()
        for search_dir in self._get_search_directories():
            for filepath in search_dir.rglob("*"):
                if filepath.suffix.lower() in [".lnk", ".exe"]:
                    # Limpieza del nombre de la aplicación
                    clean_name = filepath.stem.lower()
                    clean_name = (
                        clean_name.replace(" - acceso directo", "")
                        .replace(" - shortcut", "")
                        .strip()
                    )
                    if clean_name and clean_name not in self.app_index:
                        self.app_index[clean_name] = str(filepath)
        
        print(f"[AppIndexer] Se indexaron {len(self.app_index)} aplicaciones locales del equipo.")

    def find_app(self, target_name: str) -> str | None:
        """Busca una aplicación por coincidencia exacta, parcial o aproximada (fuzzy)."""
        target = target_name.lower().strip()

        # 1. Coincidencia exacta
        if target in self.app_index:
            return self.app_index[target]

        # 2. Coincidencia por subcadena (ej: "steam" dentro de "steam.lnk")
        for app_name, path in self.app_index.items():
            if target in app_name or app_name in target:
                return path

        # 3. Coincidencia borrosa / aproximada (Fuzzy Matching)
        matches = difflib.get_close_matches(target, self.app_index.keys(), n=1, cutoff=0.5)
        if matches:
            best_match = matches[0]
            print(f"[AppIndexer] Coincidencia aproximada hallada: '{target}' -> '{best_match}'")
            return self.app_index[best_match]

        return None