import sqlite3
from dataclasses import dataclass
from pathlib import Path

from config.settings import settings
from src.executor.screen_mapper import ScreenMapper
from src.routines.db import init_db


@dataclass
class ContextSnapshot:
    app_name: str
    window_title: str
    screen_size: tuple[int, int]
    confidence: float
    suggestion: str


class ContextAwarenessEngine:
    """Interpreta el estado actual del escritorio y genera asistencia contextual."""

    def __init__(self, screen_mapper: ScreenMapper | None = None):
        init_db()
        self.screen_mapper = screen_mapper or ScreenMapper()
        self.db_path = settings.DB_PATH

    def observe(self, action_hint: str = "", user_command: str = "") -> ContextSnapshot:
        context = self.screen_mapper.map_screen_context(action_hint=action_hint)
        app_name = self._infer_app_name(context.get("window_title", ""), action_hint)
        suggestion = self._suggest_next_step(app_name, context.get("window_title", ""), user_command)

        snapshot = ContextSnapshot(
            app_name=app_name,
            window_title=context.get("window_title", ""),
            screen_size=context.get("screen_size", (0, 0)),
            confidence=context.get("confidence", 0.0),
            suggestion=suggestion,
        )
        self.log_context(snapshot, action_hint=action_hint, user_command=user_command)
        return snapshot

    def log_context(self, snapshot: ContextSnapshot, action_hint: str = "", user_command: str = "", response: str = ""):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO context_events (
                    app_name, window_title, action_hint, user_command, assistant_response, confidence
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.app_name,
                    snapshot.window_title,
                    action_hint,
                    user_command,
                    response or snapshot.suggestion,
                    snapshot.confidence,
                ),
            )

    def _infer_app_name(self, window_title: str, action_hint: str = "") -> str:
        text = f"{window_title} {action_hint}".lower()
        if "spotify" in text:
            return "spotify"
        if any(word in text for word in ["youtube", "youtu.be"]):
            return "youtube"
        if any(word in text for word in ["visual studio code", " vs code", "vscode", " - code", "code"]):
            return "vscode"
        if "steam" in text:
            return "steam"
        if any(word in text for word in ["word", ".docx"]):
            return "word"
        if any(word in text for word in ["notepad", "bloc de notas", ".txt"]):
            return "text_editor"
        if any(word in text for word in ["chrome", "edge", "brave", "firefox"]):
            return "browser"
        return "desktop"

    def _suggest_next_step(self, app_name: str, window_title: str, user_command: str = "") -> str:
        command = user_command.lower()
        if app_name == "spotify":
            return "Detecto Spotify activo. Puedo pausar, reanudar o buscar una canción o lista para reproducir."

        if app_name == "youtube":
            if any(word in window_title for word in ["search", "buscar", "resultados", "youtube"]):
                return "Detecto YouTube activo. ¿Deseas que reproduzca tu búsqueda o selección reciente?"
            return "Detecto YouTube activo. ¿Deseas ver o escuchar algo en particular?"

        if app_name == "vscode":
            if any(word in command for word in ["archivo", "file", "crear", "nuevo"]):
                return "Detecto VS Code activo. Puedo crear el archivo en la carpeta que indiques y abrirlo en el editor."
            return "Detecto VS Code activo. Puedo ayudarte a crear archivos, proyectos o abrir una ruta concreta."

        if app_name == "steam":
            return "Detecto Steam activo. Puedo abrir un juego instalado o lanzar Counter-Strike 2 si lo indicas."

        if app_name == "word":
            return "Detecto Word activo. Puedo preparar texto, crear documentos o ayudarte a organizar el contenido."

        if app_name == "text_editor":
            return "Detecto un editor de texto activo. Puedo escribir o guardar contenido en un archivo .txt."

        if app_name == "browser":
            return "Detecto un navegador activo. Puedo abrir una URL, buscar información o continuar con la página actual."

        return "Estoy observando el contexto del sistema para ayudarte con la acción actual."


def safe_filename(name: str, default: str = "nuevo_archivo") -> str:
    cleaned = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in name.strip())
    return cleaned or default


def default_extension_for_language(language: str) -> str:
    mapping = {
        "python": ".py",
        "node": ".js",
        "javascript": ".js",
        "typescript": ".ts",
        "web": ".html",
        "html": ".html",
        "css": ".css",
        "csharp": ".cs",
        "txt": ".txt",
        "texto": ".txt",
        "markdown": ".md",
    }
    return mapping.get(language.lower().strip(), ".txt")


def ensure_file_extension(path: Path, language: str) -> Path:
    if path.suffix:
        return path
    return path.with_suffix(default_extension_for_language(language))
