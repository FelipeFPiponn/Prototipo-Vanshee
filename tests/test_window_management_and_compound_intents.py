import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import unittest
from src.routines.db import init_db
from src.nlu.intent_parser import IntentParser, ActionStep, StepParameters, ParsedPipeline
from src.executor.window_manager import WindowManager
from src.executor.os_executor import OSExecutor


class TestWindowManagementAndCompoundIntents(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.parser = IntentParser()
        cls.wm = WindowManager()

    def test_01_split_screen_dual_open_parsing(self):
        """Verifica que 'abre a la izquierda de mi pantalla YouTube y a la derecha AntiGravity' genere 2 pasos con posiciones."""
        cmd = "abre a la izquierda de mi pantalla YouTube y a la derecha AntiGravity"
        pipeline = self.parser.parse(cmd)
        self.assertEqual(len(pipeline.steps), 2)
        
        # Paso 1: YouTube a la izquierda
        self.assertEqual(pipeline.steps[0].intent, "OPEN_APP")
        self.assertEqual(pipeline.steps[0].target, "youtube")
        self.assertEqual(pipeline.steps[0].parameters.position, "left")

        # Paso 2: AntiGravity a la derecha
        self.assertEqual(pipeline.steps[1].intent, "OPEN_APP")
        self.assertEqual(pipeline.steps[1].target, "antigravity")
        self.assertEqual(pipeline.steps[1].parameters.position, "right")

    def test_02_single_app_with_position_parsing(self):
        """Verifica que 'abre YouTube a la izquierda de mi pantalla' genere 1 paso OPEN_APP con position='left'."""
        cmd = "abre YouTube a la izquierda de mi pantalla"
        pipeline = self.parser.parse(cmd)
        self.assertEqual(len(pipeline.steps), 1)
        self.assertEqual(pipeline.steps[0].intent, "OPEN_APP")
        self.assertEqual(pipeline.steps[0].target, "youtube")
        self.assertEqual(pipeline.steps[0].parameters.position, "left")

    def test_03_app_first_dual_open_parsing(self):
        """Verifica 'abre YouTube a la izquierda y AntiGravity a la derecha'."""
        cmd = "abre YouTube a la izquierda y AntiGravity a la derecha"
        pipeline = self.parser.parse(cmd)
        self.assertEqual(len(pipeline.steps), 2)
        self.assertEqual(pipeline.steps[0].target, "youtube")
        self.assertEqual(pipeline.steps[0].parameters.position, "left")
        self.assertEqual(pipeline.steps[1].target, "antigravity")
        self.assertEqual(pipeline.steps[1].parameters.position, "right")

    def test_04_divide_pantalla_parsing(self):
        """Verifica 'divide la pantalla entre YouTube y AntiGravity'."""
        cmd = "divide la pantalla entre YouTube y AntiGravity"
        pipeline = self.parser.parse(cmd)
        self.assertEqual(len(pipeline.steps), 2)
        self.assertEqual(pipeline.steps[0].target, "youtube")
        self.assertEqual(pipeline.steps[0].parameters.position, "left")
        self.assertEqual(pipeline.steps[1].target, "antigravity")
        self.assertEqual(pipeline.steps[1].parameters.position, "right")

    def test_05_move_window_parsing(self):
        """Verifica comandos de mover o acomodar ventana existente."""
        cmd1 = "mueve YouTube a la derecha"
        p1 = self.parser.parse(cmd1)
        self.assertEqual(len(p1.steps), 1)
        self.assertEqual(p1.steps[0].intent, "WINDOW_CONTROL")
        self.assertEqual(p1.steps[0].target, "youtube")
        self.assertEqual(p1.steps[0].parameters.position, "right")

        cmd2 = "mueve la ventana actual a la izquierda"
        p2 = self.parser.parse(cmd2)
        self.assertEqual(len(p2.steps), 1)
        self.assertEqual(p2.steps[0].intent, "WINDOW_CONTROL")
        self.assertEqual(p2.steps[0].target, "active")
        self.assertEqual(p2.steps[0].parameters.position, "left")

    def test_06_maximize_minimize_center_parsing(self):
        """Verifica comandos de maximizar, minimizar y centrar ventanas."""
        p_max = self.parser.parse("maximiza Spotify")
        self.assertEqual(p_max.steps[0].intent, "WINDOW_CONTROL")
        self.assertEqual(p_max.steps[0].target, "spotify")
        self.assertEqual(p_max.steps[0].parameters.position, "maximize")

        p_min = self.parser.parse("minimiza Discord")
        self.assertEqual(p_min.steps[0].intent, "WINDOW_CONTROL")
        self.assertEqual(p_min.steps[0].target, "discord")
        self.assertEqual(p_min.steps[0].parameters.position, "minimize")

        p_cen = self.parser.parse("centra la ventana actual")
        self.assertEqual(p_cen.steps[0].intent, "WINDOW_CONTROL")
        self.assertEqual(p_cen.steps[0].target, "active")
        self.assertEqual(p_cen.steps[0].parameters.position, "center")

    def test_07_tab_management_parsing(self):
        """Verifica comandos de gestión de pestañas."""
        p_next = self.parser.parse("siguiente pestaña")
        self.assertEqual(p_next.steps[0].intent, "WINDOW_CONTROL")
        self.assertEqual(p_next.steps[0].target, "next_tab")

        p_prev = self.parser.parse("anterior pestaña")
        self.assertEqual(p_prev.steps[0].intent, "WINDOW_CONTROL")
        self.assertEqual(p_prev.steps[0].target, "prev_tab")

        p_new = self.parser.parse("nueva pestaña")
        self.assertEqual(p_new.steps[0].intent, "WINDOW_CONTROL")
        self.assertEqual(p_new.steps[0].target, "new_tab")

        p_close = self.parser.parse("cierra la pestaña")
        self.assertEqual(p_close.steps[0].intent, "WINDOW_CONTROL")
        self.assertEqual(p_close.steps[0].target, "close_tab")

    def test_08_compound_multi_action_parsing(self):
        """Verifica que oraciones con múltiples acciones independientes se separen correctamente."""
        cmd = "abre Spotify y pon el volumen al 50%"
        pipeline = self.parser.parse(cmd)
        self.assertEqual(len(pipeline.steps), 2)
        self.assertEqual(pipeline.steps[0].intent, "OPEN_APP")
        self.assertEqual(pipeline.steps[0].target, "spotify")
        self.assertEqual(pipeline.steps[1].intent, "SET_APP_VOLUME")
        self.assertEqual(pipeline.steps[1].parameters.content, "50")

    def test_09_compound_dual_app_open(self):
        """Verifica 'abre YouTube y abre Discord'."""
        cmd = "abre YouTube y abre Discord"
        pipeline = self.parser.parse(cmd)
        self.assertEqual(len(pipeline.steps), 2)
        self.assertEqual(pipeline.steps[0].intent, "OPEN_APP")
        self.assertEqual(pipeline.steps[0].target, "youtube")
        self.assertEqual(pipeline.steps[1].intent, "OPEN_APP")
        self.assertEqual(pipeline.steps[1].target, "discord")

    def test_10_search_rule_preservation(self):
        """Verifica que 'abre youtube y busca videos de música' siga generando 1 solo paso SEARCH_CONTENT."""
        cmd = "abre youtube y busca videos de música"
        pipeline = self.parser.parse(cmd)
        self.assertEqual(len(pipeline.steps), 1)
        self.assertEqual(pipeline.steps[0].intent, "SEARCH_CONTENT")
        self.assertEqual(pipeline.steps[0].target, "youtube")

    def test_11_window_manager_position_normalization(self):
        """Verifica que _normalize_position reconozca variantes en español."""
        self.assertEqual(self.wm._normalize_position("a la izquierda de mi pantalla"), "left")
        self.assertEqual(self.wm._normalize_position("mitad derecha"), "right")
        self.assertEqual(self.wm._normalize_position("mitad superior"), "top")
        self.assertEqual(self.wm._normalize_position("mitad inferior"), "bottom")
        self.assertEqual(self.wm._normalize_position("arriba a la izquierda"), "top_left")
        self.assertEqual(self.wm._normalize_position("abajo a la derecha"), "bottom_right")
        self.assertEqual(self.wm._normalize_position("pantalla completa"), "maximize")
        self.assertEqual(self.wm._normalize_position("minimizar"), "minimize")
        self.assertEqual(self.wm._normalize_position("en el centro"), "center")

    @patch("src.executor.window_manager.WindowManager.set_window_position", return_value=True)
    def test_12_os_executor_window_control_execution(self, mock_set_pos):
        """Verifica que OSExecutor ejecute acciones WINDOW_CONTROL exitosamente."""
        executor = OSExecutor()
        with patch.object(executor.window_manager, "find_window", return_value={"hwnd": 111, "title": "YouTube - Brave"}):
            step = ActionStep(
                intent="WINDOW_CONTROL",
                target="youtube",
                parameters=StepParameters(position="left")
            )
            pipeline = ParsedPipeline(raw_text="pon youtube a la izquierda", steps=[step])
            success = executor.execute_pipeline(pipeline)
            self.assertTrue(success)
            self.assertIn("YouTube", executor.last_action_message)
            self.assertIn("izquierda", executor.last_action_message)

    @patch("pyautogui.hotkey")
    def test_13_tab_action_execution(self, mock_hotkey):
        """Verifica que las acciones de pestañas ejecuten los atajos adecuados."""
        success, msg = self.wm.handle_tab_action("next_tab")
        self.assertTrue(success)
        mock_hotkey.assert_called_with("ctrl", "tab")

        success, msg = self.wm.handle_tab_action("close_tab")
        self.assertTrue(success)
        mock_hotkey.assert_called_with("ctrl", "w")

    def test_14_full_screen_variations_parsing(self):
        """Verifica que todas las variaciones de pantalla completa se reconozcan como position='maximize'."""
        cases = [
            ("pon spotify en pantalla completa", "spotify", "maximize"),
            ("pon la ventana en pantalla completa", "active", "maximize"),
            ("pantalla completa", "active", "maximize"),
            ("en pantalla completa", "active", "maximize"),
            ("a pantalla completa", "active", "maximize"),
            ("pon a pantalla completa", "active", "maximize"),
            ("pon en pantalla completa", "active", "maximize"),
            ("pon spotify a pantalla completa", "spotify", "maximize"),
            ("hazla pantalla completa", "active", "maximize"),
            ("pon la ventana actual a pantalla completa", "active", "maximize"),
        ]
        for cmd, expected_target, expected_pos in cases:
            p = self.parser.parse(cmd)
            self.assertEqual(len(p.steps), 1, f"Fallo al parsear '{cmd}'")
            self.assertEqual(p.steps[0].intent, "WINDOW_CONTROL", f"Intent incorrecto para '{cmd}'")
            self.assertEqual(p.steps[0].target, expected_target, f"Target incorrecto para '{cmd}'")
            self.assertEqual(p.steps[0].parameters.position, expected_pos, f"Posicion incorrecta para '{cmd}'")

    def test_15_open_app_with_full_screen_parsing(self):
        """Verifica que 'abre <app> en pantalla completa' genere OPEN_APP con position='maximize'."""
        cmd1 = "abre youtube en pantalla completa"
        p1 = self.parser.parse(cmd1)
        self.assertEqual(len(p1.steps), 1)
        self.assertEqual(p1.steps[0].intent, "OPEN_APP")
        self.assertEqual(p1.steps[0].target, "youtube")
        self.assertEqual(p1.steps[0].parameters.position, "maximize")

        cmd2 = "abre en pantalla completa spotify"
        p2 = self.parser.parse(cmd2)
        self.assertEqual(len(p2.steps), 1)
        self.assertEqual(p2.steps[0].intent, "OPEN_APP")
        self.assertEqual(p2.steps[0].target, "spotify")
        self.assertEqual(p2.steps[0].parameters.position, "maximize")

    def test_16_arrange_tile_windows_parsing(self):
        """Verifica que comandos para ordenar u organizar ventanas generen target='tile' y position='tile'."""
        for cmd in ["ordena las ventanas", "organiza las ventanas", "ordena las ventanas en la pantalla", "acomoda las ventanas"]:
            p = self.parser.parse(cmd)
            self.assertEqual(len(p.steps), 1, f"Fallo en '{cmd}'")
            self.assertEqual(p.steps[0].intent, "WINDOW_CONTROL")
            self.assertEqual(p.steps[0].target, "tile")
            self.assertEqual(p.steps[0].parameters.position, "tile")

    @patch("src.executor.window_manager.WindowManager.set_window_position", return_value=True)
    def test_17_snap_window_target_pantalla_completa(self, mock_set_pos):
        """Verifica que snap_window reconozca target='pantalla completa' como posición para la ventana activa."""
        with patch("win32gui.GetForegroundWindow", return_value=999), \
             patch("win32gui.GetWindowText", return_value="Test Window"):
            success, msg = self.wm.snap_window("pantalla completa", "")
            self.assertTrue(success)
            mock_set_pos.assert_called_with(999, "maximize")
            self.assertIn("pantalla completa", msg)

    @patch("src.executor.window_manager.WindowManager.set_window_position", return_value=True)
    def test_18_tile_windows_execution(self, mock_set_pos):
        """Verifica que tile_windows organice las ventanas abiertas."""
        mock_windows = [
            {"hwnd": 101, "title": "Brave Browser", "pid": 111},
            {"hwnd": 102, "title": "Spotify", "pid": 222}
        ]
        with patch.object(self.wm, "get_open_windows", return_value=mock_windows), \
             patch.object(self.wm, "_is_self_window", return_value=False):
            success, msg = self.wm.tile_windows()
            self.assertTrue(success)
            self.assertEqual(mock_set_pos.call_count, 2)
            mock_set_pos.assert_any_call(101, "left")
            mock_set_pos.assert_any_call(102, "right")

    def test_19_multiple_apps_and_independent_media_control(self):
        """Verifica que 'abre League of Legends, abre YouTube y da play en Spotify' no busque LoL en YouTube/Spotify."""
        p1 = self.parser.parse("Banshee, abre League of Legends, abre YouTube y da play en Spotify.")
        self.assertEqual(len(p1.steps), 3)
        self.assertEqual(p1.steps[0].intent, "OPEN_APP")
        self.assertEqual(p1.steps[0].target, "league of legends")
        self.assertEqual(p1.steps[1].intent, "OPEN_APP")
        self.assertEqual(p1.steps[1].target, "youtube")
        self.assertEqual(p1.steps[2].intent, "MEDIA_CONTROL")
        self.assertEqual(p1.steps[2].target, "play")
        self.assertNotIn("SEARCH_CONTENT", [s.intent for s in p1.steps])

        # Caso sin comas procedente de transcripción STT continua
        p2 = self.parser.parse("abre league of legends abre youtube y da play en spotify")
        self.assertEqual(len(p2.steps), 3)
        self.assertEqual(p2.steps[0].intent, "OPEN_APP")
        self.assertEqual(p2.steps[1].intent, "OPEN_APP")
        self.assertEqual(p2.steps[2].intent, "MEDIA_CONTROL")
        self.assertNotIn("SEARCH_CONTENT", [s.intent for s in p2.steps])

    def test_20_close_app_and_window_parsing(self):
        """Verifica la correcta interpretación y parsing de comandos de cierre."""
        cases = [
            ("cierra Brave", "CLOSE_APP", "brave", ""),
            ("cerrar Brave", "CLOSE_APP", "brave", ""),
            ("cierra el navegador Brave", "CLOSE_APP", "brave", ""),
            ("cierra la aplicación de Brave", "CLOSE_APP", "brave", ""),
            ("cierra la ventana de Brave", "CLOSE_APP", "brave", ""),
            ("sierra Brave", "CLOSE_APP", "brave", ""),
            ("cierra el juego League of Legends", "CLOSE_APP", "league of legends", ""),
            ("cierra la ventana", "WINDOW_CONTROL", "active", "close"),
            ("cierra esta ventana", "WINDOW_CONTROL", "active", "close"),
            ("cierra la ventana actual", "WINDOW_CONTROL", "active", "close"),
            ("cierra esto", "WINDOW_CONTROL", "active", "close"),
            ("cierra la pestaña", "WINDOW_CONTROL", "close_tab", ""),
            ("cierra esta pestaña", "WINDOW_CONTROL", "close_tab", ""),
        ]
        for cmd, exp_intent, exp_target, exp_pos in cases:
            p = self.parser.parse(cmd)
            self.assertEqual(len(p.steps), 1, f"Fallo al parsear '{cmd}'")
            self.assertEqual(p.steps[0].intent, exp_intent, f"Intent incorrecto para '{cmd}'")
            self.assertEqual(p.steps[0].target, exp_target, f"Target incorrecto para '{cmd}'")
            self.assertEqual(p.steps[0].parameters.position, exp_pos, f"Position incorrecta para '{cmd}'")

    def test_21_close_app_execution(self):
        """Verifica que OSExecutor ejecute la acción CLOSE_APP delegando a window_manager.close_app."""
        executor = OSExecutor()
        with patch.object(executor.window_manager, "close_app", return_value=(True, "Programa 'brave' cerrado correctamente.")) as mock_close:
            step = ActionStep(intent="CLOSE_APP", target="brave", parameters=StepParameters())
            pipeline = ParsedPipeline(raw_text="cierra brave", steps=[step])
            success = executor.execute_pipeline(pipeline)
            self.assertTrue(success)
            mock_close.assert_called_once_with("brave")
            self.assertIn("brave", executor.last_action_message)

    def test_22_close_active_window_execution(self):
        """Verifica que WINDOW_CONTROL con posición 'close' y target 'active' llame a close_active_window."""
        executor = OSExecutor()
        with patch.object(executor.window_manager, "close_active_window", return_value=(True, "Ventana activa cerrada.")) as mock_close_win:
            step = ActionStep(intent="WINDOW_CONTROL", target="active", parameters=StepParameters(position="close"))
            pipeline = ParsedPipeline(raw_text="cierra la ventana", steps=[step])
            success = executor.execute_pipeline(pipeline)
            self.assertTrue(success)
            mock_close_win.assert_called_once()
            self.assertIn("Ventana activa cerrada", executor.last_action_message)

    def test_23_window_manager_close_app_logic(self):
        """Verifica que WindowManager.close_app detecte ventanas coincidentes y cierre el hwnd."""
        mock_windows = [
            {"hwnd": 5555, "title": "Brave - YouTube", "pid": 1234},
            {"hwnd": 6666, "title": "Discord", "pid": 4321}
        ]
        with patch.object(self.wm, "get_open_windows", return_value=mock_windows), \
             patch.object(self.wm, "_is_self_window", return_value=False), \
             patch.object(self.wm, "close_window", return_value=True) as mock_close_win, \
             patch("psutil.process_iter", return_value=[]):
            success, msg = self.wm.close_app("brave")
            self.assertTrue(success)
            mock_close_win.assert_called_once_with(5555)
            self.assertIn("brave", msg.lower())


if __name__ == "__main__":
    unittest.main()

