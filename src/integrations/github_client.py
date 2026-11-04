"""Integración con GitHub REST API para V.ANSHEE.

Permite consultar el estado de GitHub Actions (builds/tests), Pull Requests abiertos,
Issues pendientes y crear nuevas Issues por comando de voz o texto.
Autodetecta el repositorio 'owner/repo' desde el remote 'origin' de Git si no se especifica.
"""

import os
import re
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Tuple, Optional, List, Dict, Any

from config.settings import settings
from src.integrations.git_manager import git_manager


class GitHubClient:
    """Cliente ligero para GitHub REST API v3 con autodetección de repositorio local."""

    def __init__(self):
        self.api_base = "https://api.github.com"

    def _get_token(self) -> str:
        token = getattr(settings, "GITHUB_TOKEN", "") or os.getenv("GITHUB_TOKEN", "")
        return token.strip()

    def resolve_repo(self, explicit_repo: str = "") -> Optional[str]:
        """Resuelve 'owner/repo' desde configuración o desde 'git remote get-url origin'."""
        if explicit_repo and "/" in explicit_repo:
            return explicit_repo.strip()

        cfg_repo = (getattr(settings, "GITHUB_REPO", "") or os.getenv("GITHUB_REPO", "")).strip()
        if cfg_repo and "/" in cfg_repo:
            return cfg_repo

        # Autodetectar desde el repositorio Git local
        ws = git_manager._resolve_workspace_path()
        if ws:
            res = git_manager._run_git(["remote", "get-url", "origin"], cwd=ws)
            if res.returncode == 0 and res.stdout.strip():
                remote_url = res.stdout.strip()
                # Soportar HTTPS (https://github.com/owner/repo.git) y SSH (git@github.com:owner/repo.git)
                m = re.search(r"github\.com[:/]([^/]+/[^/\s]+?)(?:\.git)?$", remote_url, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
        return None

    def _request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Tuple[int, Any]:
        url = f"{self.api_base}{endpoint}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "VANSHEE-Core-Assistant/2.5",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        token = self._get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        body_bytes = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            body_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
            except Exception:
                err_body = {"message": str(e)}
            return e.code, err_body
        except Exception as e:
            return 0, {"message": str(e)}

    def get_actions_status(self, repo: str = "") -> Tuple[bool, str]:
        """Consulta el estado del último workflow run en GitHub Actions."""
        target_repo = self.resolve_repo(repo)
        if not target_repo:
            return False, "No detecté un repositorio de GitHub vinculado. Configura 'owner/repo' en los Ajustes de Vanshee o añade un remote origin de GitHub."

        status_code, body = self._request("GET", f"/repos/{target_repo}/actions/runs?per_page=3")
        if status_code != 200 or not isinstance(body, dict):
            msg = body.get("message", "Error desconocido") if isinstance(body, dict) else str(body)
            return False, f"No pude consultar GitHub Actions en {target_repo} ({msg})."

        runs = body.get("workflow_runs") or []
        if not runs:
            return True, f"El repositorio {target_repo} no tiene ejecuciones registradas en GitHub Actions todavía."

        latest = runs[0]
        wf_name = latest.get("name") or "Workflow"
        status = latest.get("status")
        conclusion = latest.get("conclusion")
        branch = latest.get("head_branch") or "main"

        if status == "completed":
            if conclusion == "success":
                return True, f"¡Todo en verde! El último workflow '{wf_name}' en la rama '{branch}' de {target_repo} pasó exitosamente."
            elif conclusion == "failure":
                return True, f"Atención: el último workflow '{wf_name}' en la rama '{branch}' de {target_repo} falló. Te sugiero revisar los logs."
            else:
                return True, f"El último workflow '{wf_name}' en '{branch}' finalizó con estado: {conclusion}."
        else:
            return True, f"El workflow '{wf_name}' en la rama '{branch}' está actualmente en ejecución ({status})."

    def get_open_prs(self, repo: str = "") -> Tuple[bool, str]:
        """Consulta los Pull Requests abiertos en el repositorio."""
        target_repo = self.resolve_repo(repo)
        if not target_repo:
            return False, "No detecté un repositorio de GitHub configurado para revisar los Pull Requests."

        status_code, body = self._request("GET", f"/repos/{target_repo}/pulls?state=open&per_page=5")
        if status_code != 200 or not isinstance(body, list):
            msg = body.get("message", "Error") if isinstance(body, dict) else "Error de conexión"
            return False, f"No pude obtener los Pull Requests de {target_repo}: {msg}."

        if not body:
            return True, f"No hay ningún Pull Request abierto en {target_repo} en este momento."

        count = len(body)
        top_titles = [f"#{pr.get('number')} '{pr.get('title')}' por {pr.get('user', {}).get('login', 'usuario')}" for pr in body[:2]]
        joined = "; ".join(top_titles)
        return True, f"Hay {count} Pull Request(s) abiertos en {target_repo}: {joined}."

    def get_open_issues(self, repo: str = "") -> Tuple[bool, str]:
        """Consulta las Issues abiertas en el repositorio (excluyendo PRs)."""
        target_repo = self.resolve_repo(repo)
        if not target_repo:
            return False, "No detecté un repositorio de GitHub configurado para consultar las Issues."

        status_code, body = self._request("GET", f"/repos/{target_repo}/issues?state=open&per_page=10")
        if status_code != 200 or not isinstance(body, list):
            msg = body.get("message", "Error") if isinstance(body, dict) else "Error de conexión"
            return False, f"No pude consultar las Issues de {target_repo}: {msg}."

        pure_issues = [item for item in body if "pull_request" not in item]
        if not pure_issues:
            return True, f"¡Excelente! No hay Issues abiertas pendientes en {target_repo}."

        top = [f"#{iss.get('number')} '{iss.get('title')}'" for iss in pure_issues[:3]]
        return True, f"Tienes {len(pure_issues)} Issue(s) abiertas en {target_repo}: {', '.join(top)}."

    def create_issue(self, title_and_body: str, repo: str = "") -> Tuple[bool, str]:
        """Crea una nueva Issue en GitHub."""
        target_repo = self.resolve_repo(repo)
        if not target_repo:
            return False, "No detecté un repositorio de GitHub configurado para crear la Issue."

        if not self._get_token():
            return False, "Para crear Issues en GitHub necesitas configurar tu Personal Access Token en los Ajustes de Vanshee."

        clean = (title_and_body or "").strip()
        if not clean:
            return False, "Indícame el título o descripción de la Issue que quieres crear."

        parts = clean.split(":", 1) if ":" in clean and len(clean.split(":", 1)[0]) < 80 else [clean]
        title = parts[0].strip()
        body_txt = parts[1].strip() if len(parts) > 1 else f"Issue creada por voz desde V.ANSHEE Core Assistant.\n\nDetalle: {clean}"

        status_code, resp = self._request("POST", f"/repos/{target_repo}/issues", data={
            "title": title,
            "body": body_txt
        })
        if status_code in (200, 201) and isinstance(resp, dict):
            num = resp.get("number")
            return True, f"¡Listo! He creado la Issue #{num} titulada '{title}' en {target_repo}."
        msg = resp.get("message", "Error al crear issue") if isinstance(resp, dict) else str(resp)
        return False, f"No se pudo crear la Issue en GitHub: {msg}."


github_client = GitHubClient()
