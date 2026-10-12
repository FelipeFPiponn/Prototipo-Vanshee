import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import unittest
from src.routines.db import init_db
from src.context.mode_manager import ModeManager, mode_manager
from src.nlu.intent_parser import IntentParser, ActionStep, StepParameters, ParsedPipeline
from src.executor.os_executor import OSExecutor


class TestOperatingModes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.parser = IntentParser()

    def setUp(self):
        # Asegurar un estado limpio antes de cada test
        mode_manager.set_mode("default")

    def test_01_mode_manager_state_transitions(self):
        """Verifica las transiciones entre Modo Gamer, Modo Trabajo y Modo General."""
        self.assertEqual(mode_manager.get_current_mode(), "default")
        self.assertFalse(mode_manager.is_gamer_mode())
        self.assertFalse(mode_manager.is_work_mode())

        # Activar Modo Gamer
        ok, desc, voice = mode_manager.set_mode("gamer")
        self.assertTrue(ok)
        self.assertEqual(mode_manager.get_current_mode(), "gamer")
        self.assertTrue(mode_manager.is_gamer_mode())
        self.assertFalse(mode_manager.is_work_mode())
        self.assertIn("Gamer", desc)
        self.assertIn("Gamer", voice)

        # Activar Modo Trabajo
        ok, desc, voice = mode_manager.set_mode("work")
        self.assertTrue(ok)
        self.assertEqual(mode_manager.get_current_mode(), "work")
        self.assertTrue(mode_manager.is_work_mode())
        self.assertFalse(mode_manager.is_gamer_mode())
        self.assertIn("Trabajo", desc)
        self.assertIn("Trabajo", voice)

        # Restablecer a General
        ok, desc, voice = mode_manager.set_mode("default")
        self.assertTrue(ok)
        self.assertEqual(mode_manager.get_current_mode(), "default")
        self.assertFalse(mode_manager.is_gamer_mode())
        self.assertFalse(mode_manager.is_work_mode())

    def test_02_mode_manager_sqlite_persistence(self):
        """Verifica que el modo activo se persista en la base de datos SQLite y se recupere en nuevas instancias."""
        mode_manager.set_mode("gamer")
        
        # Crear una nueva instancia independiente de ModeManager
        new_mgr = ModeManager()
        self.assertEqual(new_mgr.get_current_mode(), "gamer")
        self.assertTrue(new_mgr.is_gamer_mode())

        # Cambiar a modo trabajo y verificar persistencia
        mode_manager.set_mode("work")
        another_mgr = ModeManager()
        self.assertEqual(another_mgr.get_current_mode(), "work")
        self.assertTrue(another_mgr.is_work_mode())

    def test_03_mode_manager_normalization_and_aliases(self):
        """Verifica que sinónimos y variaciones coloquiales mapeen al modo correcto."""
        mgr = ModeManager()
        self.assertEqual(mgr.normalize_mode_name("programador"), "work")
        self.assertEqual(mgr.normalize_mode_name("programacion"), "work")
        self.assertEqual(mgr.normalize_mode_name("desarrollo"), "work")
        self.assertEqual(mgr.normalize_mode_name("dev"), "work")
        self.assertEqual(mgr.normalize_mode_name("oficina"), "work")

        self.assertEqual(mgr.normalize_mode_name("juegos"), "gamer")
        self.assertEqual(mgr.normalize_mode_name("gaming"), "gamer")
        self.assertEqual(mgr.normalize_mode_name("partida"), "gamer")

        self.assertEqual(mgr.normalize_mode_name("normal"), "default")
        self.assertEqual(mgr.normalize_mode_name("estándar"), "default")
        self.assertEqual(mgr.normalize_mode_name("general"), "default")
        self.assertEqual(mgr.normalize_mode_name("desconocido123"), "default")

    def test_04_mode_manager_callbacks(self):
        """Verifica que los observadores registrados reciban las notificaciones de cambio de modo."""
        events = []
        def on_change(canonical, info):
            events.append((canonical, info["name"]))

        mgr = ModeManager()
        mgr.on_mode_change(on_change)
        mgr.set_mode("gamer")
        mgr.set_mode("work")

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], ("gamer", "Modo Gamer"))
        self.assertEqual(events[1], ("work", "Modo Trabajo"))

    def test_05_nlu_gamer_mode_detection(self):
        """Verifica la detección determinista de activación del Modo Gamer por voz."""
        gamer_phrases = [
            "activa el modo gamer",
            "activar modo gamer",
            "pon el modo gamer",
            "inicia el modo de juego",
            "cambia al modo gamer",
            "vamos a jugar",
            "hora de jugar",
            "modo gamer",
            "modo juego",
            "banshee, activa el modo gamer",
            "oye banshee activa modo gamer",
        ]
        for phrase in gamer_phrases:
            pipeline = self.parser.parse(phrase)
            self.assertEqual(len(pipeline.steps), 1, f"Fallo al parsear: '{phrase}'")
            step = pipeline.steps[0]
            self.assertEqual(step.intent, "MODE_SWITCH", f"Intent incorrecto en: '{phrase}'")
            self.assertEqual(step.target, "gamer", f"Target incorrecto en: '{phrase}'")

    def test_06_nlu_work_mode_detection(self):
        """Verifica la detección determinista de activación del Modo Trabajo / Programador por voz."""
        work_phrases = [
            "activa el modo trabajo",
            "activar modo trabajo",
            "activa el modo programador",
            "pon el modo dev",
            "inicia modo de programacion",
            "vamos a programar",
            "hora de programar",
            "a programar",
            "hora de trabajar",
            "vamos a trabajar",
            "modo trabajo",
            "modo programador",
            "modo dev",
            "banshee, pon modo programador",
            "oye banshee vamos a programar",
        ]
        for phrase in work_phrases:
            pipeline = self.parser.parse(phrase)
            self.assertEqual(len(pipeline.steps), 1, f"Fallo al parsear: '{phrase}'")
            step = pipeline.steps[0]
            self.assertEqual(step.intent, "MODE_SWITCH", f"Intent incorrecto en: '{phrase}'")
            self.assertEqual(step.target, "work", f"Target incorrecto en: '{phrase}'")

    def test_07_nlu_default_mode_and_status_detection(self):
        """Verifica la desactivación de modos y la consulta del modo activo actual."""
        default_phrases = [
            "desactiva los modos",
            "desactivar modo",
            "quita los modos",
            "modo normal",
            "activa el modo normal",
            "restablece el modo general",
        ]
        for phrase in default_phrases:
            pipeline = self.parser.parse(phrase)
            self.assertEqual(len(pipeline.steps), 1, f"Fallo al parsear: '{phrase}'")
            step = pipeline.steps[0]
            self.assertEqual(step.intent, "MODE_SWITCH", f"Intent incorrecto en: '{phrase}'")
            self.assertEqual(step.target, "default", f"Target incorrecto en: '{phrase}'")

        status_phrases = [
            "en que modo estas",
            "que modo esta activo",
            "cual es el modo actual",
            "modo actual",
            "estado del modo",
            "banshee, en que modo estas",
        ]
        for phrase in status_phrases:
            pipeline = self.parser.parse(phrase)
            self.assertEqual(len(pipeline.steps), 1, f"Fallo al parsear: '{phrase}'")
            step = pipeline.steps[0]
            self.assertEqual(step.intent, "MODE_STATUS", f"Intent incorrecto en: '{phrase}'")

    def test_08_os_executor_mode_switch_actions(self):
        """Verifica la ejecución de MODE_SWITCH en OSExecutor con enfoque contextual de ventanas y TTS."""
        executor = OSExecutor()
        executor.window_manager.find_and_focus = MagicMock(return_value=(True, "OK"))
        executor.tts.speak = MagicMock()

        # Activar Modo Trabajo
        step_work = ActionStep(intent="MODE_SWITCH", target="work", parameters=StepParameters())
        pipeline_work = ParsedPipeline(raw_text="activa modo trabajo", steps=[step_work], confidence=1.0)
        res_work = executor.execute_pipeline(pipeline_work)
        self.assertTrue(res_work)
        self.assertTrue(executor.mode_manager.is_work_mode())
        executor.window_manager.find_and_focus.assert_called_with("antigravity")

        # Activar Modo Gamer
        executor.window_manager.find_and_focus.reset_mock()
        step_gamer = ActionStep(intent="MODE_SWITCH", target="gamer", parameters=StepParameters())
        pipeline_gamer = ParsedPipeline(raw_text="activa modo gamer", steps=[step_gamer], confidence=1.0)
        res_gamer = executor.execute_pipeline(pipeline_gamer)
        self.assertTrue(res_gamer)
        self.assertTrue(executor.mode_manager.is_gamer_mode())
        executor.window_manager.find_and_focus.assert_called_with("discord")

    def test_09_os_executor_mode_status(self):
        """Verifica la consulta y locución de estado del modo en OSExecutor."""
        executor = OSExecutor()
        executor.tts.speak = MagicMock()
        executor.mode_manager.set_mode("work")

        step_status = ActionStep(intent="MODE_STATUS", target="mode", parameters=StepParameters())
        pipeline_status = ParsedPipeline(raw_text="en que modo estas", steps=[step_status], confidence=1.0)
        res_status = executor.execute_pipeline(pipeline_status)
        self.assertTrue(res_status)
        self.assertIn("Modo Trabajo", executor.last_action_message)


if __name__ == "__main__":
    unittest.main()
