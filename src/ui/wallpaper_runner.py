import os
import sys
import time
import ctypes
import threading
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return True
    try:
        SYNCHRONIZE = 0x00100000
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        exit_code = ctypes.c_ulong(0)
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(h)
        return exit_code.value == 259  # STILL_ACTIVE = 259
    except Exception:
        return True


def run_wallpaper_window(base_url: str, parent_pid: int = 0):
    import webview
    from src.ui.desktop_wallpaper import wallpaper_controller

    x, y, w, h = wallpaper_controller.get_wallpaper_bounds()
    wallpaper_url = f"{base_url.rstrip('/')}/wallpaper"

    window = webview.create_window(
        title="Vanshee Core Wallpaper",
        url=wallpaper_url,
        width=w,
        height=h,
        x=x,
        y=y,
        frameless=True,
        on_top=False,
        easy_drag=False,
        focus=False,
        background_color="#000000",
    )

    def _layer_loop():
        time.sleep(0.35)
        while True:
            if parent_pid > 0 and not _is_pid_running(parent_pid):
                try:
                    ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, None, 0x0002)
                except Exception:
                    pass
                os._exit(0)
            try:
                wallpaper_controller.enforce_desktop_layer()
            except Exception:
                pass
            time.sleep(0.5)

    threading.Thread(target=_layer_loop, daemon=True, name="WallpaperDesktopLayerLoop").start()

    cache_path = ROOT / "data" / "wallpaper_webview_cache"
    cache_path.mkdir(parents=True, exist_ok=True)
    try:
        webview.start(debug=False, private_mode=False, storage_path=str(cache_path))
    finally:
        try:
            ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, None, 0x0002)
        except Exception:
            pass


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    ppid = int(sys.argv[2]) if len(sys.argv) > 2 else os.getppid()
    run_wallpaper_window(url, ppid)
