"""Controlador de volumen individual por aplicación y volumen maestro de Windows.

Utiliza Windows Core Audio API (pycaw / comtypes) para ajustar volúmenes y silenciar
aplicaciones específicas (Spotify, Discord, Juegos, Navegadores) en < 5ms sin abrir el mezclador de Windows.
"""

import sys
import psutil
from typing import Dict, List, Optional, Tuple

try:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume
    PYCAW_AVAILABLE = True
except Exception as e:
    PYCAW_AVAILABLE = False
    print(f"[AudioMixer Warning] pycaw no disponible: {e}")


class AudioMixerController:
    """Gestiona el mezclador de audio de Windows a nivel de aplicación individual."""

    def __init__(self):
        self.available = PYCAW_AVAILABLE

    def _ensure_com_init(self):
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass

    def list_audio_sessions(self) -> List[Dict[str, any]]:
        """Lista todas las aplicaciones con sesiones de audio activas en Windows."""
        if not self.available:
            return []

        self._ensure_com_init()
        sessions_info = []
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                volume = session.SimpleAudioVolume
                if session.Process:
                    p_name = session.Process.name().lower()
                    display_name = session.Process.name()
                    pid = session.Process.pid
                else:
                    p_name = "sistema"
                    display_name = "Audio del Sistema"
                    pid = 0

                is_muted = bool(volume.GetMute())
                vol_level = round(volume.GetMasterVolume() * 100)
                sessions_info.append({
                    "name": display_name,
                    "process_name": p_name,
                    "pid": pid,
                    "volume": vol_level,
                    "is_muted": is_muted
                })
        except Exception as e:
            print(f"[AudioMixer Error] Error al listar sesiones: {e}")

        return sessions_info

    def set_app_volume(self, app_name: str, volume_pct: float) -> Tuple[bool, str]:
        """Ajusta el volumen (0 a 100) de una aplicación específica."""
        if not self.available:
            return False, "Control de audio no disponible en este entorno."

        self._ensure_com_init()
        target = app_name.lower().strip()
        # Normalizar nombres comunes
        alias_map = {
            "juego": ["valorant", "league", "steam", "warframe", "genshin", "overwatch", "cs2"],
            "spotify": ["spotify.exe", "spotify"],
            "discord": ["discord.exe", "discord"],
            "navegador": ["chrome.exe", "chrome", "msedge.exe", "msedge", "brave.exe", "firefox.exe"],
            "chrome": ["chrome.exe", "chrome"],
            "edge": ["msedge.exe", "msedge"],
            "youtube": ["chrome.exe", "msedge.exe", "brave.exe", "firefox.exe"]
        }

        search_terms = alias_map.get(target, [target])
        vol_scalar = max(0.0, min(1.0, volume_pct / 100.0))

        found = False
        matched_apps = []
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if not session.Process:
                    continue
                p_name = session.Process.name().lower()
                for term in search_terms:
                    if term in p_name:
                        volume = session.SimpleAudioVolume
                        volume.SetMasterVolume(vol_scalar, None)
                        found = True
                        matched_apps.append(session.Process.name())
                        break

            if found:
                msg = f"Volumen de '{', '.join(set(matched_apps))}' ajustado al {int(volume_pct)}%."
                print(f"[AudioMixer] {msg}")
                return True, msg
            else:
                msg = f"No se encontró un proceso de audio activo para '{app_name}'."
                print(f"[AudioMixer] {msg}")
                return False, msg

        except Exception as e:
            err = f"Error al modificar volumen de {app_name}: {e}"
            print(f"[AudioMixer Error] {err}")
            return False, err

    def mute_app(self, app_name: str, mute: bool = True) -> Tuple[bool, str]:
        """Silencia o reactiva el audio de una aplicación específica."""
        if not self.available:
            return False, "Control de audio no disponible."

        self._ensure_com_init()
        target = app_name.lower().strip()
        found = False
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if not session.Process:
                    continue
                p_name = session.Process.name().lower()
                if target in p_name:
                    volume = session.SimpleAudioVolume
                    volume.SetMute(1 if mute else 0, None)
                    found = True

            action_str = "silenciado" if mute else "reactivado"
            if found:
                msg = f"Audio de '{app_name}' {action_str}."
                print(f"[AudioMixer] {msg}")
                return True, msg
            return False, f"No se encontró la aplicación '{app_name}' para silenciar."
        except Exception as e:
            return False, f"Error al silenciar {app_name}: {e}"

    def set_master_volume(self, volume_pct: float) -> Tuple[bool, str]:
        """Ajusta el volumen maestro general de Windows al porcentaje solicitado (0-100%)."""
        if not self.available:
            return False, "Control de audio no disponible."

        self._ensure_com_init()
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            if hasattr(devices, "EndpointVolume"):
                volume = devices.EndpointVolume
            elif hasattr(devices, "_dev"):
                interface = devices._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
            else:
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)

            vol_scalar = max(0.0, min(1.0, volume_pct / 100.0))
            volume.SetMasterVolumeLevelScalar(vol_scalar, None)
            msg = f"Volumen maestro de Windows ajustado al {int(volume_pct)}%."
            print(f"[AudioMixer] {msg}")
            return True, msg
        except Exception as e:
            return False, f"Error al cambiar volumen maestro: {e}"


# Instancia global compartida
audio_mixer = AudioMixerController()
