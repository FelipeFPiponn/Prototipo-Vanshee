"""Gestor de Modos de Operación para V.ANSHEE (Modo Gamer vs Modo Trabajo/Programador).

Permite alternar perfiles contextuales por comando de voz o interfaz, persistiendo
el estado en base de datos SQLite y optimizando la priorización de integraciones.
"""

import sqlite3
import threading
from typing import Callable, List, Tuple, Dict, Any
from pathlib import Path

try:
    from config.settings import settings
except ImportError:
    settings = None


class ModeManager:
    """Gestiona el modo operativo activo (Gamer vs Trabajo) y su persistencia."""

    MODES = {
        "gamer": {
            "name": "Modo Gamer",
            "aliases": ["gamer", "juego", "juegos", "gaming", "game", "partida"],
            "description": "Optimizado para gaming, Discord, League of Legends, Valorant, Steam y OBS Studio.",
            "voice_announcement": "Modo Gamer activado. Herramientas de juego, Discord y grabación listas.",
            "accent_color": "#10b981", # Verde esmeralda neón
        },
        "work": {
            "name": "Modo Trabajo",
            "aliases": ["work", "trabajo", "programador", "programacion", "programación", "dev", "desarrollo", "oficina"],
            "description": "Optimizado para desarrollo de software, editores de código, Git y terminales.",
            "voice_announcement": "Modo Trabajo activado. Editores de código y flujo Git preparados.",
            "accent_color": "#3b82f6", # Azul eléctrico dev
        },
        "default": {
            "name": "Modo General",
            "aliases": ["default", "general", "normal", "estándar", "estandar", "off"],
            "description": "Modo balanceado para uso general del sistema operativo y multimedia.",
            "voice_announcement": "Modo general restablecido.",
            "accent_color": "#8b5cf6", # Púrpura estándar Vanshee
        }
    }

    def __init__(self):
        self._current_mode = "default"
        self._lock = threading.RLock()
        self._callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self._load_persisted_mode()

    def _get_db_connection(self) -> sqlite3.Connection:
        if settings and hasattr(settings, "DB_PATH"):
            db_path = settings.DB_PATH
        else:
            db_path = Path(__file__).resolve().parent.parent.parent / "data" / "vanshee.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(db_path))

    def _load_persisted_mode(self):
        """Carga el modo activo guardado previamente en SQLite."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    pref_key TEXT PRIMARY KEY,
                    pref_value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("SELECT pref_value FROM user_preferences WHERE pref_key = 'active_mode'")
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                raw_mode = row[0].lower().strip()
                self._current_mode = self.normalize_mode_name(raw_mode)
        except Exception as e:
            print(f"[ModeManager Warning] No se pudo leer modo de base de datos: {e}")

    def _save_persisted_mode(self, mode: str):
        """Guarda el modo activo en SQLite."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_preferences (pref_key, pref_value, updated_at)
                VALUES ('active_mode', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(pref_key) DO UPDATE SET pref_value = excluded.pref_value, updated_at = CURRENT_TIMESTAMP
            """, (mode,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[ModeManager Warning] No se pudo persistir modo en base de datos: {e}")

    def normalize_mode_name(self, raw_name: str) -> str:
        """Normaliza un término en lenguaje natural al identificador canónico del modo."""
        term = (raw_name or "").lower().strip()
        for mode_key, mode_info in self.MODES.items():
            if term == mode_key or term in mode_info["aliases"]:
                return mode_key
            for alias in mode_info["aliases"]:
                if alias in term or term in alias:
                    return mode_key
        return "default"

    def get_current_mode(self) -> str:
        """Retorna el identificador del modo actual ('gamer', 'work', 'default')."""
        with self._lock:
            return self._current_mode

    def is_gamer_mode(self) -> bool:
        """Determina si el Modo Gamer está activo."""
        return self.get_current_mode() == "gamer"

    def is_work_mode(self) -> bool:
        """Determina si el Modo Trabajo está activo."""
        return self.get_current_mode() == "work"

    def set_mode(self, target_mode: str) -> Tuple[bool, str, str]:
        """Cambia el modo activo, lo persiste y notifica a los suscriptores.
        
        Retorna: (éxito, mensaje descriptivo, locución para TTS)
        """
        canonical = self.normalize_mode_name(target_mode)
        with self._lock:
            self._current_mode = canonical
            self._save_persisted_mode(canonical)

        info = self.MODES.get(canonical, self.MODES["default"])
        mode_name = info["name"]
        voice_msg = info["voice_announcement"]
        desc_msg = f"{mode_name} activado con éxito. {info['description']}"

        print(f"[ModeManager] Cambio de modo aplicado: '{canonical}' ({mode_name})")

        # Notificar a los observadores registrados
        for cb in self._callbacks:
            try:
                cb(canonical, info)
            except Exception as e:
                print(f"[ModeManager Error] Falló callback de cambio de modo: {e}")

        return True, desc_msg, voice_msg

    def get_mode_summary(self) -> str:
        """Retorna un resumen conversacional en español del modo actualmente activo."""
        mode = self.get_current_mode()
        info = self.MODES.get(mode, self.MODES["default"])
        if mode == "gamer":
            return "Actualmente estás en Modo Gamer. Discord, OBS Studio, League of Legends y Valorant tienen prioridad activa."
        elif mode == "work":
            return "Actualmente estás en Modo Trabajo. Tu editor de código, el flujo de Git y herramientas de desarrollo están listos y priorizados."
        return "Actualmente estás en el Modo General balanceado de Vanshee."

    def on_mode_change(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Registra un callback que se ejecuta cada vez que el modo cambia."""
        self._callbacks.append(callback)


# Instancia singleton de gestión de modos
mode_manager = ModeManager()
