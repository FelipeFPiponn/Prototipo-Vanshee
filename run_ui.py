import os
import sys

# Forzar codificación UTF-8 en consola de Windows para evitar errores CP1252 charmap
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import time
import socket
import shutil
import urllib.request
import webbrowser
import subprocess
import threading
import uvicorn
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
        os.path.expandvars(r"%ProgramFiles%\Ollama\ollama.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Ollama\ollama.exe"),
        r"C:\Users\Entoma\AppData\Local\Programs\Ollama\ollama.exe",
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

def open_app_window(url: str):
    """Abre la consola como una aplicación de escritorio nativa usando Edge o Chrome en modo App."""
    server_ready = wait_for_server(url, timeout=30.0)
    if not server_ready:
        print(f"[V.ANSHEE UI Warning] Tiempo de espera agotado para {url}. Abriendo ventana de todos modos...")
    else:
        print(f"[V.ANSHEE UI] Servidor verificado y respondiendo en {url}.")

    # 1. Intentar Microsoft Edge en modo aplicación (sin barras de navegador)
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in edge_paths:
        if os.path.exists(p):
            try:
                subprocess.Popen([p, f"--app={url}", "--window-size=1180,780", "--window-position=center"])
                print(f"[V.ANSHEE UI] Consola de escritorio abierta con Microsoft Edge: {url}")
                return
            except Exception:
                pass

    # 2. Intentar Google Chrome en modo aplicación
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in chrome_paths:
        if os.path.exists(p):
            try:
                subprocess.Popen([p, f"--app={url}", "--window-size=1180,780"])
                print(f"[V.ANSHEE UI] Consola de escritorio abierta con Google Chrome: {url}")
                return
            except Exception:
                pass

    # 3. Fallback al navegador por defecto del sistema
    print(f"[V.ANSHEE UI] Abriendo en navegador predeterminado: {url}")
    webbrowser.open(url)

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
    print("[Voz] Di 'Banshee' en cualquier momento para hablar.")
    print("=" * 60)

    # Iniciar hilo de apertura de ventana que espera a que el servidor HTTP esté listo
    threading.Thread(target=open_app_window, args=(url,), daemon=True).start()

    # Ejecutar Uvicorn
    uvicorn.run("src.server:app", host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
