import sys
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import unittest
from src.routines.db import init_db
from src.integrations.file_manager import FileManager, file_manager
from src.nlu.intent_parser import IntentParser, ActionStep, StepParameters, ParsedPipeline
from src.executor.os_executor import OSExecutor


class TestFileAndFolderCreation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.parser = IntentParser()
        cls.test_dir = ROOT / "data" / "test_scratch_files"
        cls.test_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        self.fm = FileManager()

    def test_01_file_manager_create_folder(self):
        """Verifica la creación de carpetas en una ubicación específica."""
        with patch("subprocess.Popen") as mock_popen:
            ok, msg, path = self.fm.create_folder(
                folder_name="proyecto_alpha",
                location=str(self.test_dir),
                open_after=True
            )
            self.assertTrue(ok)
            self.assertTrue(path.exists())
            self.assertTrue(path.is_dir())
            self.assertIn("proyecto_alpha", path.name)
            mock_popen.assert_called_once()

    def test_02_file_manager_create_folder_conflict_resolution(self):
        """Verifica que carpetas con el mismo nombre no se sobrescriban y generen sufijo."""
        ok1, _, path1 = self.fm.create_folder("docs", location=str(self.test_dir))
        ok2, _, path2 = self.fm.create_folder("docs", location=str(self.test_dir))
        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertNotEqual(path1, path2)
        self.assertTrue(path2.name.startswith("docs_"))

    def test_03_file_manager_create_notepad(self):
        """Verifica la creación de notas .txt y el lanzamiento de notepad.exe."""
        with patch("subprocess.Popen") as mock_popen:
            ok, msg, path = self.fm.create_notepad(
                note_name="lista_compras",
                content="1. Leche\n2. Café",
                location=str(self.test_dir),
                open_notepad=True
            )
            self.assertTrue(ok)
            self.assertTrue(path.exists())
            self.assertTrue(path.name.endswith(".txt"))
            content = path.read_text(encoding="utf-8")
            self.assertIn("Leche", content)
            mock_popen.assert_called_once_with(["notepad.exe", str(path)])

    def test_04_file_manager_create_code_file_with_template(self):
        """Verifica la creación de archivos de código con plantillas iniciales por defecto."""
        ok_py, _, py_path = self.fm.create_file(
            file_name="script_demo",
            language="python",
            location=str(self.test_dir)
        )
        self.assertTrue(ok_py)
        self.assertTrue(py_path.name.endswith(".py"))
        py_content = py_path.read_text(encoding="utf-8")
        self.assertIn("def main()", py_content)

        ok_html, _, html_path = self.fm.create_file(
            file_name="index",
            language="html",
            location=str(self.test_dir)
        )
        self.assertTrue(ok_html)
        self.assertTrue(html_path.name.endswith(".html"))
        html_content = html_path.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", html_content)

    def test_05_nlu_folder_creation_parsing(self):
        """Verifica el parseo NLU determinista de creación de carpetas."""
        phrases = [
            ("crea una carpeta llamada proyectos", "proyectos", ""),
            ("crea la carpeta tareas", "tareas", ""),
            ("nueva carpeta viajes", "viajes", ""),
            ("crea una nueva carpeta llamada fotos", "fotos", ""),
            ("crea una carpeta proyectos en el escritorio", "proyectos", "escritorio"),
            ("crea una carpeta notas en documentos y ábrela", "notas", "documentos"),
            ("banshee, crea una carpeta llamada codigo", "codigo", ""),
        ]
        for phrase, expected_name, expected_loc in phrases:
            pipeline = self.parser.parse(phrase)
            self.assertEqual(len(pipeline.steps), 1, f"Fallo al parsear: '{phrase}'")
            step = pipeline.steps[0]
            self.assertEqual(step.intent, "CREATE_FOLDER", f"Intent incorrecto en: '{phrase}'")
            self.assertEqual(step.parameters.file_name, expected_name, f"Nombre incorrecto en: '{phrase}'")
            if expected_loc:
                self.assertEqual(step.parameters.path, expected_loc, f"Ubicación incorrecta en: '{phrase}'")

    def test_06_nlu_notepad_creation_parsing(self):
        """Verifica el parseo NLU determinista de creación de Bloc de notas."""
        phrases = [
            ("crea un bloc de notas llamado ideas", "ideas.txt", ""),
            ("crea un block de notas llamado notas", "notas.txt", ""),
            ("crea un bloc de notas en el escritorio", "", "escritorio"),
            ("crea una nota llamada recordatorio", "recordatorio.txt", ""),
            ("crea un bloc de notas que diga comprar pan", "", ""),
            ("crea un bloc de notas con el texto reunión mañana", "", ""),
            ("banshee, crea un bloc de notas llamado lista", "lista.txt", ""),
        ]
        for phrase, expected_name, expected_loc in phrases:
            pipeline = self.parser.parse(phrase)
            self.assertEqual(len(pipeline.steps), 1, f"Fallo al parsear: '{phrase}'")
            step = pipeline.steps[0]
            self.assertEqual(step.intent, "CREATE_FILE", f"Intent incorrecto en: '{phrase}'")
            self.assertEqual(step.target, "notepad", f"Target incorrecto en: '{phrase}'")
            if expected_name:
                self.assertEqual(step.parameters.file_name, expected_name, f"Nombre incorrecto en: '{phrase}'")
            if expected_loc:
                self.assertEqual(step.parameters.path, expected_loc, f"Ubicación incorrecta en: '{phrase}'")

    def test_07_nlu_open_notepad_app_vs_create_file(self):
        """Verifica que 'abre el bloc de notas' se reconozca como OPEN_APP y no como creación de archivo."""
        p_open = self.parser.parse("abre el bloc de notas")
        self.assertEqual(p_open.steps[0].intent, "OPEN_APP")
        self.assertIn("bloc de notas", p_open.steps[0].target.lower())

        p_create = self.parser.parse("crea un bloc de notas")
        self.assertEqual(p_create.steps[0].intent, "CREATE_FILE")
        self.assertEqual(p_create.steps[0].target, "notepad")

    def test_08_nlu_code_file_creation_parsing(self):
        """Verifica el parseo NLU determinista de archivos de código."""
        phrases = [
            ("crea un archivo llamado script.py", "script.py", "txt"),
            ("crea un archivo python llamado test", "test", "python"),
            ("crea un archivo index.html", "index.html", "txt"),
            ("crea un archivo llamado config.json", "config.json", "txt"),
            ("nuevo archivo app.js", "app.js", "txt"),
            ("banshee, crea un archivo de texto llamado lista.txt", "lista.txt", "txt"),
        ]
        for phrase, expected_name, _ in phrases:
            pipeline = self.parser.parse(phrase)
            self.assertEqual(len(pipeline.steps), 1, f"Fallo al parsear: '{phrase}'")
            step = pipeline.steps[0]
            self.assertEqual(step.intent, "CREATE_FILE", f"Intent incorrecto en: '{phrase}'")
            self.assertIn(expected_name, step.parameters.file_name)

    def test_09_os_executor_folder_and_file_actions(self):
        """Verifica la ejecución en OSExecutor invocando FileManager con voz."""
        executor = OSExecutor()
        executor.tts.speak = MagicMock()

        with patch.object(executor.file_manager, "create_folder") as mock_folder, \
             patch.object(executor.file_manager, "create_notepad") as mock_notepad:

            mock_folder.return_value = (True, "Carpeta 'test' creada con éxito.", Path("dummy"))
            mock_notepad.return_value = (True, "Bloc de notas 'notas.txt' creado.", Path("dummy.txt"))

            # Ejecutar creación de carpeta
            step_folder = ActionStep(intent="CREATE_FOLDER", target="folder", parameters=StepParameters(file_name="test"))
            res_f = executor.execute_pipeline(ParsedPipeline(raw_text="crea carpeta test", steps=[step_folder]))
            self.assertTrue(res_f)
            mock_folder.assert_called_once()
            self.assertIn("creada", executor.last_action_message)

            # Ejecutar creación de bloc de notas
            step_note = ActionStep(intent="CREATE_FILE", target="notepad", parameters=StepParameters(file_name="notas.txt"))
            res_n = executor.execute_pipeline(ParsedPipeline(raw_text="crea bloc de notas", steps=[step_note]))
            self.assertTrue(res_n)
            mock_notepad.assert_called_once()
            self.assertIn("creado", executor.last_action_message)


if __name__ == "__main__":
    unittest.main()
