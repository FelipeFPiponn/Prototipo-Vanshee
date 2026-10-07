"""Cliente de Integración Directa para VALORANT y Riot Client.

Permite consultar la tienda diaria de skins, seleccionar y bloquear agentes de forma instantánea (auto-lock),
verificar rango competitivo y estado de grupo a través de la API local de Riot sin simulación de teclado.
"""

import os
import base64
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import requests
import urllib3

# Deshabilitar advertencias SSL para certificados autofirmados de Riot Client local
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Mapa de agentes oficiales de Valorant con sus UUIDs
AGENT_MAP = {
    "jett": "add6443a-41bd-e414-f6ad-e58d267f4e95",
    "reyna": "a3bfb807-4347-88a1-49fb-71edc546b721",
    "raze": "f94c3b30-42be-e959-889c-5aa313daf222",
    "omen": "8e253930-4c05-31dd-1b6c-968525494517",
    "sova": "320b2a48-4d9b-a075-30f1-1f93a9b638fa",
    "sage": "568548a2-47da-4526-e610-04a3f10e10c7",
    "phoenix": "eb9333ab-4034-ce4f-49b5-dae6b04a0e29",
    "viper": "707eab51-4836-f488-046a-cda6bf494859",
    "cypher": "117ed9e3-49f3-6516-da5e-f00905de9a33",
    "brimstone": "9f0d8ba9-42c6-9428-02d7-27943fa0595e",
    "killjoy": "1e58de9c-4950-523e-f32c-70a380e87f84",
    "skye": "6f2a04ca-43e0-be17-7f36-b3908627744d",
    "yoru": "7f94d92c-4234-0a36-9646-3a87eb8b5c89",
    "astra": "443312f9-4279-4358-8435-21be3545c05b",
    "kayo": "601fb3d5-4b29-e2d6-30c6-318e823b17e0",
    "kay/o": "601fb3d5-4b29-e2d6-30c6-318e823b17e0",
    "chamber": "22697a3d-45bf-8dd7-4fec-84a9e28c69d7",
    "neon": "bb2a483e-42d1-e773-0602-50b8431a4383",
    "fade": "dade69b4-4f5a-8528-247b-219e5a1facd6",
    "harbor": "95b78ed7-4637-86d9-7e41-71ba8c293152",
    "gekko": "e370fa57-4757-3604-3648-499e1f642d3f",
    "deadlock": "cc8e01d3-47f9-6378-eb81-f69263096b63",
    "iso": "0e38b510-41a8-5780-5e8f-568b2a4f2d6c",
    "clove": "1dbf2edd-4729-0984-3115-ffb5dde52525",
    "vyse": "efba5359-4016-a1e5-7626-b1ae76895940",
    "tejo": "b444168b-497c-a6ae-a2e6-a3bc76be42e7",
}


class ValorantClient:
    """Gestiona la comunicación con la API local de Valorant mediante Riot Lockfile."""

    def __init__(self):
        self.lockfile_path = self._find_lockfile()
        self.port: int = 0
        self.password: str = ""
        self.headers: Dict[str, str] = {}
        self.session_data: Dict[str, Any] = {}
        self.region: str = "latam"   # Default a región LATAM / NA

    def _find_lockfile(self) -> Optional[Path]:
        """Localiza el archivo lockfile de Riot Client en Windows."""
        local_app_data = os.getenv("LOCALAPPDATA", "")
        candidates = [
            Path(local_app_data) / "Riot Games" / "Riot Client" / "Config" / "lockfile" if local_app_data else None,
            Path(local_app_data) / "VALORANT" / "Saved" / "Config" / "lockfile" if local_app_data else None,
            Path("C:/Riot Games/Riot Client/Config/lockfile"),
            Path("D:/Riot Games/Riot Client/Config/lockfile"),
            Path("E:/Riot Games/Riot Client/Config/lockfile"),
        ]

        # Si hay procesos de Riot / Valorant en ejecución, revisar su directorio
        try:
            import psutil
            for proc in psutil.process_iter(["name", "exe"]):
                pname = (proc.info.get("name") or "").lower()
                if "riotclient" in pname or "valorant" in pname:
                    pexe = proc.info.get("exe")
                    if pexe:
                        candidates.append(Path(pexe).parent / "Config" / "lockfile")
                        candidates.append(Path(pexe).parent.parent / "Config" / "lockfile")
                        candidates.append(Path(pexe).parent / "lockfile")
        except Exception:
            pass

        for p in candidates:
            if p and p.exists():
                return p
        return None

    def is_game_running(self) -> bool:
        """Comprueba si Riot Client o Valorant están activos y su lockfile es legible."""
        self.lockfile_path = self._find_lockfile()
        return self.lockfile_path is not None and self.lockfile_path.exists()

    def connect(self) -> bool:
        """Lee el lockfile y establece las cabeceras de autenticación básica."""
        if not self.is_game_running():
            return False

        try:
            content = self.lockfile_path.read_text(encoding="utf-8").strip()
            # Formato: name:pid:port:password:protocol
            parts = content.split(":")
            if len(parts) >= 5:
                self.port = int(parts[2])
                self.password = parts[3]
                auth_token = base64.b64encode(f"riot:{self.password}".encode()).decode()
                self.headers = {
                    "Authorization": f"Basic {auth_token}",
                    "Content-Type": "application/json"
                }
                return True
        except Exception as e:
            print(f"[ValorantClient Error] Error al leer lockfile: {e}")
        return False

    def get_session_status(self) -> Dict[str, Any]:
        """Retorna el estado de conexión del cliente de Valorant."""
        if not self.connect():
            return {"connected": False, "message": "Valorant o Riot Client no están en ejecución."}

        try:
            url = f"https://127.0.0.1:{self.port}/chat/v1/session"
            res = requests.get(url, headers=self.headers, verify=False, timeout=2.0)
            if res.status_code == 200:
                data = res.json()
                return {
                    "connected": True,
                    "game_name": data.get("game_name", ""),
                    "tag_line": data.get("game_tag", ""),
                    "state": data.get("state", "connected")
                }
        except Exception as e:
            print(f"[ValorantClient Warning] No se pudo obtener sesión: {e}")

        return {"connected": True, "message": "Riot Client activo."}

    def lock_agent(self, agent_name: str) -> Tuple[bool, str]:
        """Bloquea automáticamente un agente durante la fase pre-game (selección de personajes)."""
        target = agent_name.lower().strip()
        agent_uuid = AGENT_MAP.get(target)
        if not agent_uuid:
            # Búsqueda parcial si el usuario dijo 'el nuevo agente' o nombre similar
            for k, v in AGENT_MAP.items():
                if target in k or k in target:
                    agent_uuid = v
                    target = k
                    break

        if not agent_uuid:
            return False, f"Agente '{agent_name}' no reconocido en Valorant."

        if not self.connect():
            return False, "Valorant no está en ejecución."

        try:
            # 1. Obtener entitlements del jugador (subject UUID y token)
            ent_url = f"https://127.0.0.1:{self.port}/entitlements/v1/token"
            ent_res = requests.get(ent_url, headers=self.headers, verify=False, timeout=2.0)
            if ent_res.status_code != 200:
                return False, "No se pudieron obtener credenciales de partida."

            ent_data = ent_res.json()
            player_uuid = ent_data.get("subject", "")
            access_token = ent_data.get("accessToken", "")
            token = ent_data.get("token", "")

            # 2. Obtener match_id de la fase pre-game
            glz_url = f"https://glz-{self.region}-1.{self.region}.a.pvp.net/pregame/v1/players/{player_uuid}"
            riot_headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Riot-Entitlements-JWT": token,
                "Content-Type": "application/json"
            }
            pregame_res = requests.get(glz_url, headers=riot_headers, timeout=3.0)
            if pregame_res.status_code != 200:
                return False, "No estás en la fase de selección de agente de una partida."

            match_id = pregame_res.json().get("MatchID")
            if not match_id:
                return False, "No se encontró el ID de la partida activa."

            # 3. Bloquear agente (Lock)
            lock_url = f"https://glz-{self.region}-1.{self.region}.a.pvp.net/pregame/v1/matches/{match_id}/lock/{agent_uuid}"
            lock_res = requests.post(lock_url, headers=riot_headers, timeout=3.0)

            if lock_res.status_code == 200:
                msg = f"¡Agente {target.title()} seleccionado y bloqueado con éxito!"
                print(f"[ValorantClient] {msg}")
                return True, msg
            else:
                return False, f"No se pudo bloquear a {target.title()} (quizás ya fue seleccionado)."

        except Exception as e:
            print(f"[ValorantClient Error] Error al bloquear agente: {e}")
            return False, f"Error al seleccionar agente en Valorant: {e}"

    def get_daily_store_summary(self) -> Tuple[bool, str]:
        """Consulta la rotación diaria de skins de la tienda del jugador."""
        if not self.connect():
            return False, "Valorant no está en ejecución para consultar la tienda."

        try:
            ent_url = f"https://127.0.0.1:{self.port}/entitlements/v1/token"
            ent_res = requests.get(ent_url, headers=self.headers, verify=False, timeout=2.0)
            if ent_res.status_code != 200:
                return False, "No se pudieron obtener las credenciales de la tienda."

            ent_data = ent_res.json()
            player_uuid = ent_data.get("subject", "")
            access_token = ent_data.get("accessToken", "")
            token = ent_data.get("token", "")

            store_url = f"https://pd.{self.region}.a.pvp.net/store/v2/storefront/{player_uuid}"
            riot_headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Riot-Entitlements-JWT": token,
                "Content-Type": "application/json"
            }
            res = requests.get(store_url, headers=riot_headers, timeout=4.0)
            if res.status_code == 200:
                store_data = res.json()
                skins_panel = store_data.get("SkinsPanelLayout", {})
                offers = skins_panel.get("SingleItemOffers", [])
                remaining = skins_panel.get("SingleItemOffersRemainingDurationInSeconds", 0)
                hours_left = max(0, int(remaining // 3600))
                msg = f"Tu tienda diaria de Valorant tiene {len(offers)} ofertas activas (tiempo restante: {hours_left}h)."
                print(f"[ValorantClient] {msg}")
                return True, msg
            return False, "No se pudo consultar el catálogo de la tienda."
        except Exception as e:
            return False, f"Error al consultar la tienda de Valorant: {e}"


# Instancia global compartida
valorant_client = ValorantClient()
