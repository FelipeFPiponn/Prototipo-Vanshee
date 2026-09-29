import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

def get_startup_folder() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        p = Path(appdata) / r"Microsoft\Windows\Start Menu\Programs\Startup"
        if p.exists():
            return p
    return Path.home() / r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"

def get_shortcut_path() -> Path:
    return get_startup_folder() / "VansheeCore.lnk"

def get_vbs_path() -> Path:
    return get_startup_folder() / "VansheeCore.vbs"

def is_autostart_enabled() -> bool:
    lnk = get_shortcut_path()
    vbs = get_vbs_path()
    return lnk.exists() or vbs.exists()

def set_autostart(enable: bool) -> bool:
    vbs = get_vbs_path()
    lnk = get_shortcut_path()

    if not enable:
        try:
            if vbs.exists():
                vbs.unlink()
            if lnk.exists():
                lnk.unlink()
            print("[AutoStart] Inicio automático con Windows desactivado.")
            return True
        except Exception as e:
            print(f"[AutoStart Error] No se pudo eliminar acceso directo de inicio: {e}")
            return False

    # Crear lanzador silencioso VBScript en la carpeta de inicio de Windows
    try:
        startup_dir = get_startup_folder()
        startup_dir.mkdir(parents=True, exist_ok=True)

        pythonw_exe = ROOT / ".venv" / "Scripts" / "pythonw.exe"
        run_ui_py = ROOT / "run_ui.py"

        # VBScript ejecuta pythonw completamente invisible sin ventana negra de terminal
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{str(ROOT)}"
WshShell.Run """{str(pythonw_exe)}"" ""{str(run_ui_py)}""", 0, False
'''
        vbs.write_text(vbs_content, encoding="utf-8")
        print(f"[AutoStart] Inicio automático con Windows configurado exitosamente en: {vbs}")
        return True
    except Exception as e:
        print(f"[AutoStart Error] Falla al crear lanzador de inicio automático: {e}")
        return False
