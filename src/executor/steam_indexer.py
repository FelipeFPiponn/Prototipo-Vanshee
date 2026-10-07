import os
import re
import difflib
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import winreg
except ImportError:
    winreg = None


class SteamIndexer:
    """Auto-indexador dinámico de juegos instalados en Steam para Windows."""

    IGNORED_APP_IDS = {
        "228980",  # Steamworks Common Redistributables
        "1070560", # Steam Linux Runtime
        "1391110", # Steam Linux Runtime - Soldier
        "1628350", # Steam Linux Runtime - Sniper
    }

    IGNORED_NAME_PREFIXES = (
        "steamworks",
        "steam linux runtime",
        "proton ",
        "source sdk",
    )

    def __init__(self):
        self.games: Dict[str, Dict[str, Any]] = {}
        self.alias_map: Dict[str, str] = {}  # alias -> steam://rungameid/<appid>
        self.refresh()

    def _get_steam_root(self) -> Optional[Path]:
        """Obtiene la ruta base de instalación de Steam desde el Registro de Windows o rutas estándar."""
        if winreg is not None:
            registry_paths = [
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            ]

            for hkey, subkey, val_name in registry_paths:
                try:
                    with winreg.OpenKey(hkey, subkey) as key:
                        val, _ = winreg.QueryValueEx(key, val_name)
                        if val and os.path.isdir(str(val)):
                            return Path(str(val).replace("/", "\\"))
                except Exception:
                    continue

        common_paths = [
            Path(r"C:\Program Files (x86)\Steam"),
            Path(r"C:\Program Files\Steam"),
            Path(r"D:\Steam"),
            Path(r"E:\Steam"),
            Path(r"D:\SteamLibrary"),
            Path(r"E:\SteamLibrary"),
        ]
        for p in common_paths:
            if p.is_dir():
                return p

        return None

    def _get_library_folders(self, steam_root: Path) -> list[Path]:
        """Lee libraryfolders.vdf para encontrar todas las bibliotecas de Steam en cualquier disco."""
        libraries = [steam_root]
        vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
        if not vdf_path.exists():
            return libraries

        try:
            with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Extraer todas las rutas "path" "X:\\..."
            found_paths = re.findall(r'"path"\s+"([^"]+)"', content, re.IGNORECASE)
            for p in found_paths:
                clean_p = p.replace("\\\\", "\\").replace("/", "\\")
                lib_path = Path(clean_p)
                if lib_path.is_dir() and lib_path not in libraries:
                    libraries.append(lib_path)
        except Exception as e:
            print(f"[SteamIndexer Error] Al leer libraryfolders.vdf: {e}")

        # También verificar bibliotecas típicas en otras unidades
        for drive in ["C", "D", "E", "F", "G"]:
            extra_lib = Path(f"{drive}:\\SteamLibrary")
            if extra_lib.is_dir() and extra_lib not in libraries:
                libraries.append(extra_lib)

        return libraries

    def _parse_manifest(self, manifest_file: Path) -> Optional[Dict[str, Any]]:
        """Lee un archivo appmanifest_<appid>.acf y extrae appid y name."""
        try:
            with open(manifest_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            appid_match = re.search(r'"appid"\s+"(\d+)"', content, re.IGNORECASE)
            name_match = re.search(r'"name"\s+"([^"]+)"', content, re.IGNORECASE)

            if not appid_match or not name_match:
                return None

            appid = appid_match.group(1).strip()
            name = name_match.group(1).strip()

            if appid in self.IGNORED_APP_IDS:
                return None

            name_lower = name.lower()
            if any(name_lower.startswith(pfx) for pfx in self.IGNORED_NAME_PREFIXES):
                return None

            return {
                "appid": appid,
                "name": name,
                "uri": f"steam://rungameid/{appid}",
                "manifest_path": str(manifest_file)
            }
        except Exception as e:
            print(f"[SteamIndexer Error] Leyendo {manifest_file.name}: {e}")
            return None

    def _generate_aliases(self, name: str, appid: str) -> list[str]:
        """Genera alias útiles para reconocimiento por voz y búsqueda tolerante."""
        aliases = set()
        clean = name.lower().strip()
        aliases.add(clean)

        # Eliminar caracteres especiales como ™, ®, ©, etc.
        no_symbols = re.sub(r"[™®©:]", "", clean).strip()
        no_symbols = re.sub(r"\s+", " ", no_symbols)
        if no_symbols:
            aliases.add(no_symbols)

        # Reemplazar puntos (ej: 'r.e.p.o.' -> 'repo')
        no_dots = clean.replace(".", "")
        if no_dots and no_dots != clean:
            aliases.add(no_dots)

        # Reemplazar guiones por espacios y viceversa
        if "-" in clean:
            aliases.add(clean.replace("-", " ").strip())
            aliases.add(clean.replace("-", "").strip())

        # Separar palabras compuestas comunes para tolerancia fonética
        # Ej: "warframe" -> "war frame"
        if clean == "warframe":
            aliases.add("war frame")
            aliases.add("guerfreim")
            aliases.add("guarfreim")
            aliases.add("warfare")

        if clean == "helldivers 2" or no_symbols == "helldivers 2":
            aliases.add("helldivers")
            aliases.add("helldivers two")
            aliases.add("helldivers dos")

        if clean == "monster hunter wilds":
            aliases.add("monster hunter wild")
            aliases.add("mhw")
            aliases.add("wilds")

        return list(aliases)

    def refresh(self):
        """Escanea todas las bibliotecas de Steam e indexa los juegos instalados."""
        self.games.clear()
        self.alias_map.clear()

        steam_root = self._get_steam_root()
        if not steam_root:
            print("[SteamIndexer] No se detectó instalación de Steam en el sistema.")
            return

        libraries = self._get_library_folders(steam_root)
        for lib in libraries:
            steamapps = lib / "steamapps"
            if not steamapps.is_dir():
                continue

            for manifest in steamapps.glob("appmanifest_*.acf"):
                parsed = self._parse_manifest(manifest)
                if parsed:
                    appid = parsed["appid"]
                    name = parsed["name"]
                    uri = parsed["uri"]
                    
                    self.games[appid] = parsed
                    
                    # Asociar alias
                    for alias in self._generate_aliases(name, appid):
                        self.alias_map[alias] = uri

        print(f"[SteamIndexer] Se indexaron {len(self.games)} juegos de Steam instalados dinámicamente.")

    def find_game(self, target_name: str) -> Optional[Dict[str, Any]]:
        """Busca un juego de Steam por coincidencia exacta, alias, subcadena o aproximada."""
        target = target_name.lower().strip()
        if not target or not self.alias_map:
            return None

        # Limpiar prefijos de comando si los tuviera
        target = re.sub(r"^(?:juego|el juego|abrir|abre|inicia|ejecuta)\s+", "", target).strip()

        # 1. Coincidencia directa en alias_map
        if target in self.alias_map:
            uri = self.alias_map[target]
            appid = uri.split("/")[-1]
            return self.games.get(appid, {"name": target, "uri": uri, "appid": appid})

        # 2. Coincidencia por subcadena
        for alias, uri in self.alias_map.items():
            if target in alias or alias in target:
                appid = uri.split("/")[-1]
                return self.games.get(appid, {"name": alias, "uri": uri, "appid": appid})

        # 3. Coincidencia aproximada / fuzzy
        matches = difflib.get_close_matches(target, list(self.alias_map.keys()), n=1, cutoff=0.70)
        if matches:
            best_alias = matches[0]
            uri = self.alias_map[best_alias]
            appid = uri.split("/")[-1]
            print(f"[SteamIndexer] Coincidencia aproximada hallada: '{target_name}' -> '{best_alias}' ({uri})")
            return self.games.get(appid, {"name": best_alias, "uri": uri, "appid": appid})

        return None
