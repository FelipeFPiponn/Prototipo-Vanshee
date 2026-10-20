import os
import sys
import io
import multiprocessing
from pathlib import Path
import time
import socket
import shutil
import urllib.request
import webbrowser
import subprocess
import threading
import uvicorn
from typing import Optional

# Soporte de multiproceso en ejecutables congelados con PyInstaller en Windows
multiprocessing.freeze_support()

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# En ejecutables de Windows sin consola (--noconsole), sys.stdout y sys.stderr son None.
# Uvicorn y sus formateadores de log crashean al intentar sys.stdout.isatty().
class SafeStream:
    def __init__(self, log_path: Path, original=None):
        self.log_path = log_path
        self.original = original
    def write(self, data):
        if not data:
            return
        try:
            if self.original and hasattr(self.original, "write"):
                self.original.write(data)
        except Exception:
            pass
        try:
            with open(self.log_path, "a", encoding="utf-8", errors="replace") as f:
                f.write(data)
        except Exception:
            pass
    def flush(self):
        try:
            if self.original and hasattr(self.original, "flush"):
                self.original.flush()
        except Exception:
            pass
    def isatty(self):
        return False

log_file = ROOT / "vanshee_app.log"
sys.stdout = SafeStream(log_file, original=sys.stdout)
sys.stderr = SafeStream(log_file, original=sys.stderr)

if sys.stdin is None:
    sys.stdin = io.StringIO()

from config.settings import settings

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

def get_ollama_executable() -> Optional[str]:
    """Localiza el binario de ollama.exe en el sistema."""
    # 1. Verificar si 'ollama' está en el PATH
    p = shutil.which("ollama")
    if p and os.path.exists(p):
        return p

    # 2. Rutas estándar de instalación en Windows
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\Ollama\ollama.exe"),
        os.path.expandvars(r"%ProgramFiles%\Ollama\ollama.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Ollama\ollama.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def ensure_ollama_running():
    """Verifica si Ollama está en ejecución. Si no lo está, lo inicia en segundo plano."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.0) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    ollama_bin = get_ollama_executable()
    if not ollama_bin:
        print("[V.ANSHEE Warning] No se encontró el ejecutable de Ollama en el sistema.")
        return False

    print(f"[V.ANSHEE] Iniciando servicio Ollama en segundo plano ({ollama_bin})...")
    try:
        # 0x08000000 = CREATE_NO_WINDOW, 0x00000200 = CREATE_NEW_PROCESS_GROUP
        flags = 0x08000000 | 0x00000200
        subprocess.Popen(
            [ollama_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags
        )
        # Esperar hasta que el servicio de Ollama responda
        for _ in range(12):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.0) as resp:
                    if resp.status == 200:
                        print("[V.ANSHEE] Servicio Ollama iniciado y listo.")
                        return True
            except Exception:
                pass
        return True
    except Exception as e:
        print(f"[V.ANSHEE Warning] No se pudo arrancar Ollama automáticamente: {e}")
        return False

def wait_for_server(url: str, timeout: float = 30.0) -> bool:
    """Espera activamente a que el servidor web FastAPI responda HTTP 200 antes de abrir la ventana."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=0.6) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False

def get_primary_work_area():
    """Retorna las coordenadas del área de trabajo disponible (restando la barra de tareas de Windows)."""
    try:
        import ctypes
        class RECT(ctypes.Structure):
            _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long), ('right', ctypes.c_long), ('bottom', ctypes.c_long)]
        r = RECT()
        # SPI_GETWORKAREA = 0x0030
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
            return int(r.left), int(r.top), int(r.right), int(r.bottom)
    except Exception:
        pass
    try:
        import win32api
        import win32con
        hmon = win32api.MonitorFromPoint((0, 0), win32con.MONITOR_DEFAULTTOPRIMARY)
        info = win32api.GetMonitorInfo(hmon)
        work = info.get("work")
        if work:
            return work[0], work[1], work[2], work[3]
    except Exception:
        pass
    try:
        import ctypes
        user32 = ctypes.windll.user32
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        return 0, 0, sw, max(400, sh - 48)
    except Exception:
        return 0, 0, 1366, 720

def launch_desktop_gui(url: str) -> bool:
    """Abre la arquitectura coordinada: Burbuja flotante circular nativa (Tkinter) + Panel de Chat (pywebview 420x720)."""
    try:
        import webview
        from src.server import window_bridge
        from src.ui.floating_launcher import FloatingLauncherBubble

        wx, wy, wr, wb = get_primary_work_area()

        # 1. Iniciar la Burbuja Flotante Circular Nativa (oculta inicialmente mientras el chat esté abierto)
        bubble = FloatingLauncherBubble(api_url=url)
        window_bridge.launcher_window = bubble
        bubble_thread = threading.Thread(target=bubble.start, daemon=True, name="LauncherBubbleThread")
        bubble_thread.start()

        # 2. Ventana de Chat Principal adaptable a la pantalla
        cw = 420
        ch = min(720, max(480, wb - wy - 40))
        cx = max(wx, wr - cw - 20)
        cy = max(wy, wb - ch - 20)

        chat_window = webview.create_window(
            title="Vanshee Chat",
            url=url,
            width=cw,
            height=ch,
            x=cx,
            y=cy,
            frameless=True,       # Sin barra de título estándar del SO (arrastre por cabecera y easy_drag)
            on_top=True,          # Superpuesto inicialmente a otras ventanas
            easy_drag=True,       # Habilita arrastrar la ventana a cualquier parte de la pantalla
            background_color='#0d111a'
        )

        # Registrar ventana de chat en el puente del servidor
        window_bridge.chat_window = chat_window

        print(f"[V.ANSHEE UI] Interfaz iniciada: Burbuja circular nativa + Panel de Chat ({cw}x{ch}).")
        webview.start(debug=False)
        
        # Al cerrar la ventana, terminar todo el proceso y la terminal limpiamente
        import os
        os._exit(0)
        return True
    except Exception as e:
        print(f"[V.ANSHEE UI Warning] No se pudo iniciar con pywebview ({e}). Usando modo navegador...")
        open_app_window(url)
        return False

def open_app_window(url: str):
    """Abre la consola como una aplicación de escritorio nativa usando Edge o Chrome en modo App."""
    server_ready = wait_for_server(url, timeout=30.0)
    if not server_ready:
        print(f"[V.ANSHEE UI Warning] Tiempo de espera agotado para {url}. Abriendo ventana de todos modos...")
    else:
        print(f"[V.ANSHEE UI] Servidor verificado y respondiendo en {url}.")

    from src.server import window_bridge
    from src.ui.floating_launcher import FloatingLauncherBubble
    if window_bridge.launcher_window is None:
        try:
            bubble = FloatingLauncherBubble(api_url=url)
            window_bridge.launcher_window = bubble
            bubble_thread = threading.Thread(target=bubble.start, daemon=True, name="LauncherBubbleThread")
            bubble_thread.start()
        except Exception as e:
            print(f"[V.ANSHEE UI Warning] No se pudo iniciar burbuja flotante: {e}")

    # Dimensiones y posicionamiento dinámicos adaptados a la pantalla del equipo
    wx, wy, wr, wb = get_primary_work_area()
    cw = 430
    ch = min(730, max(480, wb - wy - 40))
    cx = max(wx, wr - cw - 20)
    cy = max(wy, wb - ch - 20)

    # Directorio de perfil aislado para la app de escritorio de Vanshee
    profile_dir = os.path.expandvars(r"%LOCALAPPDATA%\Vanshee\UIProfile")
    try:
        os.makedirs(profile_dir, exist_ok=True)
    except Exception:
        pass

    chatbot_args = [
        f"--user-data-dir={profile_dir}",
        f"--window-size={cw},{ch}",
        f"--window-position={cx},{cy}",
        "--disable-http-cache",
        "--disk-cache-size=1",
        "--media-cache-size=1",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    launched = False
    # 1. Intentar Microsoft Edge en modo aplicación
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in edge_paths:
        if os.path.exists(p):
            try:
                subprocess.Popen([p, f"--app={url}"] + chatbot_args)
                print(f"[V.ANSHEE UI] Chatbot de escritorio abierto con Microsoft Edge: {url}")
                launched = True
                break
            except Exception:
                pass

    # 2. Intentar Google Chrome en modo aplicación
    if not launched:
        chrome_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for p in chrome_paths:
            if os.path.exists(p):
                try:
                    subprocess.Popen([p, f"--app={url}"] + chatbot_args)
                    print(f"[V.ANSHEE UI] Chatbot de escritorio abierto con Google Chrome: {url}")
                    launched = True
                    break
                except Exception:
                    pass

    # 3. Fallback al navegador predeterminado
    if not launched:
        print(f"[V.ANSHEE UI] Abriendo en navegador predeterminado: {url}")
        webbrowser.open(url)

    # Mantener el proceso activo para que el servidor Uvicorn no se detenga
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

def main():
    # 1. Asegurar que Ollama esté levantado
    ensure_ollama_running()

    host = getattr(settings, "WEB_HOST", "127.0.0.1")
    port = getattr(settings, "WEB_PORT", 8000)

    while is_port_in_use(port, host):
        port += 1

    url = f"http://{host}:{port}"
    print("=" * 60)
    print("        [V.ANSHEE] - ASISTENTE AUTONOMO DE WINDOWS         ")
    print("=" * 60)
    print(f"[Consola] Enlace local: {url}")
    print("[Voz] Di 'Vanshee' en cualquier momento para hablar.")
    print("=" * 60)

    # Iniciar servidor Uvicorn en un hilo secundario daemon pasando log_config=None para evitar crasheos en modo ventana
    from src.server import app
    server_thread = threading.Thread(
        target=lambda: uvicorn.run(app, host=host, port=port, log_config=None, log_level="warning"),
        daemon=True
    )
    server_thread.start()

    # Esperar a que el servidor HTTP esté listo
    wait_for_server(url, timeout=30.0)

    # Iniciar la interfaz gráfica de escritorio nativa en el hilo principal
    launch_desktop_gui(url)

if __name__ == "__main__":
    main()
