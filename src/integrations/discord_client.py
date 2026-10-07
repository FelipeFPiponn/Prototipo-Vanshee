"""Cliente de Integración para Discord Desktop.

Permite navegar y conectarse a canales de voz usando Quick Switcher con filtrado exclusivo (!canal),
desconectarse con precisión mediante el botón de desconexión del panel de voz, y gestionar
mute/ensordecer de Discord al instante.
"""

import os
import re
import time
from typing import Tuple, Optional

import pyautogui

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import win32gui
except ImportError:
    win32gui = None

from src.executor.window_manager import WindowManager


class DiscordClient:
    """Gestiona la interacción y conexión a canales de voz en Discord."""

    def __init__(self, window_manager: Optional[WindowManager] = None):
        self.window_manager = window_manager or WindowManager()

    def is_running(self) -> bool:
        """Comprueba si Discord está abierto."""
        win = self.window_manager.find_window("discord")
        return win is not None

    def connect_voice_channel(self, channel_name: str = "general") -> Tuple[bool, str]:
        """Se conecta a un canal de voz de Discord usando el Quick Switcher con prefijo '!' para filtrar canales de voz."""
        clean_name = (channel_name or "general").strip()
        clean_name = re.sub(r"^(?:en|de|al|a|el|la|los|las|un|una|canal|canal de voz|sala|servidor)\s+", "", clean_name, flags=re.IGNORECASE).strip()
        clean_name = re.sub(r"\s+(?:en|de)\s+discord$", "", clean_name, flags=re.IGNORECASE).strip()
        if not clean_name or clean_name.lower() in ["discord", "voz", "en discord", "canal de voz", "un canal de voz", "el canal de voz"]:
            clean_name = "general"

        win = self.window_manager.find_window("discord")
        if not win:
            try:
                os.startfile("discord://")
                time.sleep(1.2)
                win = self.window_manager.find_window("discord")
            except Exception:
                pass

        if not win:
            return False, "Discord no está abierto ni instalado en el equipo."

        try:
            # 1. Traer Discord al frente
            self.window_manager.focus_window(win["hwnd"])
            time.sleep(0.2)

            # 2. Abrir Quick Switcher (Ctrl + K)
            pyautogui.hotkey("ctrl", "k")
            time.sleep(0.2)

            # 3. Filtrar exclusivamente por canales de voz con el prefijo '!' en Discord Quick Switcher
            search_query = f"!{clean_name}"
            if pyperclip:
                pyperclip.copy(search_query)
                pyautogui.hotkey("ctrl", "v")
            else:
                pyautogui.typewrite(search_query, interval=0.02)
            time.sleep(0.35)

            # 4. Confirmar con Enter para unirse directamente al canal de voz filtrado
            pyautogui.press("enter")
            time.sleep(0.15)

            msg = f"Conectando al canal de voz '{clean_name.title()}' en Discord."
            print(f"[DiscordClient] {msg}")
            return True, msg

        except Exception as e:
            return False, f"Error al conectar con canal de voz en Discord: {e}"

    def disconnect_voice(self) -> Tuple[bool, str]:
        """Se desconecta del canal de voz activo en Discord haciendo clic en el botón de desconexión."""
        win = self.window_manager.find_window("discord")
        if not win:
            return False, "Discord no está abierto."

        try:
            # 1. Enfocar Discord
            self.window_manager.focus_window(win["hwnd"])
            time.sleep(0.2)

            hwnd = win["hwnd"]
            rect = win["rect"]
            if win32gui:
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                except Exception:
                    pass

            left, top, right, bottom = rect

            # 2. En Discord, el botón 'Desconectar' (ícono de teléfono colgar con X) se ubica
            # en la esquina superior derecha del panel 'Voz Conectada' / 'RTC Conectado',
            # directamente arriba del panel de usuario en la barra lateral izquierda.
            # Coordenadas relativas calibradas: x = left + 285, y = bottom - 82
            click_x = left + 285
            click_y = bottom - 82

            orig_pos = pyautogui.position()
            pyautogui.click(click_x, click_y)
            time.sleep(0.05)
            # Restaurar la posición del cursor del usuario
            pyautogui.moveTo(orig_pos.x, orig_pos.y)

            msg = "Desconectado del canal de voz en Discord."
            print(f"[DiscordClient] {msg}")
            return True, msg
        except Exception as e:
            return False, f"Error al desconectar de Discord: {e}"

    def toggle_mute(self) -> Tuple[bool, str]:
        """Alterna el micrófono (Mute/Unmute) en Discord (Ctrl + Shift + M)."""
        win = self.window_manager.find_window("discord")
        if not win:
            return False, "Discord no está abierto."

        try:
            self.window_manager.focus_window(win["hwnd"])
            time.sleep(0.15)
            pyautogui.hotkey("ctrl", "shift", "m")
            return True, "Micrófono alternado en Discord."
        except Exception as e:
            return False, f"Error al alternar micrófono en Discord: {e}"

    def toggle_deafen(self) -> Tuple[bool, str]:
        """Alterna ensordecer/desensordecer en Discord (Ctrl + Shift + D)."""
        win = self.window_manager.find_window("discord")
        if not win:
            return False, "Discord no está abierto."

        try:
            self.window_manager.focus_window(win["hwnd"])
            time.sleep(0.15)
            pyautogui.hotkey("ctrl", "shift", "d")
            return True, "Ensordecer alternado en Discord."
        except Exception as e:
            return False, f"Error al alternar ensordecer en Discord: {e}"


# Instancia global compartida
discord_client = DiscordClient()
