import time
import ctypes
from typing import Optional

try:
    import win32gui
    import win32con
    import win32process
    import win32api
    import win32service
except ImportError:
    win32gui = None
    win32con = None
    win32process = None
    win32api = None
    win32service = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pyautogui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None


class WindowManager:
    """Gestiona la detección, priorización, enfoque y navegación de ventanas y pestañas en Windows OS."""

    TARGET_ALIASES = {
        "spotify": {"keywords": ["spotify"], "processes": ["spotify.exe", "spotify"]},
        "youtube": {"keywords": ["youtube"], "processes": []},
        "antigravity": {"keywords": ["antigravity", "vanshee"], "processes": ["antigravity.exe"]},
        "cursor": {"keywords": ["cursor"], "processes": ["cursor.exe"]},
        "claude": {"keywords": ["claude"], "processes": ["claude.exe"]},
        "codex": {"keywords": ["codex", "visual studio code", " - code"], "processes": ["code.exe"]},
        "opencode": {"keywords": ["opencode", "code"], "processes": []},
        "windsurf": {"keywords": ["windsurf"], "processes": ["windsurf.exe"]},
        "chatgpt": {"keywords": ["chatgpt"], "processes": ["chatgpt.exe"]},
        "vscode": {"keywords": ["visual studio code", " - code"], "processes": ["code.exe", "code"]},
        "vs code": {"keywords": ["visual studio code", " - code"], "processes": ["code.exe", "code"]},
        "code": {"keywords": ["visual studio code", " - code"], "processes": ["code.exe", "code"]},
        "visual studio code": {"keywords": ["visual studio code", " - code"], "processes": ["code.exe", "code"]},
        "steam": {"keywords": ["steam"], "processes": ["steam.exe", "steam"]},
        "discord": {"keywords": ["discord"], "processes": ["discord.exe", "discord"]},
        "brave": {"keywords": ["brave"], "processes": ["brave.exe", "brave"]},
        "chrome": {"keywords": ["chrome", "google chrome"], "processes": ["chrome.exe", "chrome"]},
        "edge": {"keywords": ["edge", "microsoft edge"], "processes": ["msedge.exe", "msedge"]},
        "firefox": {"keywords": ["firefox", "mozilla firefox"], "processes": ["firefox.exe", "firefox"]},
        "notepad": {"keywords": ["bloc de notas", "notepad"], "processes": ["notepad.exe"]},
        "terminal": {"keywords": ["windows terminal", "powershell", "símbolo del sistema", "cmd.exe"], "processes": ["windowsterminal.exe", "cmd.exe", "powershell.exe"]},
    }

    def __init__(self):
        self.ensure_desktop()

    def ensure_desktop(self):
        """Garantiza la vinculación a la estación de ventana interactiva WinSta0\\Default."""
        if win32service:
            try:
                hwinsta = win32service.OpenWindowStation("WinSta0", False, 0x037F)
                hwinsta.SetProcessWindowStation()
                hdesk = win32service.OpenDesktop("Default", 0, False, 0x01FF)
                hdesk.SetThreadDesktop()
            except Exception:
                pass

    def get_open_windows(self) -> list[dict]:
        """Obtiene la lista de todas las ventanas visibles con título en el escritorio actual."""
        self.ensure_desktop()
        windows = []

        if win32gui is not None:
            def enum_cb(hwnd, extra):
                try:
                    if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                        return
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if width <= 0 or height <= 0:
                        return
                    title = win32gui.GetWindowText(hwnd).strip()
                    if not title:
                        return
                    pid = 0
                    if win32process:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "pid": pid,
                        "rect": rect
                    })
                except Exception:
                    pass

            for attempt in range(2):
                try:
                    win32gui.EnumWindows(enum_cb, None)
                    if windows:
                        return windows
                    break
                except Exception as e:
                    if attempt == 0:
                        time.sleep(0.05)
                        continue
                    # Si falla en el segundo intento, continúa silenciosamente al fallback pygetwindow
                    break

        # Fallback a pygetwindow si win32gui no retornó ventanas
        if gw is not None:
            try:
                for w in gw.getAllWindows():
                    if w.title.strip() and w.visible and w.width > 0 and w.height > 0:
                        windows.append({
                            "hwnd": getattr(w, "_hWnd", 0),
                            "title": w.title.strip(),
                            "pid": 0,
                            "rect": (w.left, w.top, w.right, w.bottom)
                        })
            except Exception as e:
                print(f"[WindowManager Warning] pygetwindow.getAllWindows falló: {e}")

        return windows

    def find_window(self, target: str, additional_keywords: list[str] = None) -> Optional[dict]:
        """Busca una ventana abierta por nombre de target, alias o palabras clave."""
        clean_target = target.lower().strip()
        keywords = set(additional_keywords or [])
        keywords.add(clean_target)

        # Añadir palabras clave de alias conocidos
        if clean_target in self.TARGET_ALIASES:
            keywords.update(self.TARGET_ALIASES[clean_target]["keywords"])
        else:
            for alias_key, alias_val in self.TARGET_ALIASES.items():
                if alias_key in clean_target or clean_target in alias_key:
                    keywords.update(alias_val["keywords"])

        windows = self.get_open_windows()

        # 1. Búsqueda exacta / prioritaria: título contiene cualquiera de las keywords
        for w in windows:
            title_lower = w["title"].lower()
            for kw in keywords:
                if kw in title_lower:
                    return w

        return None

    def find_browser_window(self) -> Optional[dict]:
        """Encuentra cualquier ventana abierta de navegador (Brave, Chrome, Edge, Firefox)."""
        windows = self.get_open_windows()
        browser_names = ["brave", "chrome", "edge", "firefox"]
        for w in windows:
            title_lower = w["title"].lower()
            if any(b in title_lower for b in browser_names):
                return w
        return None

    def focus_window(self, hwnd: int) -> bool:
        """Trae una ventana al frente de forma limpia, superando las restricciones de foco de Windows."""
        if not hwnd or win32gui is None:
            return False

        try:
            self.ensure_desktop()
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Restaurar si está minimizada
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # Enlazar hilos para permitir cambio de foco legítimo
            current_thread_id = kernel32.GetCurrentThreadId()
            target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
            if current_thread_id != target_thread_id:
                user32.AttachThreadInput(current_thread_id, target_thread_id, True)

            # Simular pulso de tecla Alt para desbloquear SetForegroundWindow
            user32.keybd_event(0x12, 0, 0, 0)
            win32gui.SetForegroundWindow(hwnd)
            user32.keybd_event(0x12, 0, 2, 0)
            win32gui.BringWindowToTop(hwnd)

            if current_thread_id != target_thread_id:
                user32.AttachThreadInput(current_thread_id, target_thread_id, False)

            time.sleep(0.1)
            return True
        except Exception as e:
            print(f"[WindowManager Error] No se pudo enfocar la ventana hwnd={hwnd}: {e}")
            return False

    def find_and_focus(self, target: str, additional_keywords: list[str] = None) -> tuple[bool, str]:
        """Busca una ventana por target y la enfoca en primer plano."""
        win = self.find_window(target, additional_keywords=additional_keywords)
        if win and self.focus_window(win["hwnd"]):
            return True, win["title"]
        return False, ""

    def navigate_active_browser_tab(self, url: str) -> bool:
        """Reutiliza la pestaña activa del navegador enfocando la barra de direcciones y cargando la URL."""
        if pyautogui is None:
            print("[WindowManager Warning] PyAutoGUI no disponible para navegar pestaña.")
            return False

        try:
            # Copiar URL al portapapeles
            if pyperclip:
                pyperclip.copy(url)
            else:
                import subprocess
                subprocess.run(["clip"], input=url.encode("utf-8"), check=True)

            # Ctrl + L para seleccionar la barra de navegación del navegador
            pyautogui.hotkey("ctrl", "l")
            time.sleep(0.08)
            # Pegar URL y dar Enter
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.05)
            pyautogui.press("enter")
            return True
        except Exception as e:
            print(f"[WindowManager Error] Falló al navegar en pestaña activa: {e}")
            return False

    def type_and_send_prompt(self, text: str, target_hint: str = "", press_enter: bool = True) -> bool:
        """Escribe un prompt en el agente de código o chat activo y opcionalmente pulsa Enter."""
        if not text:
            return False
        clean_text = text.strip()

        # 1. Si hay un target_hint específico de app/agente, enfocar la ventana correspondiente
        target_clean = target_hint.lower().strip()
        coding_agents = ["antigravity", "cursor", "claude", "vscode", "vs code", "code", "codex", "opencode", "windsurf", "chatgpt"]
        
        target_to_focus = None
        if target_clean in coding_agents:
            target_to_focus = target_clean
        else:
            for agent in coding_agents:
                if agent in target_clean:
                    target_to_focus = agent
                    break

        if target_to_focus:
            focused, title = self.find_and_focus(target_to_focus)
            if focused:
                print(f"[WindowManager] Ventana de agente enfocada: '{title}'")
                time.sleep(0.18)

        # 2. Obtener contexto de la ventana activa para saber si es un IDE con chat
        active_title = ""
        if win32gui:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    active_title = win32gui.GetWindowText(hwnd).lower()
            except Exception:
                pass

        is_ide_agent = any(k in active_title or k in target_clean for k in ["antigravity", "cursor", "code", "visual studio", "windsurf", "opencode"])

        if pyautogui is not None:
            # 3. Si es un IDE/agente de código (Antigravity, Cursor, VS Code, etc.),
            # enviar Ctrl+L para situar el foco en el panel/caja de prompt del agente
            if is_ide_agent:
                print("[WindowManager] Enviando Ctrl+L para enfocar la caja de prompt del agente...")
                pyautogui.hotkey("ctrl", "l")
                time.sleep(0.15)

            # 4. Copiar texto al portapapeles y pegar con Ctrl+V (soporta acentos, código y saltos de línea)
            if pyperclip:
                pyperclip.copy(clean_text)
            else:
                import subprocess
                subprocess.run(["clip"], input=clean_text.encode("utf-8"), check=True)

            time.sleep(0.08)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.12)

            # 5. Presionar Enter para enviar el prompt si se solicita
            if press_enter:
                print("[WindowManager] Enviando tecla Enter para enviar el prompt...")
                pyautogui.press("enter")

            return True
        return False
