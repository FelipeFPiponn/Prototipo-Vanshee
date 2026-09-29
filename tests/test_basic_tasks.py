import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import unittest
from src.routines.db import init_db
from config.settings import settings
from src.memory_store import MemoryStore
from src.semantic_memory import SemanticMemory
from src.executor.dynamic_resolver import DynamicResolver
from src.nlu.intent_parser import IntentParser
from src.context_awareness import ContextAwarenessEngine
from src.audio.tts_engine import TTSEngine

class TestVansheeBasicTasks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_database_and_memory(self):
        """Verifica la base de datos, guardado de hechos e interacciones en memoria."""
        memory = MemoryStore()
        memory.remember_fact("test_key", "test_value", source="test", confidence=0.99)
        val = memory.recall_fact("test_key")
        self.assertEqual(val, "test_value", "El valor guardado en memoria debe coincidir.")

        sem_memory = SemanticMemory()
        sem_memory.remember("abrir navegador chrome", kind="successful_command", importance=0.9, success=True)
        matches = sem_memory.search("navegador")
        self.assertTrue(isinstance(matches, list), "SemanticMemory debe devolver una lista de coincidencias.")

    def test_02_dynamic_resolver(self):
        """Verifica la resolución dinámica de aplicaciones y alias."""
        resolver = DynamicResolver()
        target, ttype = resolver.resolve("vscode")
        self.assertIsNotNone(target, "vscode debe resolverse a una ejecutable o alias.")
        
        target_chrome, ttype_chrome = resolver.resolve("chrome")
        self.assertIsNotNone(target_chrome, "chrome debe resolverse.")

    def test_03_nlu_intent_parser(self):
        """Verifica la interpretación de intenciones por el motor NLU (Ollama Llama 3.2)."""
        parser = IntentParser()
        pipeline = parser.parse("abrir vscode")
        self.assertTrue(len(pipeline.steps) > 0, "El NLU debe generar al menos un paso para 'abrir vscode'.")
        self.assertIn("OPEN_APP", pipeline.steps[0].intent.upper(), "El paso debe ser OPEN_APP.")

        pipeline_proj = parser.parse("crear proyecto python llamado demo_test")
        self.assertTrue(len(pipeline_proj.steps) > 0, "El NLU debe interpretar 'crear proyecto'.")

    def test_04_context_awareness(self):
        """Verifica la observación del contexto del sistema operativo."""
        engine = ContextAwarenessEngine()
        snapshot = engine.observe(action_hint="testing")
        self.assertIsNotNone(snapshot, "ContextAwarenessEngine debe retornar un ContextSnapshot.")
        self.assertIsNotNone(snapshot.window_title, "El snapshot debe tener un título de ventana.")

    def test_05_tts_engine(self):
        """Verifica la inicialización del motor TTS sin errores."""
        tts = TTSEngine()
        self.assertTrue(hasattr(tts, "speak"), "El motor TTS debe poseer el método speak.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
