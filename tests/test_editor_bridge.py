import unittest
from unittest.mock import MagicMock, patch
import json
import asyncio

from src.integrations.editor_hub import EditorHub, EditorSession
from src.integrations.mcp_server import VansheeMCPServer
from src.executor.editor_adapter import EditorAdapter
from src.nlu.intent_parser import ActionStep, StepParameters, ParsedPipeline
from src.executor.os_executor import OSExecutor


class TestEditorBridgeAndMCP(unittest.TestCase):

    def setUp(self):
        self.hub = EditorHub()
        self.mock_ws = MagicMock()
        self.mock_ws.send_json = MagicMock(return_value=asyncio.Future())
        self.mock_ws.send_json.return_value.set_result(None)

    def test_01_session_registration_and_context(self):
        """Verifica el registro de sesiones y la actualización de telemetría de contexto."""
        session = self.hub.register_session(
            session_id="test_sess_1",
            editor_name="antigravity",
            ws=self.mock_ws,
            metadata={"active_file": "main.py", "language_id": "python", "cursor_line": 42}
        )

        self.assertEqual(session.editor_name, "antigravity")
        self.assertEqual(session.active_file, "main.py")
        self.assertTrue(self.hub.has_active_editor("antigravity"))

        # Actualizar contexto
        self.hub.update_session_context("test_sess_1", {
            "active_file": "server.py",
            "cursor_line": 100
        })

        ctx = self.hub.get_active_context("antigravity")
        self.assertEqual(ctx["active_file"], "server.py")
        self.assertEqual(ctx["cursor_line"], 100)

        # Desconectar sesión
        self.hub.unregister_session("test_sess_1")
        self.assertFalse(self.hub.has_active_editor())

    def test_02_editor_adapter_direct_execution(self):
        """Verifica que EditorAdapter envíe prompts directamente al editor conectado sin simular UI."""
        self.hub.register_session(
            session_id="test_sess_2",
            editor_name="antigravity",
            ws=self.mock_ws,
            metadata={"active_file": "test.py"}
        )

        mock_wm = MagicMock()
        adapter = EditorAdapter(window_manager=mock_wm, hub=self.hub)

        # Simular que el RPC responde de inmediato con éxito
        def mock_send(prompt, editor_hint="", timeout=3.0):
            return True

        with patch.object(self.hub, "send_prompt", side_effect=mock_send):
            success, msg = adapter.send_prompt_to_agent("Escribe hola mundo", target_hint="antigravity")
            self.assertTrue(success)
            self.assertIn("Prompt inyectado directamente", msg)
            # No debió llamar a la simulación UI
            mock_wm.type_and_send_prompt.assert_not_called()

    def test_03_editor_adapter_fallback_ui(self):
        """Verifica que EditorAdapter recurra a la simulación UI cuando no hay un editor conectado."""
        mock_wm = MagicMock()
        mock_wm.type_and_send_prompt.return_value = True

        empty_hub = EditorHub()
        adapter = EditorAdapter(window_manager=mock_wm, hub=empty_hub)

        success, msg = adapter.send_prompt_to_agent("Escribe hola mundo", target_hint="antigravity")
        self.assertTrue(success)
        self.assertIn("interfaz de usuario", msg)
        mock_wm.type_and_send_prompt.assert_called_once()

    def test_04_mcp_server_initialize_and_tools(self):
        """Verifica el protocolo JSON-RPC 2.0 del servidor MCP de V.ANSHEE."""
        mcp = VansheeMCPServer()

        # 1. Initialize
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        init_res = mcp.process_message(init_req)
        self.assertEqual(init_res["result"]["serverInfo"]["name"], "vanshee-core")
        self.assertIn("tools", init_res["result"]["capabilities"])

        # 2. Tools List
        tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        tools_res = mcp.process_message(tools_req)
        tools = tools_res["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("vanshee_execute_command", tool_names)
        self.assertIn("vanshee_get_system_context", tool_names)
        self.assertIn("vanshee_media_control", tool_names)

        # 3. Tool Call System Context
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "vanshee_get_system_context",
                "arguments": {"action_hint": "coding"}
            }
        }
        call_res = mcp.process_message(call_req)
        self.assertIn("content", call_res["result"])
        text_content = call_res["result"]["content"][0]["text"]
        self.assertIn("app_name", text_content)

    def test_05_os_executor_with_editor_adapter(self):
        """Verifica la integración fluida de OSExecutor al escribir prompts en agentes."""
        executor = OSExecutor(interactive_voice=False)
        executor.tts.speak = MagicMock()
        executor.editor_adapter.send_prompt_to_agent = MagicMock(return_value=(True, "Prompt enviado"))

        step = ActionStep(
            intent="WRITE_TEXT",
            target="antigravity",
            parameters=StepParameters(content="Crea un endpoint en FastAPI")
        )
        pipeline = ParsedPipeline(raw_text="escribe en antigravity crea un endpoint", steps=[step])

        success = executor.execute_pipeline(pipeline)
        self.assertTrue(success)
        executor.editor_adapter.send_prompt_to_agent.assert_called_with("Crea un endpoint en FastAPI", target_hint="antigravity")


if __name__ == "__main__":
    unittest.main()
