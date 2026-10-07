"""Cliente de Integración Directa para League of Legends (LCU API).

Permite interactuar directamente con el cliente de LoL mediante el protocolo LCU (League Client Update):
- Aceptar o rechazar partidas en cola (Ready Check) automáticamente.
- Iniciar o cancelar la búsqueda de partida (Matchmaking Queue).
- Consultar la fase actual de juego (Lobby, Matchmaking, ReadyCheck, ChampSelect, InProgress).
- Bloqueo / Selección automática de campeones.
"""

import os
import re
import base64
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import requests
import urllib3
import psutil

# Deshabilitar advertencias SSL para certificados autofirmados de Riot Client local
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class LeagueOfLegendsClient:
    """Gestiona la comunicación con la API local LCU de League of Legends."""

    def __init__(self):
        self.port: int = 0
        self.password: str = ""
        self.headers: Dict[str, str] = {}
        self._connected: bool = False

    def _find_lcu_credentials(self) -> bool:
        """Localiza el puerto y token de autenticación de League of Legends."""
        # 1. Intentar leer desde lockfile en rutas habituales
        candidates = [
            Path(os.getenv("LOCALAPPDATA", "")) / "Riot Games" / "League of Legends" / "Config" / "lockfile",
            Path("C:/Riot Games/League of Legends/lockfile"),
            Path("D:/Riot Games/League of Legends/lockfile"),
            Path("E:/Riot Games/League of Legends/lockfile"),
            Path("C:/Program Files/Riot Games/League of Legends/lockfile"),
            Path("D:/Program Files/Riot Games/League of Legends/lockfile"),
        ]

        # 2. Si hay procesos de League of Legends activos, agregar su directorio a las rutas candidatas
        try:
            for proc in psutil.process_iter(["name", "cmdline", "exe"]):
                pname = (proc.info.get("name") or "").lower()
                if "leagueclient" in pname or "riotclient" in pname:
                    pexe = proc.info.get("exe")
                    if pexe:
                        candidates.append(Path(pexe).parent / "lockfile")
                        candidates.append(Path(pexe).parent.parent / "lockfile")

                    # Inspeccionar argumentos de línea de comandos de LeagueClientUx.exe
                    cmdline = proc.info.get("cmdline") or []
                    port = None
                    token = None
                    for arg in cmdline:
                        if arg.startswith("--app-port="):
                            port = int(arg.split("=")[1])
                        elif arg.startswith("--remoting-auth-token="):
                            token = arg.split("=")[1]

                    if port and token:
                        self.port = port
                        self.password = token
                        auth = base64.b64encode(f"riot:{self.password}".encode()).decode()
                        self.headers = {
                            "Authorization": f"Basic {auth}",
                            "Content-Type": "application/json"
                        }
                        self._connected = True
                        return True
        except Exception:
            pass

        for path in candidates:
            if path and path.exists():
                try:
                    content = path.read_text(encoding="utf-8").strip()
                    parts = content.split(":")
                    if len(parts) >= 5:
                        self.port = int(parts[2])
                        self.password = parts[3]
                        auth = base64.b64encode(f"riot:{self.password}".encode()).decode()
                        self.headers = {
                            "Authorization": f"Basic {auth}",
                            "Content-Type": "application/json"
                        }
                        self._connected = True
                        return True
                except Exception:
                    pass

        self._connected = False
        return False

    def is_running(self) -> bool:
        """Verifica si el cliente de League of Legends está activo."""
        return self._find_lcu_credentials()

    def get_gameflow_phase(self) -> Tuple[bool, str]:
        """Obtiene la fase actual del juego (Lobby, Matchmaking, ReadyCheck, ChampSelect, InProgress)."""
        if not self._find_lcu_credentials():
            return False, "League of Legends no está en ejecución."

        try:
            url = f"https://127.0.0.1:{self.port}/lol-gameflow/v1/gameflow-phase"
            res = requests.get(url, headers=self.headers, verify=False, timeout=2.0)
            if res.status_code == 200:
                phase = res.json()  # Ej: 'Lobby', 'Matchmaking', 'ReadyCheck', 'ChampSelect', 'InProgress', 'None'
                phase_names = {
                    "None": "En el menú principal",
                    "Lobby": "En sala de espera (Lobby)",
                    "Matchmaking": "Buscando partida en cola",
                    "ReadyCheck": "¡Partida encontrada! Confirmación pendiente",
                    "ChampSelect": "En fase de selección de campeón",
                    "InProgress": "Partida en curso",
                    "WaitingForStats": "Fin de partida"
                }
                msg = phase_names.get(phase, f"Fase actual: {phase}")
                print(f"[LoLClient] {msg}")
                return True, msg
            return False, "No se pudo consultar la fase de League of Legends."
        except Exception as e:
            return False, f"Error de conexión con League of Legends: {e}"

    def accept_match(self) -> Tuple[bool, str]:
        """Acepta la partida encontrada en el Ready Check."""
        if not self._find_lcu_credentials():
            return False, "League of Legends no está en ejecución."

        try:
            url = f"https://127.0.0.1:{self.port}/lol-matchmaking/v1/ready-check/accept"
            res = requests.post(url, headers=self.headers, verify=False, timeout=2.0)
            if res.status_code in [200, 204]:
                msg = "¡Partida aceptada en League of Legends!"
                print(f"[LoLClient] {msg}")
                return True, msg
            return False, "No hay una partida lista para aceptar en este momento."
        except Exception as e:
            return False, f"Error al aceptar partida: {e}"

    def decline_match(self) -> Tuple[bool, str]:
        """Rechaza la partida encontrada en el Ready Check."""
        if not self._find_lcu_credentials():
            return False, "League of Legends no está en ejecución."

        try:
            url = f"https://127.0.0.1:{self.port}/lol-matchmaking/v1/ready-check/decline"
            res = requests.post(url, headers=self.headers, verify=False, timeout=2.0)
            if res.status_code in [200, 204]:
                msg = "Partida rechazada en League of Legends."
                print(f"[LoLClient] {msg}")
                return True, msg
            return False, "No hay una partida lista para rechazar."
        except Exception as e:
            return False, f"Error al rechazar partida: {e}"

    def start_queue(self) -> Tuple[bool, str]:
        """Inicia la búsqueda de partida en el lobby activo."""
        if not self._find_lcu_credentials():
            return False, "League of Legends no está en ejecución."

        try:
            url = f"https://127.0.0.1:{self.port}/lol-lobby/v2/lobby/matchmaking/search"
            res = requests.post(url, headers=self.headers, verify=False, timeout=2.0)
            if res.status_code in [200, 204]:
                msg = "Búsqueda de partida iniciada en League of Legends."
                print(f"[LoLClient] {msg}")
                return True, msg
            return False, "No se pudo iniciar la cola. Asegúrate de estar en un lobby."
        except Exception as e:
            return False, f"Error al iniciar cola: {e}"

    def cancel_queue(self) -> Tuple[bool, str]:
        """Cancela la búsqueda de partida en cola."""
        if not self._find_lcu_credentials():
            return False, "League of Legends no está en ejecución."

        try:
            url = f"https://127.0.0.1:{self.port}/lol-lobby/v2/lobby/matchmaking/search"
            res = requests.delete(url, headers=self.headers, verify=False, timeout=2.0)
            if res.status_code in [200, 204]:
                msg = "Búsqueda de partida cancelada en League of Legends."
                print(f"[LoLClient] {msg}")
                return True, msg
            return False, "No estás en cola de búsqueda actualmente."
        except Exception as e:
            return False, f"Error al cancelar cola: {e}"

    def _resolve_champion_id(self, champion_name: str) -> Tuple[Optional[int], str]:
        """Resuelve el ID de un campeón por nombre (dinámico LCU o fallback local)."""
        clean = champion_name.lower().strip()
        # Eliminar prefijos comunes
        clean = re.sub(r"^(?:al\s+campeon|a\s+la\s+campeona|al\s+personaje|a|el|la)\s+", "", clean).strip()

        # 1. Intentar consultar el resumen de campeones dinámico de LCU
        if self._find_lcu_credentials():
            try:
                url = f"https://127.0.0.1:{self.port}/lol-game-data/assets/v1/champion-summary.json"
                res = requests.get(url, headers=self.headers, verify=False, timeout=2.0)
                if res.status_code == 200:
                    for champ in res.json():
                        c_name = champ.get("name", "").lower()
                        c_alias = champ.get("alias", "").lower()
                        if clean == c_name or clean == c_alias or clean in c_name:
                            return champ.get("id"), champ.get("name", clean)
            except Exception:
                pass

        # 2. Diccionario local de campeones oficiales de League of Legends
        champion_db = {
            "aatrox": 266, "ahri": 103, "akali": 84, "akshan": 166, "alistar": 12, "ambessa": 799,
            "amumu": 32, "anivia": 34, "annie": 1, "aphelios": 523, "ashe": 22, "aurelion sol": 136,
            "aurora": 893, "azir": 268, "bard": 432, "belveth": 200, "bel'veth": 200, "blitzcrank": 53,
            "brand": 63, "braum": 201, "briar": 233, "caitlyn": 51, "camille": 164, "cassiopeia": 69,
            "chogath": 31, "cho'gath": 31, "corki": 42, "darius": 122, "diana": 131, "dr. mundo": 36,
            "mundo": 36, "draven": 119, "ekko": 245, "elise": 60, "evelynn": 28, "ezreal": 81,
            "fiddlesticks": 9, "fiora": 114, "fizz": 105, "galio": 3, "gangplank": 41, "garen": 86,
            "gnar": 150, "gragas": 79, "graves": 104, "gwen": 887, "hecarim": 120, "heimerdinger": 74,
            "hwei": 910, "illaoi": 420, "irelia": 39, "ivern": 427, "janna": 40, "jarvan": 59,
            "jarvan iv": 59, "jax": 24, "jayce": 126, "jhin": 202, "jinx": 222, "ksante": 897,
            "k'sante": 897, "kaisa": 145, "kai'sa": 145, "kalista": 429, "karma": 43, "karthus": 30,
            "kassadin": 38, "katarina": 55, "kayle": 10, "kayn": 141, "kennen": 85, "khazix": 121,
            "kha'zix": 121, "kindred": 203, "kled": 240, "kogmaw": 96, "kog'maw": 96, "leblanc": 7,
            "lee sin": 64, "lee": 64, "leona": 89, "lillia": 876, "lissandra": 127, "lucian": 236,
            "lulu": 117, "lux": 99, "malphite": 54, "malzahar": 90, "maokai": 57, "master yi": 11,
            "yi": 11, "mel": 800, "milio": 902, "miss fortune": 21, "mf": 21, "mordekaiser": 82,
            "morgana": 25, "naafiri": 950, "nami": 267, "nasus": 75, "nautilus": 111, "neeko": 518,
            "nidalee": 76, "nilah": 895, "nocturne": 56, "nunu": 20, "olaf": 2, "orianna": 61,
            "ornn": 516, "pantheon": 80, "poppy": 78, "pyke": 555, "qiyana": 246, "quinn": 133,
            "rakan": 497, "rammus": 33, "reksai": 421, "rek'sai": 421, "rell": 526, "renata": 888,
            "renata glasc": 888, "renektan": 58, "renekton": 58, "rengar": 107, "riven": 92, "rumble": 68,
            "ryze": 13, "samira": 360, "sejuani": 113, "senna": 235, "seraphine": 147, "sett": 875,
            "shaco": 35, "shen": 98, "shyvana": 102, "singed": 27, "sion": 14, "sivir": 15,
            "skarner": 72, "smolder": 901, "sona": 37, "soraka": 16, "swain": 50, "sylas": 517,
            "syndra": 134, "tahm kench": 223, "tahm": 223, "taliyah": 163, "talon": 91, "taric": 44,
            "teemo": 17, "thresh": 412, "tristana": 18, "trundle": 48, "tryndamere": 23,
            "twisted fate": 4, "tf": 4, "twitch": 29, "udyr": 77, "urgot": 6, "varus": 110,
            "vayne": 67, "veigar": 45, "velkoz": 161, "vel'koz": 161, "vex": 711, "vi": 254,
            "viego": 234, "viktor": 112, "vladimir": 8, "volibear": 106, "warwick": 19, "wukong": 62,
            "xayah": 498, "xerath": 101, "xin zhao": 5, "yasuo": 157, "yone": 777, "yorick": 83,
            "yuumi": 350, "zac": 154, "zed": 238, "zeri": 221, "ziggs": 115, "zilean": 26,
            "zoe": 142, "zyra": 143
        }

        if clean in champion_db:
            return champion_db[clean], clean

        # Coincidencia parcial
        for k, v in champion_db.items():
            if clean in k or k in clean:
                return v, k

        return None, clean

    def pick_champion(self, champion_name: str, lock_in: bool = True) -> Tuple[bool, str]:
        """Selecciona y bloquea un campeón en la fase de Champion Select."""
        if not self._find_lcu_credentials():
            return False, "League of Legends no está en ejecución."

        champ_id, clean_name = self._resolve_champion_id(champion_name)
        if not champ_id:
            return False, f"No reconocí al campeón '{champion_name}' en League of Legends."

        try:
            url_session = f"https://127.0.0.1:{self.port}/lol-champ-select/v1/session"
            res_sess = requests.get(url_session, headers=self.headers, verify=False, timeout=2.0)
            if res_sess.status_code != 200:
                return False, "No estás en la fase de Selección de Campeones (Champ Select)."

            session = res_sess.json()
            local_cell_id = session.get("localPlayerCellId")
            actions = session.get("actions", [])

            target_action_id = None
            for action_group in actions:
                for action in action_group:
                    if action.get("actorCellId") == local_cell_id and action.get("type") == "pick" and not action.get("completed", False):
                        target_action_id = action.get("id")
                        break
                if target_action_id:
                    break

            if not target_action_id:
                for action_group in actions:
                    for action in action_group:
                        if action.get("actorCellId") == local_cell_id and action.get("type") == "pick":
                            target_action_id = action.get("id")
                            break
                    if target_action_id:
                        break

            if not target_action_id:
                return False, "No se encontró un turno activo de selección para tu jugador."

            patch_url = f"https://127.0.0.1:{self.port}/lol-champ-select/v1/session/actions/{target_action_id}"
            payload = {
                "championId": champ_id,
                "completed": lock_in
            }
            res_patch = requests.patch(patch_url, headers=self.headers, json=payload, verify=False, timeout=2.0)
            if res_patch.status_code in [200, 204]:
                action_text = "seleccionado y bloqueado" if lock_in else "seleccionado"
                msg = f"¡Campeón {clean_name.title()} {action_text} con éxito en League of Legends!"
                print(f"[LoLClient] {msg}")
                return True, msg
            else:
                return False, f"No se pudo seleccionar a {clean_name.title()} en este momento."

        except Exception as e:
            return False, f"Error al seleccionar campeón en LoL: {e}"

    def ban_champion(self, champion_name: str) -> Tuple[bool, str]:
        """Banea un campeón en la fase de baneo de Champion Select."""
        if not self._find_lcu_credentials():
            return False, "League of Legends no está en ejecución."

        champ_id, clean_name = self._resolve_champion_id(champion_name)
        if not champ_id:
            return False, f"No reconocí al campeón '{champion_name}' en League of Legends."

        try:
            url_session = f"https://127.0.0.1:{self.port}/lol-champ-select/v1/session"
            res_sess = requests.get(url_session, headers=self.headers, verify=False, timeout=2.0)
            if res_sess.status_code != 200:
                return False, "No estás en la fase de Selección de Campeones."

            session = res_sess.json()
            local_cell_id = session.get("localPlayerCellId")
            actions = session.get("actions", [])

            target_action_id = None
            for action_group in actions:
                for action in action_group:
                    if action.get("actorCellId") == local_cell_id and action.get("type") == "ban" and not action.get("completed", False):
                        target_action_id = action.get("id")
                        break
                if target_action_id:
                    break

            if not target_action_id:
                return False, "No se encontró un turno activo de baneo para tu jugador."

            patch_url = f"https://127.0.0.1:{self.port}/lol-champ-select/v1/session/actions/{target_action_id}"
            payload = {
                "championId": champ_id,
                "completed": True
            }
            res_patch = requests.patch(patch_url, headers=self.headers, json=payload, verify=False, timeout=2.0)
            if res_patch.status_code in [200, 204]:
                msg = f"¡Campeón {clean_name.title()} baneado en League of Legends!"
                print(f"[LoLClient] {msg}")
                return True, msg
            else:
                return False, f"No se pudo banear a {clean_name.title()}."
        except Exception as e:
            return False, f"Error al banear campeón: {e}"


# Instancia global compartida
lol_client = LeagueOfLegendsClient()
