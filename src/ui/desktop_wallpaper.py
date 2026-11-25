import os
import sys
import time
import ctypes
import subprocess
from pathlib import Path
from typing import Optional

try:
    import win32gui
    import win32con
    import win32api
except ImportError:
    win32gui = None
    win32con = None
    win32api = None

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent.parent


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_screen_metrics() -> tuple[int, int]:
    try:
        user32 = ctypes.windll.user32
        return max(1, int(user32.GetSystemMetrics(0))), max(1, int(user32.GetSystemMetrics(1)))
    except Exception:
        return (1920, 1080)


def get_normalized_cursor(screen_w: int, screen_h: int) -> tuple[float, float]:
    """Obtiene la posición global del mouse normalizada en [-1.0, 1.0] en ~0.001ms."""
    try:
        pt = POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            nx = (float(pt.x) / float(screen_w)) * 2.0 - 1.0
            ny = -((float(pt.y) / float(screen_h)) * 2.0 - 1.0)
            return round(max(-1.0, min(1.0, nx)), 4), round(max(-1.0, min(1.0, ny)), 4)
    except Exception:
        pass
    return 0.0, 0.0


def find_or_create_desktop_workerw() -> Optional[int]:
    """
    Implementa la arquitectura nativa de Windows (usada por Wallpaper Engine / Lively Wallpaper):
    1. Envía el mensaje 0x052C a 'Progman' para que Windows separe la capa de iconos (SHELLDLL_DefView)
       de la capa de fondo de escritorio (WorkerW).
    2. Retorna el HWND del 'WorkerW' que está detrás de los iconos del escritorio y detrás de todas las ventanas.
    """
    if win32gui is None:
        return None

    try:
        progman = win32gui.FindWindow("Progman", None)
        if progman:
            res = ctypes.c_ulong(0)
            ctypes.windll.user32.SendMessageTimeoutW(
                progman, 0x052C, 0, 0, 0x0000, 1000, ctypes.byref(res)
            )
            ctypes.windll.user32.SendMessageTimeoutW(
                progman, 0x052C, 0xD, 0x1, 0x0000, 1000, ctypes.byref(res)
            )
    except Exception:
        progman = None

    workerw = None

    def _enum_cb(hwnd, _):
        nonlocal workerw
        try:
            def_view = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
            if def_view:
                # El WorkerW del fondo de pantalla es el hermano siguiente al que contiene SHELLDLL_DefView
                w = win32gui.FindWindowEx(0, hwnd, "WorkerW", None)
                if w:
                    workerw = w
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_enum_cb, None)
    except Exception:
        pass

    if not workerw and progman:
        try:
            w = win32gui.FindWindowEx(progman, 0, "WorkerW", None)
            if w:
                workerw = w
        except Exception:
            pass

    return workerw if workerw else progman


def find_desktop_shell_hwnd() -> Optional[int]:
    if win32gui is None:
        return None
    shell_hwnd = None

    def _enum_cb(hwnd, _):
        nonlocal shell_hwnd
        try:
            if win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None):
                shell_hwnd = hwnd
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_enum_cb, None)
    except Exception:
        pass
    return shell_hwnd or win32gui.FindWindow("Progman", None)


def is_desktop_visible(screen_w: int, screen_h: int) -> bool:
    """
    Detecta si el escritorio está visible o si está completamente tapado por una ventana maximizada (>= 85%).
    - Cuando retorna False, el lienzo 3D congela requestAnimationFrame (0% GPU / 0% CPU) pero permanece
      anclado en el fondo del escritorio (WorkerW) sin superponerse nunca a ninguna ventana.
    """
    if win32gui is None or win32con is None:
        return True

    shell_hwnd = find_desktop_shell_hwnd()
    screen_area = float(screen_w * screen_h)
    occluded = False
    reached_desktop_layer = False

    ignored_classes = {
        "progman", "workerw", "shell_traywnd", "shell_secondarytraywnd",
        "dv2controlhost", "windows.ui.core.corewindow", "notifyiconoverflowwindow",
        "multitaskingviewframe", "cef-osc-widget", "xamlexplorerhostislandwindow",
        "toplevelwindowforoverflowxamlisland", "narratortouchkeyboardwindow",
        "tooltips_class32", "ime", "msctfime ui"
    }
    ignored_titles = {
        "vanshee core wallpaper", "vanshee chat", "vanshee", "banshee chat",
        "banshee", "vanshee bubble", "program manager", "nvidia geforce overlay",
        "windows input experience", "experiencia de entrada de windows", ""
    }

    def _enum_cb(hwnd, _):
        nonlocal occluded, reached_desktop_layer
        if occluded or reached_desktop_layer:
            return True

        if shell_hwnd and hwnd == shell_hwnd:
            reached_desktop_layer = True
            return True

        try:
            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return True

            cls_name = win32gui.GetClassName(hwnd).strip().lower()
            if cls_name in ignored_classes:
                return True

            if win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None):
                reached_desktop_layer = True
                return True

            title = win32gui.GetWindowText(hwnd).strip().lower()
            if not title or title in ignored_titles or "vanshee core wallpaper" in title or "vanshee chat" in title:
                return True

            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex_style & (win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE):
                return True

            try:
                cloaked = ctypes.c_int(0)
                ctypes.windll.dwmapi.DwmGetWindowAttribute(
                    hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
                )
                if cloaked.value != 0:
                    return True
            except Exception:
                pass

            if ctypes.windll.user32.IsZoomed(hwnd):
                occluded = True
                return True

            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            w = max(0, min(screen_w, right) - max(0, left))
            h = max(0, min(screen_h, bottom) - max(0, top))
            if (w * h) >= (screen_area * 0.85):
                occluded = True
                return True
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_enum_cb, None)
    except Exception:
        pass

    return not occluded


def is_button_covered(screen_w: int, screen_h: int) -> bool:
    """
    Verifica si alguna ventana visible (no minimizada) se superpone al área
    del botón de configuración (⚙️ Ajustes) en la parte inferior del escritorio.
    """
    if win32gui is None or win32con is None:
        return False

    cx = screen_w // 2
    cy = screen_h - 79
    bx1, by1, bx2, by2 = cx - 180, cy - 30, cx + 180, cy + 30

    covered = False
    ignored_classes = {
        "progman", "workerw", "shell_traywnd", "shell_secondarytraywnd",
        "dv2controlhost", "windows.ui.core.corewindow", "notifyiconoverflowwindow",
        "multitaskingviewframe", "cef-osc-widget", "xamlexplorerhostislandwindow",
        "toplevelwindowforoverflowxamlisland", "narratortouchkeyboardwindow",
        "tooltips_class32", "ime", "msctfime ui", "foregroundstaging"
    }
    ignored_titles = {
        "vanshee core wallpaper", "vanshee chat", "vanshee", "banshee chat",
        "banshee", "program manager", "nvidia geforce overlay dt",
        "nvidia geforce overlay", "microsoft text input application", ""
    }

    def _cb(hwnd, _):
        nonlocal covered
        if covered:
            return True
        try:
            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return True
            cls = win32gui.GetClassName(hwnd).strip().lower()
            if cls in ignored_classes:
                return True
            title = win32gui.GetWindowText(hwnd).strip().lower()
            if not title or title in ignored_titles or "vanshee" in title:
                return True
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex & (win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE):
                return True
            cloaked = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)
            if cloaked.value != 0:
                return True

            l, t, r, b = win32gui.GetWindowRect(hwnd)
            overlap = not (r <= bx1 or l >= bx2 or b <= by1 or t >= by2)
            if overlap:
                covered = True
                return True
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass

    return covered


class DesktopWallpaperController:
    """
    Controlador del Fondo de Pantalla Holográfico Interactivo de Vanshee.
    - Incrusta la ventana directamente dentro del 'WorkerW' del Escritorio de Windows (SetParent),
      exactamente igual que Wallpaper Engine / Lively Wallpaper.
    - Queda DETRÁS de todas las ventanas y DETRÁS de los iconos del escritorio.
    - Pausa su bucle 3D automáticamente (0% GPU/CPU) cuando una ventana maximizada tapa el escritorio.
    """

    def __init__(self):
        self.enabled: bool = True
        self.hwnd: Optional[int] = None
        self.workerw_hwnd: Optional[int] = None
        self.browser_proc: Optional[subprocess.Popen] = None
        self.base_url: str = "http://127.0.0.1:8000"
        self.screen_w, self.screen_h = get_screen_metrics()
        self.desktop_visible: bool = True
        self._parented_hwnds: set[int] = set()
        self.on_settings_click = None
        self._was_lbutton_down: bool = False
        self._last_click_time: float = 0.0

    def get_wallpaper_bounds(self) -> tuple[int, int, int, int]:
        return 0, 0, self.screen_w, self.screen_h

    def find_wallpaper_hwnd(self) -> Optional[int]:
        if win32gui is None:
            return None
        if self.hwnd and win32gui.IsWindow(self.hwnd):
            return self.hwnd

        # Buscar primero como ventana top-level y luego dentro de WorkerW / Progman
        try:
            h = win32gui.FindWindow(None, "Vanshee Core Wallpaper")
            if h:
                self.hwnd = h
                return h
        except Exception:
            pass

        found = None

        def _find_child(parent_h):
            nonlocal found
            if not parent_h:
                return
            try:
                def _cb(ch, _):
                    nonlocal found
                    if "Vanshee Core Wallpaper" in win32gui.GetWindowText(ch):
                        found = ch
                    return True
                win32gui.EnumChildWindows(parent_h, _cb, None)
            except Exception:
                pass

        if self.workerw_hwnd:
            _find_child(self.workerw_hwnd)
        if not found:
            progman = win32gui.FindWindow("Progman", None)
            _find_child(progman)

        if found:
            self.hwnd = found
        return self.hwnd

    def ensure_process_running(self, base_url: Optional[str] = None):
        """Inicia el subproceso wallpaper_runner.py si está habilitado y aún no está corriendo."""
        if base_url:
            self.base_url = base_url
        if not self.enabled or getattr(sys, "frozen", False):
            return
        if self.find_wallpaper_hwnd():
            return
        if self.browser_proc is not None and self.browser_proc.poll() is None:
            return
        try:
            wp_script = str(ROOT / "src" / "ui" / "wallpaper_runner.py")
            self.browser_proc = subprocess.Popen(
                [sys.executable, wp_script, self.base_url, str(os.getpid())],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
            )
            print("[V.ANSHEE Wallpaper] Subproceso de núcleo holográfico 3D lanzado.")
        except Exception as e:
            print(f"[V.ANSHEE Wallpaper Error] No se pudo lanzar wallpaper_runner.py: {e}")

    def enforce_desktop_layer(self) -> bool:
        """
        Ancla la ventana 'Vanshee Core Wallpaper' como hija de 'WorkerW' (la capa de fondo de escritorio de Windows 10/11).
        Así queda permanentemente detrás de todas las aplicaciones y detrás de los iconos del escritorio.
        """
        if win32gui is None or win32con is None:
            return False
        hwnd = self.find_wallpaper_hwnd()
        if not hwnd:
            return False

        try:
            if not self.enabled:
                if win32gui.IsWindowVisible(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                return True

            if hwnd not in self._parented_hwnds:
                workerw = find_or_create_desktop_workerw()
                self.workerw_hwnd = workerw

                # Asegurar que NO sea TOPMOST y que no aparezca en Alt+Tab ni robe foco
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                ex_style &= ~(win32con.WS_EX_APPWINDOW | win32con.WS_EX_TOPMOST)
                ex_style |= (win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE)
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)

                ctypes.windll.user32.SetWindowPos(
                    hwnd,
                    win32con.HWND_NOTOPMOST,
                    0,
                    0,
                    self.screen_w,
                    self.screen_h,
                    win32con.SWP_NOACTIVATE,
                )

                if workerw:
                    # Incrustar directamente dentro del WorkerW del Escritorio de Windows
                    ctypes.windll.user32.SetParent(hwnd, workerw)
                    # Mapear coordenadas al origen (0, 0) del WorkerW
                    ctypes.windll.user32.SetWindowPos(
                        hwnd,
                        0,
                        0,
                        0,
                        self.screen_w,
                        self.screen_h,
                        win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
                    )
                    print(f"[V.ANSHEE Wallpaper] Incrustado en WorkerW del escritorio (HWND={workerw}).")

                self._parented_hwnds.add(hwnd)

            if not win32gui.IsWindowVisible(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)

            return True
        except Exception as e:
            print(f"[V.ANSHEE Wallpaper Layer Error]: {e}")
            return False

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if self.enabled:
            self.ensure_process_running()
            hwnd = self.find_wallpaper_hwnd()
            if hwnd and win32gui and win32con:
                try:
                    self.enforce_desktop_layer()
                except Exception:
                    pass
        else:
            hwnd = self.find_wallpaper_hwnd()
            if hwnd and win32gui and win32con:
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                except Exception:
                    pass
            if self.browser_proc is not None:
                try:
                    self.browser_proc.terminate()
                except Exception:
                    pass
                self.browser_proc = None
            self.hwnd = None
            self._parented_hwnds.clear()
            # Refrescar el fondo de escritorio original de Windows al apagar el holograma
            try:
                ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, None, 0x0002)
            except Exception:
                pass

    def get_live_state(self, tts_speaking: bool, tts_level: float) -> dict:
        if not self.enabled:
            return {
                "enabled": False,
                "desktop_visible": False,
                "speaking": False,
                "level": 0.0,
                "mouse_x": 0.0,
                "mouse_y": 0.0,
            }

        vis = is_desktop_visible(self.screen_w, self.screen_h)
        self.desktop_visible = vis
        hover_settings = False
        button_covered = is_button_covered(self.screen_w, self.screen_h)

        if vis and not button_covered:
            mx, my = get_normalized_cursor(self.screen_w, self.screen_h)
            try:
                pt = POINT()
                if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                    # Región del botón holográfico #hudBar (bottom: 62px, centrado horizontalmente)
                    cx = self.screen_w // 2
                    cy = self.screen_h - 79
                    if abs(pt.x - cx) <= 170 and abs(pt.y - cy) <= 24:
                        # Verificar que el punto bajo el cursor sea EXCLUSIVAMENTE el escritorio (SysListView32 / SHELLDLL_DefView / WorkerW / Progman)
                        is_on_desktop_surface = False
                        if win32gui:
                            w_at = win32gui.WindowFromPoint((pt.x, pt.y))
                            if w_at:
                                cls_at = win32gui.GetClassName(w_at).strip().lower()
                                if cls_at in ("syslistview32", "shelldll_defview", "workerw", "progman"):
                                    is_on_desktop_surface = True
                        if is_on_desktop_surface:
                            hover_settings = True
                            lbutton_down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
                            now = time.time()
                            if lbutton_down and not self._was_lbutton_down and (now - self._last_click_time) > 0.45:
                                self._last_click_time = now
                                if callable(self.on_settings_click):
                                    try:
                                        self.on_settings_click()
                                    except Exception as e:
                                        print(f"[Wallpaper Settings Click Error]: {e}")
                            self._was_lbutton_down = lbutton_down
                        else:
                            self._was_lbutton_down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
                    else:
                        self._was_lbutton_down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
            except Exception:
                pass
        else:
            mx, my = 0.0, 0.0
            self._was_lbutton_down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)

        return {
            "enabled": True,
            "desktop_visible": vis,
            "speaking": bool(tts_speaking),
            "level": round(float(tts_level), 3) if tts_speaking else 0.0,
            "mouse_x": mx,
            "mouse_y": my,
            "hover_settings": hover_settings,
        }


wallpaper_controller = DesktopWallpaperController()
