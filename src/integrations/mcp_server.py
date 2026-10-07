"""Servidor MCP (Model Context Protocol) para V.ANSHEE.

Permite que Antigravity IDE, Claude Desktop, Cursor, OpenCode u otros clientes MCP
se conecten a V.ANSHEE para consultar contexto del sistema, invocar comandos por voz
y automatizar el entorno Windows.
"""

import sys
import json
import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.brain import VansheeBrain
from src.context_awareness import ContextAwarenessEngine
from src.executor.app_indexer import AppIndexer


class VansheeMCPServer:
    """Implementación de servidor MCP en Python con transporte JSON-RPC sobre stdio."""

    def __init__(self, brain: Optional[VansheeBrain] = None):
        self.brain = brain
        self.context_engine = ContextAwarenessEngine()
        self.app_indexer = AppIndexer()
        self.server_info = {
            "name": "vanshee-core",
            "version": "2.5.0"
        }

    def _get_brain(self) -> VansheeBrain:
        if self.brain is None:
            self.brain = VansheeBrain(interactive_voice=False, speak_tts=False)
        return self.brain

    def get_tools(self) -> List[Dict[str, Any]]:
        """Retorna las herramientas disponibles para el editor o cliente MCP."""
        return [
            {
                "name": "vanshee_execute_command",
                "description": "Ejecuta un comando en lenguaje natural a través de V.ANSHEE en Windows OS (abrir apps, buscar en YouTube/Spotify, crear proyectos, etc.).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Instrucción en lenguaje natural (ej: 'abre chrome y busca noticias', 'pausa la musica')."
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "vanshee_get_system_context",
                "description": "Obtiene el contexto actual del sistema operativo (ventana activa, aplicación en foco, sugerencia proactiva y confianza).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action_hint": {
                            "type": "string",
                            "description": "Pista opcional de la acción a evaluar."
                        }
                    }
                }
            },
            {
                "name": "vanshee_media_control",
                "description": "Controla la reproducción multimedia global de Windows (reproducir, pausar, siguiente, anterior, volumen, silenciar).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["play", "pause", "play_pause", "next", "previous", "mute", "volume_up", "volume_down"],
                            "description": "Acción multimedia a ejecutar."
                        }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "vanshee_list_apps",
                "description": "Lista las aplicaciones locales y juegos de Steam indexados en el sistema.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filter_query": {
                            "type": "string",
                            "description": "Filtro de búsqueda de texto opcional."
                        }
                    }
                }
            }
        ]

    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta una herramienta solicitada por el cliente MCP."""
        if tool_name == "vanshee_execute_command":
            cmd = arguments.get("command", "")
            brain = self._get_brain()
            res = brain.handle_user_input(cmd)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": res.success,
                            "response": res.response_text,
                            "plan_summary": res.plan_summary,
                            "context": {
                                "app": res.context.app_name,
                                "window": res.context.window_title
                            }
                        }, ensure_ascii=False, indent=2)
                    }
                ]
            }

        elif tool_name == "vanshee_get_system_context":
            hint = arguments.get("action_hint", "")
            ctx = self.context_engine.observe(action_hint=hint)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "app_name": ctx.app_name,
                            "window_title": ctx.window_title,
                            "suggestion": ctx.suggestion,
                            "confidence": ctx.confidence
                        }, ensure_ascii=False, indent=2)
                    }
                ]
            }

        elif tool_name == "vanshee_media_control":
            action = arguments.get("action", "play_pause")
            brain = self._get_brain()
            res = brain.handle_user_input(f"media_{action}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Acción multimedia '{action}' ejecutada con éxito: {res.success}"
                    }
                ]
            }

        elif tool_name == "vanshee_list_apps":
            q = arguments.get("filter_query", "").lower()
            apps = []
            for name, path in self.app_indexer.app_index.items():
                if not q or q in name.lower():
                    apps.append({"name": name, "path": path})
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"total": len(apps), "apps": apps[:30]}, ensure_ascii=False, indent=2)
                    }
                ]
            }

        raise ValueError(f"Herramienta desconocida: '{tool_name}'")

    def process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Procesa una solicitud JSON-RPC 2.0."""
        req_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False}
                    },
                    "serverInfo": self.server_info
                }
            }

        elif method == "notifications/initialized":
            return None

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.get_tools()}
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            try:
                result = self.handle_tool_call(tool_name, args)
                return {"jsonrpc": "2.0", "id": req_id, "result": result}
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Método no soportado: '{method}'"}
        }

    def run_stdio(self):
        """Bucle principal de escucha en stdio para clientes MCP."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                res = self.process_message(req)
                if res:
                    sys.stdout.write(json.dumps(res) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                pass


if __name__ == "__main__":
    server = VansheeMCPServer()
    server.run_stdio()
