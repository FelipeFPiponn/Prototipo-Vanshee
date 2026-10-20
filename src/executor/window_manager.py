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
        "antigravity": {
            "keywords": ["antigravity", "antigravity ide", "google antigravity"],
            "processes": ["antigravity ide.exe", "antigravity.exe", "google antigravity.exe"]
        },
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
        "opera": {"keywords": ["opera", "opera gx", "operagx"], "processes": ["opera.exe", "opera_gx.exe"]},
        "opera gx": {"keywords": ["opera gx", "opera", "operagx"], "processes": ["opera.exe", "opera_gx.exe"]},
        "operagx": {"keywords": ["opera gx", "opera", "operagx"], "processes": ["opera.exe", "opera_gx.exe"]},
        "calculadora": {"keywords": ["calculadora", "calculator", "calc"], "processes": ["calculatorapp.exe", "calc.exe"]},
        "calc": {"keywords": ["calculadora", "calculator", "calc"], "processes": ["calculatorapp.exe", "calc.exe"]},
        "administrador de tareas": {"keywords": ["administrador de tareas", "task manager", "taskmgr"], "processes": ["taskmgr.exe"]},
        "taskmgr": {"keywords": ["administrador de tareas", "task manager", "taskmgr"], "processes": ["taskmgr.exe"]},
        "explorador": {"keywords": ["explorador de archivos", "file explorer", "explorer"], "processes": ["explorer.exe"]},
        "explorer": {"keywords": ["explorador de archivos", "file explorer", "explorer"], "processes": ["explorer.exe"]},
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
        if not windows and gw is not None:
            try:
                for w in gw.getAllWindows():
                    if w.title.strip() and w.visible and w.width > 0 and w.height > 0:
                        h = getattr(w, "_hWnd", 0)
                        pid = 0
                        if win32process and h:
                            try:
                                _, pid = win32process.GetWindowThreadProcessId(h)
                            except Exception:
                                pass
                        windows.append({
                            "hwnd": h,
                            "title": w.title.strip(),
                            "pid": pid,
                            "rect": (w.left, w.top, w.right, w.bottom)
                        })
            except Exception as e:
                print(f"[WindowManager Warning] pygetwindow.getAllWindows falló: {e}")

        # Fallback final directo vía ctypes si los métodos anteriores no retornaron
        if not windows:
            try:
                EnumWindows = ctypes.windll.user32.EnumWindows
                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                IsWindowVisible = ctypes.windll.user32.IsWindowVisible
                GetWindowTextLengthW = ctypes.windll.user32.GetWindowTextLengthW
                GetWindowTextW = ctypes.windll.user32.GetWindowTextW

                def _c_cb(hwnd, lParam):
                    if IsWindowVisible(hwnd):
                        length = GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value.strip()
                            if title:
                                pid = 0
                                if win32process:
                                    try:
                                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                                    except Exception:
                                        pass
                                windows.append({
                                    "hwnd": hwnd,
                                    "title": title,
                                    "pid": pid,
                                    "rect": (0, 0, 0, 0)
                                })
                    return True

                EnumWindows(EnumWindowsProc(_c_cb), 0)
            except Exception:
                pass

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

        # 1. Búsqueda exacta / prioritaria: título contiene cualquiera de las keywords (excluyendo ventanas de Vanshee)
        for w in windows:
            if self._is_self_window(w["title"], w.get("pid", 0)):
                continue
            title_lower = w["title"].lower()
            for kw in keywords:
                if kw in title_lower:
                    return w

        # 2. Búsqueda por proceso en ejecución asociado al alias (ej. 'Antigravity IDE.exe')
        target_procs = set()
        if clean_target in self.TARGET_ALIASES:
            target_procs.update(self.TARGET_ALIASES[clean_target].get("processes", []))
        else:
            for alias_key, alias_val in self.TARGET_ALIASES.items():
                if alias_key in clean_target or clean_target in alias_key:
                    target_procs.update(alias_val.get("processes", []))

        if target_procs:
            try:
                import psutil
                for w in windows:
                    if self._is_self_window(w["title"], w.get("pid", 0)):
                        continue
                    if w.get("pid"):
                        try:
                            p_name = psutil.Process(w["pid"]).name().lower()
                            if any(tp.lower() == p_name or tp.lower() in p_name for tp in target_procs):
                                return w
                        except Exception:
                            pass
            except Exception:
                pass

        return None

    def _is_self_window(self, title: str, pid: int = 0) -> bool:
        """Determina si una ventana pertenece al propio asistente Vanshee para evitar auto-enfoque."""
        try:
            import os
            if pid and pid == os.getpid():
                return True
        except Exception:
            pass
        t = title.lower().strip()
        # Si contiene el nombre de un editor o aplicación externa conocida, nunca es la ventana propia de Vanshee
        if any(app in t for app in ["antigravity", "cursor", "visual studio", "vscode", "windsurf", "chrome", "brave", "firefox", "edge", "spotify", "discord"]):
            return False
        if t in ["vanshee", "vanshee chat", "vanshee bubble", "vanshee launcher", "vanshee core"]:
            return True
        if "vanshee chat" in t or "vanshee launcher" in t or "vanshee bubble" in t:
            return True
        if t.startswith("vanshee ") or t.startswith("vanshee -"):
            return True
        return False

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
        coding_agents = [
            "antigravity", "anti gravity", "anti-gravity", "agent", "el agente", 
            "cursor", "claude", "vscode", "vs code", "code", "codex", "opencode", 
            "windsurf", "chatgpt", "editor", "el editor", "editor de codigo", 
            "editor de código", "agente de codigo", "agente de código", "ide"
        ]
        
        target_to_focus = None
        if target_clean in coding_agents:
            target_to_focus = target_clean
        else:
            for agent in coding_agents:
                if agent in target_clean:
                    target_to_focus = agent
                    break

        if target_to_focus in [
            "agent", "el agente", "anti gravity", "anti-gravity", "agente", 
            "agente de codigo", "agente de código", "editor", "el editor", 
            "editor de codigo", "editor de código", "ide"
        ]:
            target_to_focus = "antigravity"

        if target_to_focus:
            focused, title = self.find_and_focus(target_to_focus)
            if focused:
                print(f"[WindowManager] Ventana de agente enfocada: '{title}'")
                time.sleep(0.3)

        # 2. Obtener contexto de la ventana activa para saber si es un IDE con chat
        active_title = ""
        if win32gui:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    active_title = win32gui.GetWindowText(hwnd).lower()
            except Exception:
                pass

        is_ide_agent = any(k in active_title or k in target_clean for k in [
            "antigravity", "anti gravity", "agent", "agente", "cursor", "code", 
            "visual studio", "windsurf", "opencode", "claude", "editor"
        ])

        if pyautogui is not None:
            # 3. Si es un IDE/agente de código (Antigravity, Cursor, VS Code, etc.):
            # Situar el foco en el panel de AGENTE (no como mensaje de chat aislado)
            if is_ide_agent:
                if "cursor" in active_title or "cursor" in target_clean:
                    # En Cursor: Ctrl+I enfoca Composer en modo Agente
                    print("[WindowManager] Enfocando Composer Agent de Cursor (Ctrl+I)...")
                    pyautogui.hotkey("ctrl", "i")
                    time.sleep(0.3)
                else:
                    # En Antigravity IDE y VS Code:
                    # Ctrl+Alt+I abre directamente la sesión del Agente / Copilot Edits.
                    # Luego Ctrl+L asegura el foco en la caja de prompt del panel.
                    print("[WindowManager] Enfocando panel del Agente (Ctrl+Alt+I)...")
                    pyautogui.hotkey("ctrl", "alt", "i")
                    time.sleep(0.2)
                    pyautogui.hotkey("ctrl", "l")
                    time.sleep(0.2)

            # 4. Copiar texto al portapapeles y pegar con Ctrl+V (soporta acentos, código y saltos de línea)
            if pyperclip:
                pyperclip.copy(clean_text)
            else:
                import subprocess
                subprocess.run(["clip"], input=clean_text.encode("utf-8"), check=True)

            time.sleep(0.12)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.2)

            # 5. Presionar Enter para enviar el prompt directamente al agente (evitar que quede como mensaje/borrador)
            if press_enter:
                print("[WindowManager] Presionando tecla Enter para enviar el prompt directamente al agente...")
                pyautogui.press("enter")
                time.sleep(0.1)

            return True
        return False

    def get_window_work_area(self, hwnd: int = 0) -> tuple[int, int, int, int]:
        """Obtiene el área de trabajo disponible (restando la barra de tareas) para el monitor de la ventana."""
        if win32api and win32con and hwnd:
            try:
                hmon = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
                mon_info = win32api.GetMonitorInfo(hmon)
                work = mon_info.get("Work")
                if work:
                    wx, wy, wr, wb = work
                    return wx, wy, wr - wx, wb - wy
            except Exception:
                pass

        # Fallback SPI_GETWORKAREA del monitor principal
        try:
            from ctypes import wintypes
            rect = wintypes.RECT()
            # SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        except Exception:
            pass

        # Fallback básico con pyautogui o 1080p
        if pyautogui:
            sw, sh = pyautogui.size()
            return 0, 0, sw, max(sh - 40, 100)
        return 0, 0, 1920, 1040

    def _normalize_position(self, pos: str) -> str:
        """Normaliza términos en lenguaje natural a identificadores de posición estándar."""
        import re
        clean = (pos or "").lower().strip()
        # Verificar términos de pantalla completa / fullscreen / maximizar antes de remover 'pantalla'
        if any(w in clean for w in ["pantalla completa", "a pantalla completa", "en pantalla completa", "toda la pantalla", "pantalla entera", "fullscreen", "full screen", "maxim", "max"]):
            return "maximize"
        if any(w in clean for w in ["close", "cierra", "cerrar", "termina"]):
            return "close"
        if any(w in clean for w in ["minim", "ocult", "min"]):
            return "minimize"

        clean = re.sub(r"\b(de\s+(?:mi\s+|la\s+)?pantalla|en\s+(?:la\s+)?pantalla|lado|mitad|parte|cuadrante|esquina)\b", "", clean).strip()
        
        if any(w in clean for w in ["arriba a la izquierda", "superior izquierda", "top left", "top_left", "arriba izquierda"]):
            return "top_left"
        if any(w in clean for w in ["arriba a la derecha", "superior derecha", "top right", "top_right", "arriba derecha"]):
            return "top_right"
        if any(w in clean for w in ["abajo a la izquierda", "inferior izquierda", "bottom left", "bottom_left", "abajo izquierda"]):
            return "bottom_left"
        if any(w in clean for w in ["abajo a la derecha", "inferior derecha", "bottom right", "bottom_right", "abajo derecha"]):
            return "bottom_right"
        if any(w in clean for w in ["izq", "izquierda", "left"]):
            return "left"
        if any(w in clean for w in ["der", "derecha", "right"]):
            return "right"
        if any(w in clean for w in ["arriba", "superior", "top"]):
            return "top"
        if any(w in clean for w in ["abajo", "inferior", "bottom"]):
            return "bottom"
        if any(w in clean for w in ["completa", "fullscreen", "max"]):
            return "maximize"
        if any(w in clean for w in ["centr", "center", "medio"]):
            return "center"
        if any(w in clean for w in ["restaur", "restore", "normal"]):
            return "restore"
        return ""

    def _position_label(self, pos: str) -> str:
        """Retorna etiqueta descriptiva en español para una posición."""
        labels = {
            "left": "la mitad izquierda",
            "right": "la mitad derecha",
            "top": "la mitad superior",
            "bottom": "la mitad inferior",
            "top_left": "el cuadrante superior izquierdo",
            "top_right": "el cuadrante superior derecho",
            "bottom_left": "el cuadrante inferior izquierdo",
            "bottom_right": "el cuadrante inferior derecho",
            "center": "el centro de la pantalla",
            "maximize": "pantalla completa",
            "minimize": "modo minimizado",
            "close": "cerrada",
            "restore": "tamaño normal",
        }
        return labels.get(pos, pos)

    def set_window_position(self, hwnd: int, position: str) -> bool:
        """Posiciona y redimensiona la ventana en la pantalla (izquierda, derecha, cuadrantes, maximizar, etc.)."""
        if not hwnd:
            return False
        norm_pos = self._normalize_position(position)
        if not norm_pos:
            return False

        if norm_pos == "close":
            return self.close_window(hwnd)

        self.focus_window(hwnd)
        time.sleep(0.06)

        if norm_pos == "maximize":
            # 1. Intentar con win32gui (Restaurar primero para romper restricciones de SetWindowPos si existían)
            if win32gui and win32con:
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.04)
                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                    if win32gui.IsZoomed(hwnd):
                        return True
                except Exception as e:
                    print(f"[WindowManager Warning] Error maximizando con win32: {e}")

            # 2. Fallback con hotkey nativo de Windows (Win + Up)
            if pyautogui:
                try:
                    pyautogui.hotkey("win", "up")
                    time.sleep(0.05)
                    if win32gui and win32gui.IsZoomed(hwnd):
                        return True
                except Exception:
                    pass

            # 3. Fallback directo redimensionando al área total de trabajo del monitor
            if win32gui and win32con:
                try:
                    wx, wy, ww, wh = self.get_window_work_area(hwnd)
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, int(wx), int(wy), int(ww), int(wh), 0x0004 | 0x0040)
                    return True
                except Exception:
                    pass

            return True

        if norm_pos == "minimize":
            if win32gui and win32con:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                return True
            elif pyautogui:
                pyautogui.hotkey("win", "down")
                return True

        # Posicionamiento por cálculo de coordenadas en área de trabajo
        if win32gui and win32con:
            try:
                # Restaurar si estaba maximizada para que el redimensionado sea efectivo
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.06)
                wx, wy, ww, wh = self.get_window_work_area(hwnd)

                if norm_pos == "left":
                    x, y, w, h = wx, wy, ww // 2, wh
                elif norm_pos == "right":
                    x, y, w, h = wx + (ww // 2), wy, ww - (ww // 2), wh
                elif norm_pos == "top":
                    x, y, w, h = wx, wy, ww, wh // 2
                elif norm_pos == "bottom":
                    x, y, w, h = wx, wy + (wh // 2), ww, wh - (wh // 2)
                elif norm_pos == "top_left":
                    x, y, w, h = wx, wy, ww // 2, wh // 2
                elif norm_pos == "top_right":
                    x, y, w, h = wx + (ww // 2), wy, ww - (ww // 2), wh // 2
                elif norm_pos == "bottom_left":
                    x, y, w, h = wx, wy + (wh // 2), ww // 2, wh - (wh // 2)
                elif norm_pos == "bottom_right":
                    x, y, w, h = wx + (ww // 2), wy + (wh // 2), ww - (ww // 2), wh - (wh // 2)
                elif norm_pos == "center":
                    w, h = int(ww * 0.75), int(wh * 0.8)
                    x, y = wx + (ww - w) // 2, wy + (wh - h) // 2
                elif norm_pos == "restore":
                    w, h = int(ww * 0.65), int(wh * 0.7)
                    x, y = wx + (ww - w) // 2, wy + (wh - h) // 2
                else:
                    return False

                # SWP_NOZORDER = 0x0004, SWP_SHOWWINDOW = 0x0040
                ctypes.windll.user32.SetWindowPos(hwnd, 0, int(x), int(y), int(w), int(h), 0x0004 | 0x0040)
                return True
            except Exception as e:
                print(f"[WindowManager Error] No se pudo posicionar ventana hwnd={hwnd}: {e}")

        # Fallback con teclas Snap nativas de Windows
        if pyautogui:
            if norm_pos == "left":
                pyautogui.hotkey("win", "left")
                return True
            elif norm_pos == "right":
                pyautogui.hotkey("win", "right")
                return True
            elif norm_pos == "maximize":
                pyautogui.hotkey("win", "up")
                return True
            elif norm_pos == "minimize":
                pyautogui.hotkey("win", "down")
                return True

        return False

    def snap_window(self, target: str = "", position: str = "") -> tuple[bool, str]:
        """Busca una ventana o toma la activa y la ajusta en la posición indicada."""
        target_clean = (target or "").lower().strip()
        pos_from_target = self._normalize_position(target_clean)

        if not position and pos_from_target:
            norm_pos = pos_from_target
            target_clean = ""
        elif target_clean in [
            "left", "right", "top", "bottom", "center", "maximize", "minimize", "restore", 
            "top_left", "top_right", "bottom_left", "bottom_right", "izquierda", "derecha", 
            "arriba", "abajo", "pantalla completa", "a pantalla completa", "en pantalla completa", 
            "fullscreen", "completa", "toda la pantalla"
        ]:
            norm_pos = self._normalize_position(target_clean)
            target_clean = ""
        else:
            norm_pos = self._normalize_position(position)

        hwnd = 0
        win_title = ""

        # 1. Ventana activa / actual
        if not target_clean or target_clean in ["active", "activa", "actual", "esta", "esta ventana", "ventana actual", "pantalla", "ventana", "app"]:
            if win32gui:
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    if hwnd:
                        win_title = win32gui.GetWindowText(hwnd).strip()
                except Exception:
                    pass
            if not hwnd and gw:
                try:
                    act = gw.getActiveWindow()
                    if act:
                        hwnd = getattr(act, "_hWnd", 0)
                        win_title = act.title
                except Exception:
                    pass
        else:
            # 2. Buscar por nombre o alias
            win = self.find_window(target_clean)
            if not win and ("youtube" in target_clean or "navegador" in target_clean or "web" in target_clean):
                win = self.find_browser_window()

            if win:
                hwnd = win.get("hwnd", 0)
                win_title = win.get("title", target_clean)

        if not hwnd:
            return False, f"No encontré una ventana activa o abierta para '{target or 'actual'}'."

        if not norm_pos:
            norm_pos = "left"

        success = self.set_window_position(hwnd, norm_pos)
        if success:
            label = self._position_label(norm_pos)
            display_title = win_title if len(win_title) < 35 else win_title[:32] + "..."
            return True, f"Ventana '{display_title}' colocada en {label}."
        return False, f"No se pudo posicionar la ventana '{win_title}' en {norm_pos}."

    def split_screen(self, target_left: str, target_right: str) -> tuple[bool, str]:
        """Divide la pantalla colocando una aplicación a la izquierda y otra a la derecha."""
        res_left, msg_l = self.snap_window(target_left, "left")
        time.sleep(0.1)
        res_right, msg_r = self.snap_window(target_right, "right")
        if res_left and res_right:
            return True, f"Pantalla dividida: {target_left} a la izquierda y {target_right} a la derecha."
        return (res_left or res_right), f"{msg_l} | {msg_r}"

    def tile_windows(self) -> tuple[bool, str]:
        """Organiza y distribuye ordenadamente las ventanas visibles en la pantalla (split o mosaico cuadrantes)."""
        open_wins = self.get_open_windows()
        filtered = []
        for w in open_wins:
            t = w.get("title", "").strip()
            if not t or self._is_self_window(t, w.get("pid", 0)):
                continue
            t_low = t.lower()
            if any(ign in t_low for ign in ["program manager", "nvidia geforce overlay", "settings", "configuración", "windows input experience"]):
                continue
            filtered.append(w)

        if not filtered:
            return False, "No encontré ventanas abiertas para organizar."

        if len(filtered) == 1:
            hwnd = filtered[0]["hwnd"]
            self.set_window_position(hwnd, "maximize")
            return True, f"Ventana '{filtered[0]['title']}' colocada en pantalla completa."

        if len(filtered) == 2:
            self.set_window_position(filtered[0]["hwnd"], "left")
            time.sleep(0.08)
            self.set_window_position(filtered[1]["hwnd"], "right")
            return True, f"Ventanas organizadas: '{filtered[0]['title']}' a la izquierda y '{filtered[1]['title']}' a la derecha."

        if len(filtered) == 3:
            self.set_window_position(filtered[0]["hwnd"], "left")
            time.sleep(0.08)
            self.set_window_position(filtered[1]["hwnd"], "top_right")
            time.sleep(0.08)
            self.set_window_position(filtered[2]["hwnd"], "bottom_right")
            return True, f"3 ventanas organizadas en pantalla."

        quads = ["top_left", "top_right", "bottom_left", "bottom_right"]
        for i, q in enumerate(quads):
            self.set_window_position(filtered[i]["hwnd"], q)
            time.sleep(0.06)
        return True, f"{len(filtered[:4])} ventanas organizadas en cuadrantes en la pantalla."

    def handle_tab_action(self, action: str) -> tuple[bool, str]:
        """Gestiona acciones sobre pestañas de navegadores o editores (siguiente, anterior, nueva, cerrar, reabrir)."""
        if pyautogui is None:
            return False, "PyAutoGUI no está disponible para controlar pestañas."

        clean_act = action.lower().strip()
        if clean_act in ["next_tab", "siguiente_pestaña", "next", "siguiente"]:
            pyautogui.hotkey("ctrl", "tab")
            return True, "Cambiando a la pestaña siguiente."
        elif clean_act in ["prev_tab", "previous_tab", "anterior_pestaña", "prev", "anterior"]:
            pyautogui.hotkey("ctrl", "shift", "tab")
            return True, "Cambiando a la pestaña anterior."
        elif clean_act in ["new_tab", "nueva_pestaña", "new", "nueva"]:
            pyautogui.hotkey("ctrl", "t")
            return True, "Nueva pestaña abierta."
        elif clean_act in ["close_tab", "cerrar_pestaña", "close", "cerrar"]:
            pyautogui.hotkey("ctrl", "w")
            return True, "Pestaña cerrada."
        elif clean_act in ["reopen_tab", "reabrir_pestaña", "restore_tab", "reabrir"]:
            pyautogui.hotkey("ctrl", "shift", "t")
            return True, "Última pestaña cerrada recuperada."
        return False, f"Acción de pestaña no reconocida: '{action}'."

    def close_window(self, hwnd: int) -> bool:
        """Cierra limpiamente una ventana mediante mensaje nativo WM_CLOSE."""
        if not hwnd:
            return False
        try:
            if win32gui and win32con:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return True
            elif ctypes:
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
                return True
        except Exception as e:
            print(f"[WindowManager Error] Error al cerrar ventana hwnd={hwnd}: {e}")
        if pyautogui:
            try:
                self.focus_window(hwnd)
                pyautogui.hotkey("alt", "f4")
                return True
            except Exception:
                pass
        return False

    def close_active_window(self) -> tuple[bool, str]:
        """Cierra la ventana activa que se encuentra actualmente en primer plano."""
        hwnd = 0
        title = ""
        if win32gui:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    title = win32gui.GetWindowText(hwnd).strip()
            except Exception:
                pass
        if not hwnd and gw:
            try:
                act = gw.getActiveWindow()
                if act:
                    hwnd = getattr(act, "_hWnd", 0)
                    title = act.title
            except Exception:
                pass

        if not hwnd:
            if pyautogui:
                pyautogui.hotkey("alt", "f4")
                return True, "Ventana activa cerrada."
            return False, "No detecté ninguna ventana activa para cerrar."

        if self._is_self_window(title):
            return False, "No puedo cerrar la ventana principal de Vanshee mediante este comando."

        ok = self.close_window(hwnd)
        display_title = title if len(title) < 35 else title[:32] + "..."
        if ok:
            return True, f"Ventana '{display_title}' cerrada."
        return False, f"No se pudo cerrar la ventana '{display_title}'."

    def close_app(self, target: str) -> tuple[bool, str]:
        """Cierra todas las ventanas o procesos asociados a una aplicación específica (ej: 'Opera GX', 'Discord', 'Notepad')."""
        clean_target = (target or "").lower().strip()
        if not clean_target or clean_target in [
            "active", "activa", "actual", "esta", "esta ventana", "la ventana", 
            "la ventana actual", "ventana actual", "esto", "ventana"
        ]:
            return self.close_active_window()

        # Determinar procesos y palabras clave asociados al alias
        target_procs = set()
        keywords = {clean_target}
        for a_k, a_v in self.TARGET_ALIASES.items():
            if a_k in clean_target or clean_target in a_k:
                target_procs.update(a_v.get("processes", []))
                keywords.update(a_v.get("keywords", []))
            for kw in a_v.get("keywords", []):
                if kw in clean_target or clean_target in kw:
                    target_procs.update(a_v.get("processes", []))
                    keywords.update(a_v.get("keywords", []))

        # Añadir palabras individuales relevantes (ej: 'opera' desde 'opera gx')
        for word in clean_target.split():
            if len(word) >= 4:
                keywords.add(word)

        # Búsqueda dinámica en AppIndexer para asociar ejecutables de cualquier app del sistema
        try:
            from src.executor.app_indexer import AppIndexer
            app_idx = AppIndexer()
            found_path = app_idx.find_app(clean_target)
            if found_path:
                import os
                p_base = os.path.basename(found_path).lower()
                if p_base.endswith(".exe"):
                    target_procs.add(p_base)
                elif p_base.endswith(".lnk"):
                    clean_stem = p_base.replace(".lnk", "").replace("navegador", "").strip().lower()
                    target_procs.add(f"{clean_stem}.exe")
                    target_procs.add(f"{clean_stem.replace(' ', '')}.exe")
                    target_procs.add(f"{clean_stem.replace(' ', '_')}.exe")
                    keywords.add(clean_stem)
        except Exception:
            pass

        closed_count = 0
        windows = self.get_open_windows()
        for w in windows:
            if self._is_self_window(w.get("title", ""), w.get("pid", 0)):
                continue
            t_low = w.get("title", "").lower()
            matched = any(kw in t_low for kw in keywords)
            if not matched and target_procs:
                matched = any(tp.lower().replace(".exe", "") in t_low for tp in target_procs)

            if matched and w.get("hwnd"):
                if self.close_window(w["hwnd"]):
                    closed_count += 1

        # Cierre y terminación limpia de procesos residuales en segundo plano
        terminated_count = 0
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    p_name = proc.info["name"].lower()
                    if any(tp.lower() == p_name or tp.lower() in p_name for tp in target_procs) or (
                        clean_target in p_name and clean_target not in ["python", "python.exe", "code", "system", "cmd"]
                    ):
                        proc.terminate()
                        terminated_count += 1
                except Exception:
                    pass
        except Exception:
            pass

        if closed_count > 0 or terminated_count > 0:
            return True, f"Programa '{target}' cerrado correctamente."

        # Fallback con comando del sistema si se conoce el proceso
        for proc_name in target_procs:
            try:
                import subprocess
                res = subprocess.run(["taskkill", "/f", "/im", proc_name], capture_output=True, text=True)
                if res.returncode == 0:
                    return True, f"Programa '{target}' cerrado correctamente."
            except Exception:
                pass

        return False, f"No encontré ninguna ventana o proceso abierto de '{target}'."

    def minimize_active_window(self) -> tuple[bool, str]:
        """Minimiza la ventana activa en primer plano."""
        return self.snap_window(target="active", position="minimize")

    def minimize_app(self, target: str) -> tuple[bool, str]:
        """Minimiza una aplicación específica o la ventana actual."""
        return self.snap_window(target=target, position="minimize")


