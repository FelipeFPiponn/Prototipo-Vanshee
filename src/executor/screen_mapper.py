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

class ScreenMapper:
    def __init__(self):
        if pyautogui:
            pyautogui.FAILSAFE = False

    def capture(self):
        """Captura la pantalla completa en tiempo real."""
        if ImageGrab is None:
            print("[ScreenMapper Warning] Pillow no está instalado; se omite captura de pantalla.")
            return None
        try:
            return ImageGrab.grab()
        except Exception as e:
            print(f"[ScreenMapper Error] Falló captura de pantalla: {e}")
            return None

    def get_active_window_title(self) -> str:
        """Obtiene el título de la ventana activa en Windows OS."""
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

    def map_screen_context(self, action_hint: str = "") -> dict:
        """Escanea el panorama de la pantalla y el contexto de la aplicación activa."""
        img = self.capture()
        win_title = self.get_active_window_title().lower()
        action_text = action_hint.lower()

        app_name = "desktop"
        if "spotify" in win_title or "spotify" in action_text:
            app_name = "spotify"
        elif "youtube" in win_title or "youtube" in action_text:
            app_name = "youtube"
        elif "steam" in win_title or "steam" in action_text:
            app_name = "steam"
        elif "visual studio code" in win_title or " - code" in win_title or "vscode" in action_text:
            app_name = "vscode"
        elif any(browser in win_title for browser in ["chrome", "edge", "brave", "firefox"]):
            app_name = "browser"
        elif "word" in win_title:
            app_name = "word"

        context = {
            "app_name": app_name,
            "window_title": win_title,
            "is_youtube": "youtube" in win_title or "brave" in win_title or "chrome" in win_title,
            "is_code": "code" in win_title or "visual studio" in win_title,
            "is_steam": "steam" in win_title,
            "screen_size": img.size if img else (0, 0),
            "confidence": 0.85 if win_title else 0.35,
        }

        print(f"[ScreenMapper Mapeo de Pantalla]: Ventana activa = '{win_title}' | Dimension = {context['screen_size']}")
        return context

    def trigger_play_content(self):
        """Simula la acción de reproducir el contenido o vídeo en pantalla por obviedad."""
        if pyautogui is None:
            print("[ScreenMapper Warning] PyAutoGUI no está instalado; no se puede enviar tecla de reproducción.")
            return
        print("[ScreenMapper Ejecutando accion de reproduccion automatica...]")
        # Dar foco a la ventana y presionar 'k' / 'space' (estándar de YouTube y reproductores)
        pyautogui.press('k')

    def trigger_volume_up(self):
        """Aumenta el volumen general del sistema."""
        if pyautogui is None:
            print("[ScreenMapper Warning] PyAutoGUI no está instalado; no se puede subir volumen.")
            return
        pyautogui.press('volumeup')

    def trigger_volume_down(self):
        """Disminuye el volumen general del sistema."""
        if pyautogui is None:
            print("[ScreenMapper Warning] PyAutoGUI no está instalado; no se puede bajar volumen.")
            return
        pyautogui.press('volumedown')
