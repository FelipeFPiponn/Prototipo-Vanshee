import os
import sys
from pathlib import Path

def get_current_user_home() -> Path:
    """Retorna la ruta al directorio home del usuario actual del sistema de forma segura."""
    try:
        return Path.home()
    except Exception:
        profile = os.environ.get("USERPROFILE")
        if profile:
            return Path(profile)
        return Path("C:/Users/Default")

def get_default_projects_dir() -> Path:
    """Retorna la ruta base por defecto para proyectos de Vanshee en el equipo actual."""
    home = get_current_user_home()
    projects_dir = home / "Desktop" / "VANSHEE_Projects"
    try:
        projects_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Si por permisos de escritorio no es accesible, usar directorio en home
        projects_dir = home / "VANSHEE_Projects"
        try:
            projects_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    return projects_dir

def normalize_user_path(raw_path: str | Path | None) -> Path:
    """
    Convierte cualquier ruta absoluta (incluso si pertenecía al usuario de otra computadora)
    para que apunte al usuario activo de esta máquina de forma 100% portable y segura.
    """
    if not raw_path:
        return get_default_projects_dir()

    # 1. Expandir variables de entorno de Windows si existen (%USERPROFILE%, %APPDATA%, etc.)
    expanded = os.path.expandvars(str(raw_path)).strip()
    p = Path(expanded)

    current_home = get_current_user_home()
    current_username = current_home.name.lower()

    # 2. Detectar si la ruta apunta a C:\Users\<otro_usuario>\...
    try:
        parts = p.resolve(strict=False).parts
    except Exception:
        parts = p.parts

    # parts ej: ('C:\\', 'Users', 'jenar', 'Desktop', 'VANSHEE_Projects')
    if len(parts) >= 3 and parts[0].upper().startswith("C:") and parts[1].lower() == "users":
        stored_user = parts[2].lower()
        if stored_user != current_username:
            # Reasignar al usuario actual de este equipo
            remapped_subpath = Path(*parts[3:]) if len(parts) > 3 else Path()
            candidate = current_home / remapped_subpath
            return candidate

    return p

def to_portable_path(path_str: str | Path) -> str:
    """
    Convierte una ruta absoluta en un formato portable utilizando variables de entorno
    como %USERPROFILE% o %APPDATA% antes de guardarla en la base de datos SQLite.
    """
    if not path_str:
        return ""

    p_str = str(path_str).replace("/", "\\")
    current_home = str(get_current_user_home()).replace("/", "\\")
    appdata = os.environ.get("APPDATA", "").replace("/", "\\")
    localappdata = os.environ.get("LOCALAPPDATA", "").replace("/", "\\")

    if appdata and p_str.lower().startswith(appdata.lower()):
        return "%APPDATA%" + p_str[len(appdata):]
    if localappdata and p_str.lower().startswith(localappdata.lower()):
        return "%LOCALAPPDATA%" + p_str[len(localappdata):]
    if current_home and p_str.lower().startswith(current_home.lower()):
        return "%USERPROFILE%" + p_str[len(current_home):]

    return p_str
