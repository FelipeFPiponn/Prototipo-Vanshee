import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import unittest
from src.routines.db import init_db
from src.nlu.intent_parser import IntentParser, ActionStep, StepParameters, ParsedPipeline
from src.integrations.git_manager import GitManager, git_manager
from src.executor.os_executor import OSExecutor


class TestGitIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.parser = IntentParser()
        cls.git = GitManager()

    def test_01_git_status_parsing(self):
        """Verifica comandos de estado del repositorio Git."""
        for cmd in ["estado de git", "revisa git", "git status", "revisa el estado de git", "que cambios hay en git"]:
            p = self.parser.parse(cmd)
            self.assertEqual(len(p.steps), 1, f"Fallo en '{cmd}'")
            self.assertEqual(p.steps[0].intent, "GIT_STATUS")
            self.assertEqual(p.steps[0].target, "git")

    def test_02_git_commit_parsing(self):
        """Verifica comandos de commit automático y con mensaje explícito."""
        # Commit automático
        p_auto = self.parser.parse("haz un commit")
        self.assertEqual(len(p_auto.steps), 1)
        self.assertEqual(p_auto.steps[0].intent, "GIT_COMMIT")
        self.assertEqual(p_auto.steps[0].parameters.content, "")

        # Commit con mensaje
        p_msg = self.parser.parse("haz un commit con el mensaje fix: update window snapping")
        self.assertEqual(len(p_msg.steps), 1)
        self.assertEqual(p_msg.steps[0].intent, "GIT_COMMIT")
        self.assertEqual(p_msg.steps[0].parameters.content, "fix: update window snapping")

        # Commit con comillas
        p_quote = self.parser.parse("haz un commit 'feat: add git workflow'")
        self.assertEqual(len(p_quote.steps), 1)
        self.assertEqual(p_quote.steps[0].intent, "GIT_COMMIT")
        self.assertEqual(p_quote.steps[0].parameters.content, "feat: add git workflow")

    def test_03_git_push_pull_diff_branch_parsing(self):
        """Verifica comandos de push, pull, diff y gestión de ramas."""
        p_push = self.parser.parse("sube los cambios a git")
        self.assertEqual(p_push.steps[0].intent, "GIT_PUSH")

        p_pull = self.parser.parse("trae los cambios de git")
        self.assertEqual(p_pull.steps[0].intent, "GIT_PULL")

        p_diff = self.parser.parse("muestra el diff")
        self.assertEqual(p_diff.steps[0].intent, "GIT_DIFF")

        p_branch_cur = self.parser.parse("en que rama estoy")
        self.assertEqual(p_branch_cur.steps[0].intent, "GIT_BRANCH")
        self.assertEqual(p_branch_cur.steps[0].target, "current")

        p_branch_new = self.parser.parse("crea una rama llamada feature-auth")
        self.assertEqual(p_branch_new.steps[0].intent, "GIT_BRANCH")
        self.assertEqual(p_branch_new.steps[0].target, "create")
        self.assertEqual(p_branch_new.steps[0].parameters.content, "feature-auth")

        p_branch_sw = self.parser.parse("cambia a la rama main")
        self.assertEqual(p_branch_sw.steps[0].intent, "GIT_BRANCH")
        self.assertEqual(p_branch_sw.steps[0].target, "switch")
        self.assertEqual(p_branch_sw.steps[0].parameters.content, "main")

    def test_04_compound_git_command(self):
        """Verifica que 'haz un commit y sube los cambios a git' se descomponga en dos pasos."""
        cmd = "haz un commit y sube los cambios a git"
        pipeline = self.parser.parse(cmd)
        self.assertEqual(len(pipeline.steps), 2)
        self.assertEqual(pipeline.steps[0].intent, "GIT_COMMIT")
        self.assertEqual(pipeline.steps[1].intent, "GIT_PUSH")

    def test_05_git_manager_status_mock(self):
        """Verifica el análisis de estado con repositorio limpio y sucio."""
        gm = GitManager()
        with patch.object(gm, "_resolve_workspace_path", return_value="C:\\fake\\repo"):
            # Caso 1: Repositorio limpio
            clean_mock = MagicMock(returncode=0, stdout="## main...origin/main\n")
            with patch.object(gm, "_run_git", return_value=clean_mock):
                success, msg, data = gm.get_status()
                self.assertTrue(success)
                self.assertTrue(data["is_clean"])
                self.assertEqual(data["branch"], "main")
                self.assertIn("limpio", msg)

            # Caso 2: Repositorio modificado
            dirty_mock = MagicMock(
                returncode=0, 
                stdout="## feature/test [ahead 1]\n M src/app.py\n?? test.txt\n"
            )
            with patch.object(gm, "_run_git", return_value=dirty_mock):
                success, msg, data = gm.get_status()
                self.assertTrue(success)
                self.assertFalse(data["is_clean"])
                self.assertEqual(len(data["modified"]), 1)
                self.assertEqual(len(data["untracked"]), 1)
                self.assertEqual(data["ahead"], 1)

    def test_06_git_manager_auto_commit_with_ollama(self):
        """Verifica que auto_commit invoque add, genere commit con Ollama y complete la operación."""
        gm = GitManager()
        status_dirty = (True, "dirty", {"is_clean": False, "branch": "dev"})
        diff_mock = MagicMock(stdout="diff content")
        stat_mock = MagicMock(stdout="M src/code.py")
        commit_mock = MagicMock(returncode=0, stdout="[dev 1234] feat: mock commit")

        with patch.object(gm, "_resolve_workspace_path", return_value="C:\\fake\\repo"), \
             patch.object(gm, "get_status", return_value=status_dirty), \
             patch.object(gm, "_run_git", side_effect=[
                 MagicMock(returncode=0), # git add -A
                 diff_mock,               # git diff --cached
                 stat_mock,               # git status --short
                 commit_mock              # git commit -m
             ]), \
             patch("src.integrations.git_manager.ollama.chat", return_value={"message": {"content": "feat: mock commit"}}):
            
            success, msg = gm.auto_commit()
            self.assertTrue(success)
            self.assertIn("feat: mock commit", msg)
            self.assertIn("dev", msg)

    def test_07_git_manager_branch_operations(self):
        """Verifica la ejecución de creación y cambio de ramas en GitManager."""
        gm = GitManager()
        ok_mock = MagicMock(returncode=0, stdout="")
        with patch.object(gm, "_resolve_workspace_path", return_value="C:\\fake\\repo"), \
             patch.object(gm, "_run_git", return_value=ok_mock):
            
            s1, m1 = gm.branch(action="create", branch_name="fix-issue")
            self.assertTrue(s1)
            self.assertIn("creada y activada", m1)

            s2, m2 = gm.branch(action="switch", branch_name="main")
            self.assertTrue(s2)
            self.assertIn("Cambiado exitosamente", m2)

    def test_08_os_executor_git_execution(self):
        """Verifica que OSExecutor despache acciones GIT_STATUS y GIT_COMMIT correctamente."""
        executor = OSExecutor()
        with patch.object(executor.integration_router.git, "get_status", return_value=(True, "Estado de Git OK", {})):
            step = ActionStep(intent="GIT_STATUS", target="git")
            pipeline = ParsedPipeline(raw_text="estado de git", steps=[step])
            success = executor.execute_pipeline(pipeline)
            self.assertTrue(success)
            self.assertIn("Estado de Git OK", executor.last_action_message)

    def test_09_git_manager_push_with_auto_commit(self):
        """Verifica que push() detecte cambios pendientes y haga auto_commit antes de subir."""
        gm = GitManager()
        status_dirty = (True, "dirty", {"is_clean": False, "branch": "martin"})
        push_ok = MagicMock(returncode=0, stdout="Push success", stderr="")

        with patch.object(gm, "_resolve_workspace_path", return_value="C:\\fake\\repo"), \
             patch.object(gm, "get_current_branch", return_value="martin"), \
             patch.object(gm, "get_status", return_value=status_dirty), \
             patch.object(gm, "auto_commit", return_value=(True, "Commit auto exitoso")) as mock_auto_commit, \
             patch.object(gm, "_run_git", return_value=push_ok):
            
            success, msg = gm.push()
            self.assertTrue(success)
            mock_auto_commit.assert_called_once()
            self.assertIn("Commit auto exitoso", msg)
            self.assertIn("subieron exitosamente", msg)


if __name__ == "__main__":
    unittest.main()
