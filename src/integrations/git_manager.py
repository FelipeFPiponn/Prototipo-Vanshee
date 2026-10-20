"""Módulo de Integración con Git y Flujo de Commits Automáticos para V.ANSHEE.

Permite consultar estado, inspeccionar diffs, generar commits semánticos automáticos con Ollama,
crear/cambiar ramas y sincronizar con repositorios remotos.
"""

import os
import re
import shutil
import subprocess
from typing import Tuple, Dict, Any, Optional
from pathlib import Path

try:
    import ollama
except ImportError:
    ollama = None

try:
    from config.settings import settings
except ImportError:
    settings = None

try:
    from src.integrations.editor_hub import editor_hub
except ImportError:
    editor_hub = None


class GitManager:
    """Gestiona el flujo de trabajo de Git y la generación de commits automatizados."""

    def __init__(self):
        self._git_binary = self._resolve_git_binary()

    def _resolve_git_binary(self) -> str:
        """Encuentra el binario de Git en PATH o ubicaciones estándar de Windows / WinGet."""
        found = shutil.which("git")
        if found:
            return found
        import glob
        home = os.path.expanduser("~")
        candidates = [
            *glob.glob(os.path.join(home, "AppData", "Local", "Microsoft", "WinGet", "Packages", "Git.MinGit*", "cmd", "git.exe")),
            *glob.glob(os.path.join(home, "AppData", "Local", "Programs", "Git", "bin", "git.exe")),
            "C:\\Program Files\\Git\\cmd\\git.exe",
            "C:\\Program Files\\Git\\bin\\git.exe",
            "C:\\Program Files (x86)\\Git\\cmd\\git.exe"
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return "git"

    def _resolve_workspace_path(self, override_path: str = "") -> Optional[str]:
        """Detecta la ruta del repositorio Git activo según el editor conectado o el sistema."""
        if override_path and os.path.isdir(override_path):
            root = self._find_git_root(override_path)
            if root:
                return root

        # 1. Priorizar workspace_root del editor activo reportado por vanshee-editor-bridge
        if editor_hub:
            try:
                session = editor_hub.get_active_session()
                if session:
                    if session.workspace_root and os.path.isdir(session.workspace_root):
                        root = self._find_git_root(session.workspace_root)
                        if root:
                            return root
                    if session.active_file and os.path.exists(session.active_file):
                        root = self._find_git_root(os.path.dirname(session.active_file))
                        if root:
                            return root
            except Exception:
                pass

        # 2. Directorio de trabajo actual
        cwd = os.getcwd()
        root = self._find_git_root(cwd)
        if root:
            return root

        # 3. Raíz del proyecto vanshee-core como fallback
        project_root = Path(__file__).resolve().parent.parent.parent
        if os.path.isdir(project_root):
            root = self._find_git_root(str(project_root))
            if root:
                return root

        return None

    def _find_git_root(self, start_dir: str) -> Optional[str]:
        """Busca la raíz del repositorio Git ejecutando git rev-parse."""
        try:
            res = subprocess.run(
                [self._git_binary, "rev-parse", "--show-toplevel"],
                cwd=start_dir,
                capture_output=True,
                text=True,
                timeout=3,
                check=False
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip().replace("/", os.sep)
        except Exception:
            pass
        return None

    def _run_git(self, args: list[str], cwd: str, timeout: int = 20) -> subprocess.CompletedProcess:
        """Ejecuta un comando git de forma controlada y con decodificación utf-8."""
        return subprocess.run(
            [self._git_binary] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False
        )

    def get_current_branch(self, workspace: str = "") -> str:
        """Retorna el nombre de la rama actual."""
        ws = self._resolve_workspace_path(workspace)
        if not ws:
            return ""
        res = self._run_git(["branch", "--show-current"], cwd=ws)
        if res.returncode == 0:
            return res.stdout.strip()
        return "main"

    def get_status(self, workspace: str = "") -> Tuple[bool, str, Dict[str, Any]]:
        """Analiza el estado actual del repositorio Git en lenguaje natural y estructurado."""
        ws = self._resolve_workspace_path(workspace)
        if not ws:
            return False, "No detecté ningún repositorio Git activo en el editor o directorio actual.", {}

        res = self._run_git(["status", "--porcelain=v1", "-b"], cwd=ws)
        if res.returncode != 0:
            return False, f"Error al ejecutar git status: {res.stderr.strip()}", {}

        lines = [line for line in res.stdout.splitlines() if line.strip()]
        branch = "main"
        ahead = 0
        behind = 0
        staged = []
        modified = []
        untracked = []

        for line in lines:
            if line.startswith("##"):
                b_info = line[2:].strip()
                # Extraer nombre de la rama
                m_branch = re.match(r"^([^\.\s]+)", b_info)
                if m_branch:
                    branch = m_branch.group(1)
                m_ahead = re.search(r"ahead\s+(\d+)", b_info)
                if m_ahead:
                    ahead = int(m_ahead.group(1))
                m_behind = re.search(r"behind\s+(\d+)", b_info)
                if m_behind:
                    behind = int(m_behind.group(1))
            else:
                x = line[0] if len(line) > 0 else " "
                y = line[1] if len(line) > 1 else " "
                file_name = line[3:].strip() if len(line) > 3 else line.strip()

                if x in "MADRC":
                    staged.append(file_name)
                if y in "MD":
                    modified.append(file_name)
                elif line.startswith("??"):
                    untracked.append(file_name)

        is_clean = len(staged) == 0 and len(modified) == 0 and len(untracked) == 0
        data = {
            "branch": branch,
            "ahead": ahead,
            "behind": behind,
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
            "is_clean": is_clean,
            "workspace": ws
        }

        repo_name = os.path.basename(ws)
        if is_clean:
            msg = f"El repositorio '{repo_name}' está limpio en la rama '{branch}'."
            if ahead > 0:
                msg += f" Tienes {ahead} commit(s) pendientes de subir (push)."
            return True, msg, data

        details = []
        if staged:
            details.append(f"{len(staged)} archivo(s) preparados en stage")
        if modified:
            details.append(f"{len(modified)} archivo(s) modificados")
        if untracked:
            details.append(f"{len(untracked)} archivo(s) nuevos sin seguimiento")

        summary = ", ".join(details)
        msg = f"Rama '{branch}' en '{repo_name}': {summary}."
        if ahead > 0:
            msg += f" ({ahead} commit(s) pendientes de subir)."
        return True, msg, data

    def _generate_commit_message_with_ollama(self, diff_sample: str, stat_sample: str) -> str:
        """Solicita a Ollama un mensaje de commit semántico bajo Conventional Commits."""
        if not ollama or not settings or not getattr(settings, "OLLAMA_MODEL", None):
            return ""

        prompt = (
            "Eres un ingeniero de software senior experto en Git. Analiza los cambios en este repositorio "
            "y redacta un mensaje de commit convencional conciso (Conventional Commits: feat, fix, refactor, docs, chore, test) "
            "en español o inglés.\n\n"
            f"Archivos cambiados:\n{stat_sample}\n\n"
            f"Diff resumido:\n{diff_sample[:3000]}\n\n"
            "REGLAS OBLIGATORIAS:\n"
            "1. Responde ÚNICAMENTE con la línea del commit (ejemplo: 'feat: add git automation flow').\n"
            "2. Máximo 72 caracteres.\n"
            "3. NO incluyas explicaciones, NO uses comillas, NO uses formato markdown."
        )

        try:
            resp = ollama.chat(
                model=settings.OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.2}
            )
            raw = resp.get("message", {}).get("content", "").strip()
            # Limpiar posibles comillas o prefijos de markdown
            clean = re.sub(r"^[`'\"]+|[`'\"]+$", "", raw).strip()
            # Tomar solo la primera línea si generó múltiples
            clean = clean.splitlines()[0].strip() if clean else ""
            if clean and len(clean) <= 100:
                return clean
        except Exception as e:
            print(f"[GitManager Ollama Warning] No se pudo generar commit con LLM: {e}")

        return ""

    def _fallback_commit_message(self, stat_sample: str) -> str:
        """Genera un mensaje de commit heurístico cuando Ollama no está disponible."""
        lines = [ln.strip() for ln in stat_sample.splitlines() if ln.strip()]
        if not lines:
            return "chore: update repository changes"

        files = [re.sub(r"^[MADRC\?]+\s+", "", ln).strip() for ln in lines]
        first_file = os.path.basename(files[0]) if files else ""

        # Si son tests
        if all("test" in f.lower() for f in files):
            return f"test: update {first_file}" if len(files) == 1 else "test: update test suite"

        # Si son docs
        if all(f.lower().endswith(".md") or "doc" in f.lower() for f in files):
            return "docs: update documentation"

        # Si es el bridge de extensión
        if any("extension.ts" in f or "editor-bridge" in f for f in files):
            return "feat(editor): update editor integration"

        # Si es un solo archivo
        if len(files) == 1:
            return f"feat: update {first_file}"

        return f"chore: update {len(files)} modified files"

    def auto_commit(self, custom_message: str = "", workspace: str = "") -> Tuple[bool, str]:
        """Añade los cambios al stage y realiza un commit con mensaje convencional automático o personalizado."""
        ws = self._resolve_workspace_path(workspace)
        if not ws:
            return False, "No se detectó un repositorio Git activo para hacer commit."

        success, _, status_data = self.get_status(ws)
        if not success:
            return False, "No se pudo leer el estado del repositorio Git."

        if status_data.get("is_clean", False):
            return False, f"No hay cambios pendientes para hacer commit en la rama '{status_data.get('branch', 'main')}'."

        # 1. Agregar todos los cambios al stage
        add_res = self._run_git(["add", "-A"], cwd=ws)
        if add_res.returncode != 0:
            return False, f"Error al preparar archivos con git add: {add_res.stderr.strip()}"

        # 2. Determinar mensaje de commit
        commit_msg = (custom_message or "").strip()
        if not commit_msg:
            diff_proc = self._run_git(["diff", "--cached"], cwd=ws)
            stat_proc = self._run_git(["status", "--short"], cwd=ws)
            diff_text = diff_proc.stdout
            stat_text = stat_proc.stdout

            # Intentar generar mensaje semántico con Ollama
            commit_msg = self._generate_commit_message_with_ollama(diff_text, stat_text)
            if not commit_msg:
                commit_msg = self._fallback_commit_message(stat_text)

        # 3. Ejecutar git commit
        res = self._run_git(["commit", "-m", commit_msg], cwd=ws)
        if res.returncode == 0:
            branch = status_data.get("branch", "main")
            return True, f"Commit realizado con éxito en '{branch}': '{commit_msg}'."
        else:
            err = res.stderr.strip() or res.stdout.strip()
            return False, f"No se pudo completar el commit: {err}"

    def push(self, workspace: str = "", auto_commit_if_dirty: bool = True) -> Tuple[bool, str]:
        """Sube los commits locales al repositorio remoto. Si hay cambios locales sin commit, los empaqueta automáticamente."""
        ws = self._resolve_workspace_path(workspace)
        if not ws:
            return False, "No se detectó un repositorio Git activo para hacer push."

        branch = self.get_current_branch(ws)

        # 1. Verificar si hay cambios pendientes sin commit
        commit_created = False
        commit_desc = ""
        success_stat, _, status_data = self.get_status(ws)
        if success_stat and not status_data.get("is_clean", True):
            if auto_commit_if_dirty:
                print(f"[GitManager Push] Se detectaron cambios pendientes sin commit en '{branch}'. Realizando auto_commit previo...")
                commit_ok, commit_msg = self.auto_commit(workspace=ws)
                if commit_ok:
                    commit_created = True
                    commit_desc = commit_msg
                else:
                    return False, f"No se pudieron guardar los cambios antes de hacer push: {commit_msg}"
            else:
                return False, f"Tienes cambios locales pendientes sin guardar en '{branch}'. Haz un commit antes de subir."

        # 2. Ejecutar git push
        res = self._run_git(["push"], cwd=ws, timeout=60)

        # Si no tiene upstream configurado (rama nueva remota)
        if res.returncode != 0 and ("no upstream branch" in res.stderr.lower() or "set-upstream" in res.stderr.lower()):
            res_up = self._run_git(["push", "-u", "origin", branch], cwd=ws, timeout=60)
            if res_up.returncode == 0:
                if commit_created:
                    return True, f"Se guardaron los cambios con commit y la rama '{branch}' se subió y vinculó al repositorio remoto con éxito."
                return True, f"Rama '{branch}' subida y vinculada al repositorio remoto correctamente."
            return False, f"Error al subir cambios con upstream: {res_up.stderr.strip()}"

        if res.returncode == 0:
            out = (res.stdout.strip() + " " + res.stderr.strip()).lower()
            if commit_created:
                return True, f"Se guardaron los cambios ({commit_desc}) y se subieron exitosamente al repositorio remoto en la rama '{branch}'."
            if "everything up-to-date" in out or "todo actualizado" in out:
                return True, f"El repositorio remoto en la rama '{branch}' ya está al día. No había commits pendientes."
            return True, f"Cambios subidos exitosamente al repositorio remoto en la rama '{branch}'."

        return False, f"Error al subir cambios (git push): {res.stderr.strip()}"

    def pull(self, workspace: str = "") -> Tuple[bool, str]:
        """Descarga e integra los cambios más recientes desde el repositorio remoto."""
        ws = self._resolve_workspace_path(workspace)
        if not ws:
            return False, "No se detectó un repositorio Git activo para hacer pull."

        res = self._run_git(["pull"], cwd=ws, timeout=60)
        if res.returncode == 0:
            out = res.stdout.strip()
            if "already up to date" in out.lower() or "ya está actualizado" in out.lower():
                return True, "El repositorio ya está al día. No hay cambios nuevos."
            return True, f"Repositorio actualizado correctamente con los cambios remotos."
        return False, f"Error al actualizar desde el repositorio remoto: {res.stderr.strip()}"

    def get_diff(self, workspace: str = "") -> Tuple[bool, str]:
        """Muestra un resumen de las modificaciones pendientes en el árbol de trabajo."""
        ws = self._resolve_workspace_path(workspace)
        if not ws:
            return False, "No se detectó un repositorio Git activo."

        res = self._run_git(["diff", "--stat"], cwd=ws)
        diff_out = res.stdout.strip()
        if not diff_out:
            # Revisar si los cambios están en stage
            res_staged = self._run_git(["diff", "--cached", "--stat"], cwd=ws)
            diff_out = res_staged.stdout.strip()

        if not diff_out:
            return True, "No hay diferencias ni modificaciones pendientes en los archivos rastreados."

        lines = diff_out.splitlines()
        last_line = lines[-1] if lines else ""
        return True, f"Diferencias actuales en Git: {last_line}. Archivos: {len(lines) - 1} modificado(s)."

    def branch(self, action: str = "current", branch_name: str = "", workspace: str = "") -> Tuple[bool, str]:
        """Consulta, crea o cambia de rama en el repositorio activo."""
        ws = self._resolve_workspace_path(workspace)
        if not ws:
            return False, "No se detectó un repositorio Git activo."

        act = action.lower().strip()
        b_name = branch_name.strip()

        if act in ["current", "list", ""]:
            current = self.get_current_branch(ws)
            res = self._run_git(["branch", "--list"], cwd=ws)
            total = len([ln for ln in res.stdout.splitlines() if ln.strip()])
            return True, f"Estás en la rama '{current}'. Hay {total} rama(s) locales en este repositorio."

        elif act in ["create", "new"]:
            if not b_name:
                return False, "Debes indicar el nombre de la nueva rama a crear."
            res = self._run_git(["checkout", "-b", b_name], cwd=ws)
            if res.returncode == 0:
                return True, f"Nueva rama '{b_name}' creada y activada con éxito."
            return False, f"No se pudo crear la rama '{b_name}': {res.stderr.strip()}"

        elif act in ["switch", "checkout", "change"]:
            if not b_name:
                return False, "Debes indicar el nombre de la rama a la que deseas cambiar."
            res = self._run_git(["checkout", b_name], cwd=ws)
            if res.returncode == 0:
                return True, f"Cambiado exitosamente a la rama '{b_name}'."
            return False, f"No se pudo cambiar a la rama '{b_name}': {res.stderr.strip()}"

        return False, f"Acción de rama no reconocida: '{action}'."


# Instancia singleton para uso en el ecosistema de V.ANSHEE
git_manager = GitManager()
