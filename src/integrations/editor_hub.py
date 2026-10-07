"""Hub central de comunicación directa entre V.ANSHEE y editores de código (IDE Bridge).

Gestiona conexiones WebSocket activas con extensiones de Antigravity IDE, VS Code, Cursor,
Windsurf y agentes CLI, permitiendo inyección atómica de prompts, edición directa de código
y telemetría de contexto en tiempo real sin simulación de interfaz.
"""

import time
import json
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field


@dataclass
class EditorSession:
    session_id: str
    editor_name: str                     # 'antigravity', 'vscode', 'cursor', 'windsurf', 'claude_code'
    workspace_root: str = ""
    active_file: str = ""
    language_id: str = ""
    selected_text: str = ""
    cursor_line: int = 1
    cursor_column: int = 1
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    websocket: Any = None               # Referencia al WebSocket de FastAPI


class EditorHub:
    """Singleton que coordina los editores de código conectados a V.ANSHEE."""

    def __init__(self):
        self.sessions: Dict[str, EditorSession] = {}
        self._pending_rpc: Dict[str, asyncio.Future] = {}
        self._rpc_counter: int = 0
        self._lock = threading.RLock()
        self._on_context_change_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def register_session(self, session_id: str, editor_name: str, ws: Any, metadata: Dict[str, Any] = None) -> EditorSession:
        """Registra un nuevo editor conectado por WebSocket."""
        meta = metadata or {}
        session = EditorSession(
            session_id=session_id,
            editor_name=editor_name.lower().strip(),
            workspace_root=meta.get("workspace_root", ""),
            active_file=meta.get("active_file", ""),
            language_id=meta.get("language_id", ""),
            selected_text=meta.get("selected_text", ""),
            cursor_line=meta.get("cursor_line", 1),
            cursor_column=meta.get("cursor_column", 1),
            websocket=ws,
        )
        with self._lock:
            self.sessions[session_id] = session
        print(f"[EditorHub] Editor conectado: '{session.editor_name}' (Sesión: {session_id[:8]}...)")
        self._notify_context_change(session)
        return session

    def unregister_session(self, session_id: str):
        """Elimina una sesión de editor desconectado."""
        with self._lock:
            session = self.sessions.pop(session_id, None)
        if session:
            print(f"[EditorHub] Editor desconectado: '{session.editor_name}' (Sesión: {session_id[:8]}...)")

    def update_session_context(self, session_id: str, context_data: Dict[str, Any]):
        """Actualiza la telemetría del archivo o selección actual del editor."""
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return
            session.workspace_root = context_data.get("workspace_root", session.workspace_root)
            session.active_file = context_data.get("active_file", session.active_file)
            session.language_id = context_data.get("language_id", session.language_id)
            session.selected_text = context_data.get("selected_text", session.selected_text)
            session.cursor_line = context_data.get("cursor_line", session.cursor_line)
            session.cursor_column = context_data.get("cursor_column", session.cursor_column)
            session.last_ping = time.time()

        self._notify_context_change(session)

    def on_context_change(self, callback: Callable[[Dict[str, Any]], None]):
        """Suscribe un callback para cambios de contexto en los editores."""
        self._on_context_change_callbacks.append(callback)

    def _notify_context_change(self, session: EditorSession):
        payload = {
            "editor_name": session.editor_name,
            "workspace_root": session.workspace_root,
            "active_file": session.active_file,
            "language_id": session.language_id,
            "selected_text": session.selected_text,
            "cursor_line": session.cursor_line,
        }
        for cb in self._on_context_change_callbacks:
            try:
                cb(payload)
            except Exception as e:
                print(f"[EditorHub Error] Error en callback de contexto: {e}")

    def get_active_session(self, editor_hint: str = "") -> Optional[EditorSession]:
        """Obtiene la sesión más adecuada según la pista del usuario o la más reciente."""
        with self._lock:
            if not self.sessions:
                return None
            hint = editor_hint.lower().strip()
            if hint:
                for s in self.sessions.values():
                    if hint in s.editor_name or s.editor_name in hint:
                        return s
            # Retorna la sesión más recientemente activa
            return max(self.sessions.values(), key=lambda s: s.last_ping)

    def has_active_editor(self, editor_hint: str = "") -> bool:
        """Verifica si hay algún editor conectado y disponible."""
        return self.get_active_session(editor_hint) is not None

    def get_active_context(self, editor_hint: str = "") -> Dict[str, Any]:
        """Retorna el contexto del editor activo (archivo, lenguaje, selección)."""
        session = self.get_active_session(editor_hint)
        if not session:
            return {}
        return {
            "editor_name": session.editor_name,
            "workspace_root": session.workspace_root,
            "active_file": session.active_file,
            "language_id": session.language_id,
            "selected_text": session.selected_text,
            "cursor_line": session.cursor_line,
            "cursor_column": session.cursor_column,
        }

    # =========================================================================
    # Métodos RPC de Alto Nivel para OSExecutor
    # =========================================================================

    def send_prompt(self, prompt: str, editor_hint: str = "", timeout: float = 3.0) -> bool:
        """Envía un prompt directamente al panel de chat/agente del editor conectado."""
        session = self.get_active_session(editor_hint)
        if not session:
            return False

        res = self._execute_sync_rpc(session, "send_prompt", {"prompt": prompt}, timeout=timeout)
        return bool(res and res.get("success", False))

    def insert_code(self, code: str, file_path: str = "", editor_hint: str = "", timeout: float = 3.0) -> bool:
        """Inserta un fragmento de código de forma atómica en el editor activo."""
        session = self.get_active_session(editor_hint)
        if not session:
            return False

        res = self._execute_sync_rpc(
            session,
            "insert_code",
            {"code": code, "file_path": file_path},
            timeout=timeout
        )
        return bool(res and res.get("success", False))

    def open_file(self, file_path: str, line: int = 1, column: int = 1, editor_hint: str = "", timeout: float = 3.0) -> bool:
        """Abre un archivo específico en una línea/columna en el editor conectado."""
        session = self.get_active_session(editor_hint)
        if not session:
            return False

        res = self._execute_sync_rpc(
            session,
            "open_file",
            {"file_path": file_path, "line": line, "column": column},
            timeout=timeout
        )
        return bool(res and res.get("success", False))

    def run_command(self, command: str, editor_hint: str = "", timeout: float = 3.0) -> bool:
        """Ejecuta un comando en la terminal integrada del editor."""
        session = self.get_active_session(editor_hint)
        if not session:
            return False

        res = self._execute_sync_rpc(session, "run_command", {"command": command}, timeout=timeout)
        return bool(res and res.get("success", False))

    # =========================================================================
    # Despacho y Manejo Interno de Mensajes RPC
    # =========================================================================

    def handle_rpc_response(self, response_data: Dict[str, Any]):
        """Resuelve el Future pendiente cuando el cliente WebSocket responde."""
        req_id = response_data.get("id")
        if not req_id:
            return
        future = self._pending_rpc.pop(str(req_id), None)
        if future and not future.done():
            future.set_result(response_data.get("result", {}))

    def _execute_sync_rpc(self, session: EditorSession, method: str, params: Dict[str, Any], timeout: float = 3.0) -> Optional[Dict[str, Any]]:
        """Ejecuta una llamada RPC síncronamente desde un hilo de ejecución normal."""
        if not session.websocket:
            return None

        self._rpc_counter += 1
        req_id = f"rpc_{int(time.time()*1000)}_{self._rpc_counter}"
        message = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        future = asyncio.Future()
        self._pending_rpc[req_id] = future

        # Enviar mensaje a través del WebSocket en el bucle de eventos activo
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            send_coro = session.websocket.send_json(message)
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(send_coro, loop)
            else:
                # Si estamos en un hilo sin bucle, creamos uno temporal o despachamos
                asyncio.run(send_coro)
        except Exception as e:
            print(f"[EditorHub Error] No se pudo enviar mensaje RPC a '{session.editor_name}': {e}")
            self._pending_rpc.pop(req_id, None)
            return None

        # Esperar respuesta con timeout
        start = time.time()
        while not future.done():
            if time.time() - start > timeout:
                self._pending_rpc.pop(req_id, None)
                print(f"[EditorHub Warning] Timeout ({timeout}s) esperando respuesta RPC de '{session.editor_name}'")
                return None
            time.sleep(0.01)

        try:
            return future.result()
        except Exception:
            return None


# Instancia global compartida
editor_hub = EditorHub()
