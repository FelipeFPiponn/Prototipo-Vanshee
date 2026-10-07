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
        """Verifica la resolución dinámica de aplicaciones, alias y juegos de Steam."""
        resolver = DynamicResolver()
        target, ttype = resolver.resolve("vscode")
        self.assertIsNotNone(target, "vscode debe resolverse a una ejecutable o alias.")
        
        target_chrome, ttype_chrome = resolver.resolve("chrome")
        self.assertIsNotNone(target_chrome, "chrome debe resolverse.")

        # Verificación de auto-resolución dinámica de Steam (Warframe)
        target_steam, ttype_steam = resolver.resolve("warframe")
        self.assertIsNotNone(target_steam, "Warframe debe resolverse dinámicamente como juego de Steam.")
        self.assertEqual(ttype_steam, "protocol", "El tipo de destino para juegos de Steam debe ser 'protocol'.")
        self.assertTrue(str(target_steam).startswith("steam://rungameid/"), "La URI debe ser del protocolo steam://rungameid/.")

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

    def test_06_media_control(self):
        """Verifica la interpretación y ejecución de comandos multimedia."""
        parser = IntentParser()
        p_pause = parser.parse("Banshee, pausa la música de Spotify.")
        self.assertTrue(len(p_pause.steps) > 0, "Debe generar al menos un paso para pausar música.")
        self.assertEqual(p_pause.steps[0].intent, "MEDIA_CONTROL")
        self.assertEqual(p_pause.steps[0].target, "pause")

        p_next = parser.parse("siguiente canción")
        self.assertEqual(p_next.steps[0].intent, "MEDIA_CONTROL")
        self.assertEqual(p_next.steps[0].target, "next")

        p_vol = parser.parse("sube el volumen")
        self.assertEqual(p_vol.steps[0].intent, "MEDIA_CONTROL")
        self.assertEqual(p_vol.steps[0].target, "volume_up")

    def test_07_agent_prompt_writing(self):
        """Verifica la interpretación de comandos para enviar prompts a agentes de código (Antigravity, Cursor, etc.)."""
        parser = IntentParser()
        p_prompt = parser.parse("Banshee, abre Antigravity y pon el siguiente prompt. Escribe hola mundo.")
        self.assertEqual(len(p_prompt.steps), 2, "Debe generar 2 pasos: abrir app y escribir prompt.")
        self.assertEqual(p_prompt.steps[0].intent, "OPEN_APP")
        self.assertEqual(p_prompt.steps[0].target, "antigravity")
        self.assertEqual(p_prompt.steps[1].intent, "WRITE_TEXT")
        self.assertIn("hola mundo", p_prompt.steps[1].parameters.content)

        p_direct = parser.parse("escribe el siguiente prompt: crea una función fibonacci")
        self.assertEqual(p_direct.steps[0].intent, "WRITE_TEXT")
        self.assertIn("fibonacci", p_direct.steps[0].parameters.content)

    def test_08_search_brand_and_lucky_link(self):
        """Verifica la resolución de SoloTodo y preservación de marcas compuestas sin descartar 'solo'."""
        resolver = DynamicResolver()
        target_solotodo, ttype_solotodo = resolver.resolve("solotodo")
        self.assertEqual(target_solotodo, "https://www.solotodo.cl")
        self.assertEqual(ttype_solotodo, "url")

        target_solo_todo, ttype_solo_todo = resolver.resolve("solo todo")
        self.assertEqual(target_solo_todo, "https://www.solotodo.cl")

        parser = IntentParser()
        p = parser.parse("Banshee, busca solo todo en el navegador y abre el primer link.")
        self.assertTrue(len(p.steps) > 0)
        self.assertEqual(p.steps[0].intent, "SEARCH_CONTENT")
        self.assertEqual(p.steps[0].parameters.content, "solo todo")

if __name__ == "__main__":
    unittest.main(verbosity=2)
