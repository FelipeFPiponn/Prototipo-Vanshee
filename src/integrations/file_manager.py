"""Gestor de Creación y Manejo de Archivos y Carpetas en Windows OS para V.ANSHEE.

Permite la creación rápida por comando de voz de:
- Carpetas y directorios (con opción de apertura en el Explorador de Windows).
- Bloc de notas / archivos de texto .txt (abiertos automáticamente en notepad.exe).
- Archivos de código (.py, .js, .html, .css, .json, .md, etc.) con plantillas iniciales.
- Resolución inteligente de rutas de usuario (Escritorio, Documentos, Descargas o Workspace activo).
"""

import os
import subprocess
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime

from src.context_awareness import safe_filename, ensure_file_extension, default_extension_for_language
from src.integrations.editor_hub import editor_hub


class FileManager:
    """Maneja la creación de carpetas, bloc de notas y archivos en el sistema operativo."""

    FOLDER_ALIASES = {
        "escritorio": Path.home() / "Desktop",
        "desktop": Path.home() / "Desktop",
        "documentos": Path.home() / "Documents",
        "documents": Path.home() / "Documents",
        "descargas": Path.home() / "Downloads",
        "downloads": Path.home() / "Downloads",
        "imagenes": Path.home() / "Pictures",
        "fotos": Path.home() / "Pictures",
        "pictures": Path.home() / "Pictures",
        "musica": Path.home() / "Music",
        "music": Path.home() / "Music",
        "videos": Path.home() / "Videos",
        "proyectos": Path.home() / "Desktop" / "VANSHEE_Projects",
        "projects": Path.home() / "Desktop" / "VANSHEE_Projects",
    }

    STARTER_TEMPLATES = {
        ".py": '"""Módulo creado por V.ANSHEE."""\n\ndef main():\n    print("Hola desde V.ANSHEE")\n\nif __name__ == "__main__":\n    main()\n',
        ".js": '// Script creado por V.ANSHEE\nconsole.log("Hola desde V.ANSHEE");\n',
        ".ts": '// TypeScript creado por V.ANSHEE\nconsole.log("Hola desde V.ANSHEE");\n',
        ".html": '<!DOCTYPE html>\n<html lang="es">\n<head>\n    <meta charset="UTF-8">\n    <title>Nuevo Documento</title>\n</head>\n<body>\n    <h1>Creado por V.ANSHEE</h1>\n</body>\n</html>\n',
        ".css": '/* Estilos creados por V.ANSHEE */\nbody {\n    margin: 0;\n    font-family: sans-serif;\n}\n',
        ".json": '{\n    "name": "vanshee_data",\n    "created_by": "V.ANSHEE"\n}\n',
        ".md": '# Documento\n\nCreado con V.ANSHEE.\n',
        ".txt": '',
    }

    def resolve_directory(self, requested_location: str = "", prefer_workspace: bool = False) -> Path:
        """Resuelve la ruta física destino según la preferencia o contexto del usuario."""
        loc = (requested_location or "").lower().strip()

        # 1. Alias conocidos de usuario
        if loc in self.FOLDER_ALIASES:
            target = self.FOLDER_ALIASES[loc]
            target.mkdir(parents=True, exist_ok=True)
            return target

        # 2. Si se solicitó dentro de una carpeta o ruta personalizada
        if loc:
            try:
                expanded = Path(os.path.expandvars(loc)).expanduser()
                if expanded.suffix:
                    expanded = expanded.parent
                expanded.mkdir(parents=True, exist_ok=True)
                return expanded
            except Exception:
                pass

        # 3. Si se prefiere el workspace del editor y existe uno activo
        if prefer_workspace:
            active_ctx = editor_hub.get_active_context()
            ws_root = active_ctx.get("workspace_root")
            if ws_root and Path(ws_root).exists():
                return Path(ws_root)

        # 4. Por defecto para Windows OS: El Escritorio del usuario
        desktop = Path.home() / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        return desktop

    def create_folder(self, folder_name: str, location: str = "", open_after: bool = False) -> Tuple[bool, str, Path]:
        """Crea una carpeta o directorio en la ubicación indicada."""
        clean_name = safe_filename(folder_name or "Nueva_Carpeta", default="Nueva_Carpeta")
        base_dir = self.resolve_directory(location)
        target_path = base_dir / clean_name

        try:
            # Si ya existe, generar un nombre secuencial para no sobrescribir
            counter = 1
            original_target = target_path
            while target_path.exists() and counter <= 100:
                counter += 1
                target_path = base_dir / f"{clean_name}_{counter}"

            target_path.mkdir(parents=True, exist_ok=True)
            loc_label = base_dir.name or "el sistema"
            msg = f"Carpeta '{target_path.name}' creada con éxito en {loc_label}."
            print(f"[FileManager] {msg} -> {target_path}")

            if open_after:
                try:
                    subprocess.Popen(f'explorer.exe "{target_path}"', shell=True)
                except Exception as e:
                    print(f"[FileManager Warning] No se pudo abrir explorador: {e}")

            return True, msg, target_path
        except Exception as e:
            err_msg = f"Error al crear carpeta '{folder_name}': {e}"
            print(f"[FileManager Error] {err_msg}")
            return False, err_msg, base_dir

    def create_notepad(self, note_name: str = "", content: str = "", location: str = "", open_notepad: bool = True) -> Tuple[bool, str, Path]:
        """Crea un archivo de texto .txt (Bloc de notas) y lo abre en notepad.exe."""
        raw_name = note_name.strip()
        if not raw_name:
            timestamp = datetime.now().strftime("%H%M%S")
            raw_name = f"nota_{timestamp}"

        if not raw_name.lower().endswith(".txt"):
            raw_name += ".txt"

        clean_name = safe_filename(raw_name, default="nota.txt")
        base_dir = self.resolve_directory(location)
        target_path = base_dir / clean_name

        try:
            # Si ya existe y no se especificó nombre explícito, crear con sufijo
            if target_path.exists() and not note_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                target_path = base_dir / f"nota_{timestamp}.txt"

            initial_text = (content.strip() + "\n") if content else ""
            target_path.write_text(initial_text, encoding="utf-8")

            loc_label = base_dir.name or "el Escritorio"
            msg = f"Bloc de notas '{target_path.name}' creado en {loc_label}."
            print(f"[FileManager] {msg} -> {target_path}")

            if open_notepad:
                try:
                    subprocess.Popen(["notepad.exe", str(target_path)])
                except Exception as e:
                    print(f"[FileManager Warning] No se pudo abrir notepad.exe: {e}")

            return True, msg, target_path
        except Exception as e:
            err_msg = f"Error al crear Bloc de notas: {e}"
            print(f"[FileManager Error] {err_msg}")
            return False, err_msg, base_dir

    def create_file(self, file_name: str, content: str = "", location: str = "", language: str = "", open_after: bool = False, open_with: str = "") -> Tuple[bool, str, Path]:
        """Crea un archivo de cualquier extensión con plantilla inicial opcional."""
        raw_name = (file_name or "").strip()
        if not raw_name:
            raw_name = "nuevo_archivo"

        lang = (language or "").lower().strip()

        # Si se solicita explícitamente bloc de notas o es .txt
        if open_with == "notepad" or lang in ["notepad", "bloc de notas", "block de notas", "txt", "texto"] and not (raw_name.endswith(".py") or raw_name.endswith(".js")):
            return self.create_notepad(note_name=raw_name, content=content, location=location, open_notepad=open_after or True)

        base_dir = self.resolve_directory(location, prefer_workspace=(lang in ["python", "node", "javascript", "typescript", "html", "css", "json"]))
        clean_name = safe_filename(raw_name, default="nuevo_archivo")
        target_path = base_dir / clean_name

        # Asegurar extensión correspondiente al lenguaje si no tiene sufijo
        if not target_path.suffix and lang:
            target_path = ensure_file_extension(target_path, lang)
        elif not target_path.suffix:
            target_path = target_path.with_suffix(".txt")

        try:
            suffix = target_path.suffix.lower()
            initial_text = content if content else self.STARTER_TEMPLATES.get(suffix, "")
            target_path.write_text(initial_text, encoding="utf-8")

            loc_label = base_dir.name or "el sistema"
            msg = f"Archivo '{target_path.name}' creado con éxito en {loc_label}."
            print(f"[FileManager] {msg} -> {target_path}")

            if open_after:
                try:
                    if suffix == ".txt":
                        subprocess.Popen(["notepad.exe", str(target_path)])
                    else:
                        os.startfile(str(target_path))
                except Exception as e:
                    print(f"[FileManager Warning] No se pudo abrir archivo: {e}")

            return True, msg, target_path
        except Exception as e:
            err_msg = f"Error al crear archivo '{file_name}': {e}"
            print(f"[FileManager Error] {err_msg}")
            return False, err_msg, base_dir


# Instancia singleton accesible globalmente
file_manager = FileManager()
