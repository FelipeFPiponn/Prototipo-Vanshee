import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import unittest
from src.routines.db import init_db
from src.executor.window_manager import WindowManager
from src.executor.search_registry import SearchProviderRegistry, SearchProvider
from src.executor.os_executor import OSExecutor
from src.nlu.intent_parser import ActionStep, StepParameters, ParsedPipeline


class TestWindowPrioritizationAndSearchRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.wm = WindowManager()
        cls.registry = SearchProviderRegistry()

    def test_01_window_manager_enumeration(self):
        """Verifica que WindowManager enumere las ventanas visibles sin errores."""
        windows = self.wm.get_open_windows()
        self.assertIsInstance(windows, list)
        for w in windows:
            self.assertIn("hwnd", w)
            self.assertIn("title", w)
            self.assertTrue(len(w["title"]) > 0)

    def test_02_search_provider_registry_defaults(self):
        """Verifica que los proveedores predeterminados estén registrados con sus reglas."""
        spotify_p = self.registry.get_provider("spotify")
        self.assertIsNotNone(spotify_p)
        self.assertTrue(spotify_p.prefer_desktop)
        self.assertEqual(spotify_p.app_uri, "spotify:search:{query}")

        yt_p = self.registry.get_provider("youtube")
        self.assertIsNotNone(yt_p)
        self.assertIn("{query}", yt_p.web_url)

        steam_p = self.registry.get_provider("steam")
        self.assertIsNotNone(steam_p)
        self.assertTrue(steam_p.prefer_desktop)

    def test_03_protocol_detection(self):
        """Verifica la detección de protocolos nativos en el Registro de Windows."""
        self.assertTrue(self.registry.is_protocol_registered("spotify:search:{query}"))
        self.assertFalse(self.registry.is_protocol_registered("protocolofalsoinexistente12345:"))

    def test_04_save_and_load_learned_provider(self):
        """Verifica que se puedan aprender y persistir nuevos proveedores en SQLite."""
        test_provider = SearchProvider(
            id="testapp",
            name="TestApp",
            aliases=["testapp", "prueba"],
            app_uri="testapp://search?q={query}",
            web_url="https://testapp.com/search?q={query}",
            prefer_desktop=True
        )
        self.registry.save_learned_provider(test_provider)
        
        # Recargar registro desde DB
        new_registry = SearchProviderRegistry()
        loaded = new_registry.get_provider("testapp")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "TestApp")
        self.assertEqual(loaded.app_uri, "testapp://search?q={query}")

    @patch("os.startfile")
    def test_05_spotify_search_uses_desktop_protocol_and_cleans_query(self, mock_startfile):
        """Verifica que la búsqueda en Spotify use protocolo nativo con espacios limpios y sin 'canciones de'."""
        with patch("webbrowser.open_new_tab") as mock_browser:
            success, msg = self.registry.dispatch_search(
                target="spotify",
                query="canciones de Lana del Rey",
                window_manager=self.wm
            )
            self.assertTrue(success)
            self.assertIn("Spotify", msg)
            self.assertIn("Lana del Rey", msg)
            # Debe invocar os.startfile con espacios limpios (sin '+' ni '%20') y sin 'canciones de'
            mock_startfile.assert_called_once_with("spotify:search:Lana del Rey")
            # NO debe abrir pestaña de navegador
            mock_browser.assert_not_called()

    def test_06_youtube_search_tab_reuse(self):
        """Verifica que si existe una ventana de YouTube abierta, se reutilice la pestaña navegando en ella."""
        fake_window = {"hwnd": 12345, "title": "YouTube - Brave", "pid": 9999, "rect": (0, 0, 800, 600)}
        mock_wm = MagicMock(spec=WindowManager)
        mock_wm.find_window.return_value = fake_window
        mock_wm.focus_window.return_value = True
        mock_wm.navigate_active_browser_tab.return_value = True

        with patch("webbrowser.open_new_tab") as mock_browser:
            success, msg = self.registry.dispatch_search(
                target="youtube",
                query="videos de Monster Hunter",
                window_manager=mock_wm
            )
            self.assertTrue(success)
            self.assertIn("Reutilizando pestaña", msg)
            mock_wm.focus_window.assert_called_once_with(12345)
            # Debe haber navegado con query limpia 'Monster%20Hunter' (sin 'videos de')
            mock_wm.navigate_active_browser_tab.assert_called_once_with("https://www.youtube.com/results?search_query=Monster%20Hunter")
            mock_browser.assert_not_called()

    def test_07_launch_target_prioritizes_open_window(self):
        """Verifica que _launch_target traiga al frente una ventana si ya está abierta y no abra nueva pestaña."""
        fake_win = {"hwnd": 54321, "title": "YouTube - Google Chrome", "pid": 8888, "rect": (0, 0, 800, 600)}
        executor = OSExecutor()
        executor.window_manager.find_window = MagicMock(return_value=fake_win)
        executor.window_manager.focus_window = MagicMock(return_value=True)

        with patch("webbrowser.open_new_tab") as mock_browser, patch("subprocess.Popen") as mock_popen:
            res = executor._launch_target("youtube")
            self.assertTrue(res)
            self.assertIn("ya estaba abierto", executor.last_action_message)
            executor.window_manager.focus_window.assert_called_once_with(54321)
            mock_browser.assert_not_called()
            mock_popen.assert_not_called()

    def test_08_end_to_end_search_pipeline(self):
        """Verifica el flujo completo a través de execute_pipeline con SEARCH_CONTENT."""
        executor = OSExecutor()
        step = ActionStep(
            intent="SEARCH_CONTENT",
            target="spotify",
            parameters=StepParameters(content="canciones de Imagine Dragons")
        )
        pipeline = ParsedPipeline(raw_text="busca canciones de imagine dragons en spotify", steps=[step])

        with patch("os.startfile") as mock_startfile, patch("webbrowser.open_new_tab") as mock_browser:
            success = executor.execute_pipeline(pipeline)
            self.assertTrue(success)
            self.assertIn("Spotify", executor.last_action_message)
            self.assertIn("Imagine Dragons", executor.last_action_message)
            mock_startfile.assert_called_once_with("spotify:search:Imagine Dragons")
            mock_browser.assert_not_called()

    def test_09_intent_parser_fast_search_query_cleaning(self):
        """Verifica que IntentParser elimine 'canciones de' y 'videos de' determinísticamente."""
        from src.nlu.intent_parser import IntentParser
        parser = IntentParser()

        p1 = parser.parse("busca canciones de Lana del Rey en Spotify")
        self.assertEqual(len(p1.steps), 1)
        self.assertEqual(p1.steps[0].intent, "SEARCH_CONTENT")
        self.assertEqual(p1.steps[0].target, "spotify")
        self.assertEqual(p1.steps[0].parameters.content, "Lana del Rey")

        p2 = parser.parse("busca videos de Monster Hunter en YouTube")
        self.assertEqual(len(p2.steps), 1)
        self.assertEqual(p2.steps[0].intent, "SEARCH_CONTENT")
        self.assertEqual(p2.steps[0].target, "youtube")
        self.assertEqual(p2.steps[0].parameters.content, "Monster Hunter")


if __name__ == "__main__":
    unittest.main(verbosity=2)
