"""Adaptador de ejecución para editores de código (IDE Bridge / Fallback UI).

Permite que V.ANSHEE interactúe con editores de código (Antigravity, VS Code, Cursor, Windsurf)
a través de una conexión directa (< 10ms) cuando esté disponible, o recurra al mecanismo
de automatización de ventanas y teclado en Windows OS como fallback universal.
"""

from typing import Tuple, Optional
from pathlib import Path

from src.integrations.editor_hub import editor_hub, EditorHub
from src.executor.window_manager import WindowManager


class EditorAdapter:
    """Gestiona la estrategia híbrida: Conexión directa (WebSocket/MCP) vs Simulación UI."""

    def __init__(self, window_manager: Optional[WindowManager] = None, hub: Optional[EditorHub] = None):
        self.window_manager = window_manager or WindowManager()
        self.editor_hub = hub or editor_hub

    def send_prompt_to_agent(self, prompt: str, target_hint: str = "") -> Tuple[bool, str]:
        """Envía un prompt al agente de IA del editor (Antigravity, Cursor, Copilot, etc.)."""
        # 1. Estrategia Directa: Si el editor está conectado por WebSocket / MCP
        if self.editor_hub.has_active_editor(target_hint):
            session = self.editor_hub.get_active_session(target_hint)
            editor_name = session.editor_name if session else "editor"
            success = self.editor_hub.send_prompt(prompt, editor_hint=target_hint)
            if success:
                msg = f"Prompt inyectado directamente en {editor_name.title()}: '{prompt}'"
                print(f"[EditorAdapter Direct] {msg}")
                return True, msg

        # 2. Estrategia Fallback UI: Simulación de teclado y foco de ventana en Windows
        print(f"[EditorAdapter Fallback] Sin conexión de API directa; recurriendo a foco y teclado...")
        success = self.window_manager.type_and_send_prompt(prompt, target_hint=target_hint, press_enter=True)
        if success:
            msg = f"Prompt enviado al agente vía interfaz de usuario: '{prompt}'"
            print(f"[EditorAdapter UI] {msg}")
            return True, msg

        return False, "No se pudo comunicar con el editor ni enfocar su ventana."

    def insert_code(self, code: str, file_path: str = "", target_hint: str = "") -> Tuple[bool, str]:
        """Inserta código atómicamente en el editor o recurre a edición en disco."""
        if self.editor_hub.has_active_editor(target_hint):
            session = self.editor_hub.get_active_session(target_hint)
            editor_name = session.editor_name if session else "editor"
            success = self.editor_hub.insert_code(code, file_path=file_path, editor_hint=target_hint)
            if success:
                msg = f"Código insertado directamente en {editor_name.title()}."
                print(f"[EditorAdapter Direct] {msg}")
                return True, msg

        # Fallback si se proporcionó una ruta de archivo
        if file_path:
            p = Path(file_path)
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a", encoding="utf-8") as f:
                    f.write(code + "\n")
                return True, f"Código guardado en disco: {p.name}"
            except Exception as e:
                return False, f"Error al guardar código: {e}"

        return False, "Editor no conectado para inserción directa."

    def open_file(self, file_path: str, line: int = 1, column: int = 1, target_hint: str = "") -> Tuple[bool, str]:
        """Abre un archivo en una línea específica mediante API directa o subproceso."""
        if self.editor_hub.has_active_editor(target_hint):
            success = self.editor_hub.open_file(file_path, line=line, column=column, editor_hint=target_hint)
            if success:
                return True, f"Archivo abierto en línea {line} vía API directa."

        return False, "Requiere inicio de editor local."
