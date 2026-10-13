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
        def mock_send(prompt, editor_hint="", timeout=4.0, **kwargs):
            return True

        with patch.object(self.hub, "send_prompt", side_effect=mock_send):
            success, msg = adapter.send_prompt_to_agent("Escribe hola mundo", target_hint="antigravity")
            self.assertTrue(success)
            self.assertIn("Prompt enviado directamente al agente", msg)
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

    def test_06_dile_a_antigravity_nlu_and_voice_deduplication(self):
        """Verifica que 'dile a antigravity <msg>' se parsee sin 'dile' y no duplique voz en Brain."""
        from src.nlu.intent_parser import IntentParser
        from src.brain import VansheeBrain

        parser = IntentParser()
        pipeline = parser.parse("dile a antigravity hola esto es una prueba")
        self.assertEqual(len(pipeline.steps), 2)
        self.assertEqual(pipeline.steps[0].intent, "OPEN_APP")
        self.assertEqual(pipeline.steps[0].target, "antigravity")
        self.assertEqual(pipeline.steps[1].intent, "WRITE_TEXT")
        self.assertEqual(pipeline.steps[1].target, "antigravity")
        self.assertEqual(pipeline.steps[1].parameters.content, "hola esto es una prueba")

        # Verificar que OSExecutor con interactive_voice=False no invoque tts.speak internamente
        mock_tts = MagicMock()
        executor = OSExecutor(tts=mock_tts, interactive_voice=False)
        executor.window_manager.find_and_focus = MagicMock(return_value=(True, "Antigravity IDE"))
        executor.editor_adapter.send_prompt_to_agent = MagicMock(return_value=(True, "Prompt enviado"))

        brain = VansheeBrain(tts=mock_tts, parser=parser, executor=executor, speak_tts=True)
        res = brain.handle_user_input("dile a antigravity hola esto es una prueba")

        self.assertTrue(res.success)
        # La voz debe llamarse EXACTAMENTE UNA VEZ por Brain al finalizar, no repetirse
        self.assertEqual(mock_tts.speak.call_count, 1)

    def test_07_window_manager_excludes_vanshee_self_windows(self):
        """Verifica que WindowManager diferencie ventanas propias de Vanshee del editor Antigravity."""
        from src.executor.window_manager import WindowManager
        wm = WindowManager()

        self.assertTrue(wm._is_self_window("Vanshee Chat"))
        self.assertTrue(wm._is_self_window("Vanshee Bubble"))
        self.assertTrue(wm._is_self_window("Vanshee Launcher"))
        self.assertTrue(wm._is_self_window("Vanshee"))

        # Ventana de Antigravity IDE con el workspace abierto 'vanshee-core' NO debe ser excluida
        self.assertFalse(wm._is_self_window("vanshee-core - Antigravity IDE - window_manager.py"))
        self.assertFalse(wm._is_self_window("Antigravity IDE"))

    def test_08_editor_status_intent_and_generic_hints(self):
        """Verifica la resolución de hints genéricos de editor y el comando de estado de editores."""
        from src.nlu.intent_parser import IntentParser

        self.hub.register_session(
            session_id="test_sess_8",
            editor_name="antigravity",
            ws=self.mock_ws,
            metadata={"active_file": "main.py"}
        )

        # 1. get_active_session debe resolver con 'editor', 'el editor', 'agente', etc.
        s1 = self.hub.get_active_session("editor")
        self.assertIsNotNone(s1)
        self.assertEqual(s1.editor_name, "antigravity")

        s2 = self.hub.get_active_session("el agente")
        self.assertIsNotNone(s2)
        self.assertEqual(s2.editor_name, "antigravity")

        # 2. Parsing de comandos de estado de editores
        parser = IntentParser()
        p1 = parser.parse("conéctate al editor de código")
        self.assertEqual(len(p1.steps), 1)
        self.assertEqual(p1.steps[0].intent, "EDITOR_STATUS")

        p2 = parser.parse("revisa la conexión con los editores")
        self.assertEqual(len(p2.steps), 1)
        self.assertEqual(p2.steps[0].intent, "EDITOR_STATUS")

        p3 = parser.parse("envia el prompt al agente: crea una función de suma")
        self.assertEqual(len(p3.steps), 1)
        self.assertEqual(p3.steps[0].intent, "WRITE_TEXT")
        self.assertEqual(p3.steps[0].target, "antigravity")
        self.assertEqual(p3.steps[0].parameters.content, "crea una función de suma")


if __name__ == "__main__":
    unittest.main()
