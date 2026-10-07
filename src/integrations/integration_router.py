"""Enrutador Unificado de Integraciones Directas para V.ANSHEE.

Despacha solicitudes específicas de Spotify, Valorant, OBS Studio, Mezclador de Audio,
Hardware y Obsidian directamente sin simulación de interfaz.
"""

from typing import Tuple, Dict, Any

from src.integrations.spotify_controller import spotify_controller
from src.integrations.audio_mixer import audio_mixer
from src.integrations.valorant_client import valorant_client
from src.integrations.lol_client import lol_client
from src.integrations.discord_client import discord_client
from src.integrations.obs_controller import obs_controller
from src.integrations.hardware_monitor import hardware_monitor
from src.integrations.obsidian_client import obsidian_client


class IntegrationRouter:
    """Orquesta las llamadas directas a las APIs e integraciones de aplicaciones."""

    def __init__(self):
        self.spotify = spotify_controller
        self.mixer = audio_mixer
        self.valorant = valorant_client
        self.lol = lol_client
        self.discord = discord_client
        self.obs = obs_controller
        self.hardware = hardware_monitor
        self.obsidian = obsidian_client

    def execute_direct_action(self, action_type: str, target: str = "", params: Dict[str, Any] = None) -> Tuple[bool, str]:
        """Despacha la acción a la integración correspondiente."""
        action = action_type.upper().strip()
        p = params or {}

        # 1. Spotify
        if action == "SPOTIFY_NOW_PLAYING" or (action == "NOW_PLAYING" and "spotify" in target):
            msg = self.spotify.get_now_playing_summary()
            return True, msg

        elif action == "SPOTIFY_LIKE":
            return self.spotify.like_current_track()

        elif action == "SPOTIFY_QUEUE":
            query = p.get("content", target)
            return self.spotify.add_to_queue(query)

        # 2. Mezclador de Audio de Windows
        elif action in ["SET_VOLUME_PCT", "SET_APP_VOLUME"]:
            vol_val = p.get("volume", 50)
            if target in ["master", "general", "sistema", "windows", ""]:
                return self.mixer.set_master_volume(vol_val)
            return self.mixer.set_app_volume(target, vol_val)

        elif action in ["MUTE_APP", "SILENCE_APP"]:
            return self.mixer.mute_app(target, mute=True)

        elif action in ["UNMUTE_APP", "DESMUTEAR_APP"]:
            return self.mixer.mute_app(target, mute=False)

        # 3. Valorant
        elif action == "VALORANT_LOCK" or (action == "LOCK_AGENT" and ("valorant" in target or target in self.valorant.AGENT_MAP if hasattr(self.valorant, "AGENT_MAP") else True)):
            agent_name = p.get("content") or target
            return self.valorant.lock_agent(agent_name)

        elif action == "VALORANT_STORE" or (action == "CHECK_STORE" and "valorant" in target):
            return self.valorant.get_daily_store_summary()

        # 4. League of Legends (LCU API)
        elif action in ["LOL_ACCEPT", "LOL_ACCEPT_MATCH"]:
            return self.lol.accept_match()

        elif action in ["LOL_DECLINE", "LOL_DECLINE_MATCH", "LOL_REJECT"]:
            return self.lol.decline_match()

        elif action in ["LOL_START_QUEUE", "LOL_QUEUE_START", "LOL_FIND_MATCH"]:
            return self.lol.start_queue()

        elif action in ["LOL_CANCEL_QUEUE", "LOL_QUEUE_CANCEL", "LOL_LEAVE_QUEUE"]:
            return self.lol.cancel_queue()

        elif action in ["LOL_PICK", "LOL_LOCK", "LOL_SELECT_CHAMPION", "LOL_CHAMPION_SELECT"]:
            champ_name = p.get("content") or target
            return self.lol.pick_champion(champ_name, lock_in=True)

        elif action in ["LOL_BAN", "LOL_BAN_CHAMPION"]:
            champ_name = p.get("content") or target
            return self.lol.ban_champion(champ_name)

        elif action in ["LOL_STATUS", "LOL_GAMEFLOW"]:
            return self.lol.get_gameflow_phase()

        # 4.5. Discord Desktop
        elif action in ["DISCORD_CONNECT_VOICE", "DISCORD_VOICE", "DISCORD_JOIN_CHANNEL", "DISCORD_JOIN_VOICE"]:
            ch_name = p.get("content") or target or "general"
            return self.discord.connect_voice_channel(ch_name)

        elif action in ["DISCORD_DISCONNECT_VOICE", "DISCORD_LEAVE_VOICE", "DISCORD_LEAVE_CHANNEL", "DISCORD_DISCONNECT"]:
            return self.discord.disconnect_voice()

        # 5. OBS Studio
        elif action in ["OBS_RECORD", "OBS_TOGGLE_RECORD"]:
            return self.obs.toggle_recording()

        elif action == "OBS_START_RECORD":
            return self.obs.start_recording()

        elif action == "OBS_STOP_RECORD":
            return self.obs.stop_recording()

        elif action == "OBS_SCENE":
            scene_name = p.get("content") or target
            return self.obs.set_scene(scene_name)

        elif action == "OBS_REPLAY":
            return self.obs.save_replay_buffer()

        # 5. Hardware y Diagnóstico
        elif action in ["SYSTEM_DIAGNOSTIC", "HARDWARE_STATUS", "CHECK_HARDWARE"]:
            msg = self.hardware.get_voice_summary()
            return True, msg

        # 6. Obsidian
        elif action == "OBSIDIAN_NOTE":
            content = p.get("content", target)
            return self.obsidian.append_daily_note(content)

        elif action == "OBSIDIAN_TODO":
            task_text = p.get("content", target)
            return self.obsidian.add_todo_task(task_text)

        return False, f"Acción directa '{action_type}' no reconocida."


# Instancia global compartida
integration_router = IntegrationRouter()
