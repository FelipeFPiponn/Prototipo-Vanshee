import ctypes

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None


def _get_fast_screen_size() -> tuple[int, int]:
    """Obtiene la resolución de pantalla en ~0.001ms vía Win32 API sin capturar píxeles."""
    try:
        user32 = ctypes.windll.user32
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    except Exception:
        return (1920, 1080)


class ScreenMapper:
    def __init__(self):
        if pyautogui:
            pyautogui.FAILSAFE = False
        self._cached_screen_size: tuple[int, int] = _get_fast_screen_size()

    def capture(self):
        """Captura la pantalla completa en tiempo real (solo bajo demanda explícita)."""
        if ImageGrab is None:
            print("[ScreenMapper Warning] Pillow no está instalado; se omite captura de pantalla.")
            return None
        try:
            return ImageGrab.grab()
        except Exception as e:
            print(f"[ScreenMapper Error] Falló captura de pantalla: {e}")
            return None

    def get_active_window_title(self) -> str:
        """Obtiene el título de la ventana activa en Windows OS en <0.1ms."""
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd).strip()
                if title:
                    return title
        except Exception:
            pass

        if gw is not None:
            try:
                active_win = gw.getActiveWindow()
                return active_win.title if active_win else ""
            except Exception:
                pass
        return ""

    def map_screen_context(self, action_hint: str = "", capture_image: bool = False) -> dict:
        """Escanea la ventana activa de forma instantánea sin capturar píxeles salvo que se pida explícitamente."""
        img = self.capture() if capture_image else None
        win_title = self.get_active_window_title().lower()
        action_text = action_hint.lower()

        app_name = "desktop"
        if "spotify" in win_title or "spotify" in action_text:
            app_name = "spotify"
        elif "youtube" in win_title or "youtube" in action_text:
            app_name = "youtube"
        elif "steam" in win_title or "steam" in action_text:
            app_name = "steam"
        elif "antigravity" in win_title or "antigravity" in action_text:
            app_name = "antigravity"
        elif "visual studio code" in win_title or " - code" in win_title or "vscode" in action_text:
            app_name = "vscode"
        elif any(browser in win_title for browser in ["chrome", "edge", "brave", "firefox"]):
            app_name = "browser"
        elif "word" in win_title:
            app_name = "word"

        screen_size = img.size if img else self._cached_screen_size

        return {
            "app_name": app_name,
            "window_title": win_title,
            "is_youtube": "youtube" in win_title or "brave" in win_title or "chrome" in win_title,
            "is_code": "code" in win_title or "visual studio" in win_title or "antigravity" in win_title,
            "is_steam": "steam" in win_title,
            "screen_size": screen_size,
            "confidence": 0.85 if win_title else 0.35,
        }

    def trigger_play_content(self):
        """Simula la acción de reproducir el contenido o vídeo en pantalla por obviedad."""
        if pyautogui is None:
            print("[ScreenMapper Warning] PyAutoGUI no está instalado; no se puede enviar tecla de reproducción.")
            return
        pyautogui.press('k')

    def trigger_volume_up(self):
        """Aumenta el volumen general del sistema."""
        if pyautogui is None:
            return
        pyautogui.press('volumeup')

    def trigger_volume_down(self):
        """Disminuye el volumen general del sistema."""
        if pyautogui is None:
            return
        pyautogui.press('volumedown')
