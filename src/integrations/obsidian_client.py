"""Cliente de Integración para Obsidian (Bóveda Local y Local REST API).

Permite agregar notas rápidas, tareas a la lista diaria y consultar contenido de la bóveda
sin necesidad de enfocar ni abrir la interfaz de Obsidian.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional


class ObsidianClient:
    """Gestiona notas directas en la bóveda de Obsidian."""

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = self._resolve_vault_path(vault_path)

    def _resolve_vault_path(self, custom_path: Optional[str]) -> Optional[Path]:
        if custom_path and Path(custom_path).exists():
            return Path(custom_path)

        # Buscar ubicaciones habituales de Obsidian en Documentos o Escritorio
        home = Path.home()
        candidates = [
            home / "Documents" / "Obsidian Vault",
            home / "Documents" / "Obsidian",
            home / "Desktop" / "Obsidian Vault",
            home / "Obsidian",
        ]
        for c in candidates:
            if c.exists():
                return c
        return home / "Documents" / "Vanshee_Notes"

    def append_daily_note(self, content: str) -> Tuple[bool, str]:
        """Agrega una entrada con marca de tiempo a la nota diaria."""
        if not self.vault_path:
            return False, "No se encontró la ruta de la bóveda de Obsidian."

        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            time_str = datetime.now().strftime("%H:%M")
            daily_dir = self.vault_path / "Diario"
            daily_dir.mkdir(parents=True, exist_ok=True)
            daily_file = daily_dir / f"{today_str}.md"

            entry = f"- **{time_str}**: {content.strip()}\n"
            with daily_file.open("a", encoding="utf-8") as f:
                f.write(entry)

            msg = f"Anotado en tu diario de Obsidian ({today_str}): '{content}'"
            print(f"[ObsidianClient] {msg}")
            return True, msg
        except Exception as e:
            return False, f"Error al escribir en Obsidian: {e}"

    def add_todo_task(self, task_text: str) -> Tuple[bool, str]:
        """Agrega una tarea pendiente (- [ ]) en el archivo de tareas."""
        if not self.vault_path:
            return False, "Bóveda no configurada."

        try:
            todo_file = self.vault_path / "Tareas.md"
            self.vault_path.mkdir(parents=True, exist_ok=True)
            entry = f"- [ ] {task_text.strip()} (Agregado: {datetime.now().strftime('%d/%m %H:%M')})\n"
            with todo_file.open("a", encoding="utf-8") as f:
                f.write(entry)

            msg = f"Tarea añadida a Obsidian: '{task_text}'"
            print(f"[ObsidianClient] {msg}")
            return True, msg
        except Exception as e:
            return False, f"Error al agregar tarea: {e}"


# Instancia global compartida
obsidian_client = ObsidianClient()
