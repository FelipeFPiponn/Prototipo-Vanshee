import ast
import importlib.util
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"

SCAN_DIRS = [
    ROOT / "src",
    ROOT / "scripts",
    ROOT / "config",
]

INTERNAL_MODULES = {
    "config",
    "scripts",
    "src",
}

PACKAGE_MAP = {
    "PIL": "pillow>=11.0.0",
    "faster_whisper": "faster-whisper>=1.2.1",
    "numpy": "numpy>=2.5.2",
    "ollama": "ollama>=0.6.2",
    "pydantic": "pydantic>=2.13.4",
    "pydantic_settings": "pydantic-settings>=2.15.0",
    "pyautogui": "pyautogui>=0.9.54",
    "pygetwindow": "pygetwindow>=0.0.9",
    "pythoncom": "pywin32>=312",
    "scipy": "scipy>=1.10.0",
    "sounddevice": "sounddevice>=0.5.6",
    "soundfile": "soundfile>=0.14.0",
    "win32com": "pywin32>=312",
}


def stdlib_modules() -> set[str]:
    names = set(getattr(sys, "stdlib_module_names", set()))
    stdlib = sysconfig.get_paths().get("stdlib")
    if stdlib:
        for path in Path(stdlib).glob("*.py"):
            names.add(path.stem)
    return names


def imported_roots(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        print(f"[WARN] No se pudo analizar {path.relative_to(ROOT)}: {exc}")
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imports.add(node.module.split(".", 1)[0])
    return imports


def read_existing_requirements() -> dict[str, str]:
    existing: dict[str, str] = {}
    if not REQUIREMENTS.exists():
        return existing

    for raw_line in REQUIREMENTS.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key = line
        for separator in ("==", ">=", "<=", "~=", ">", "<"):
            if separator in line:
                key = line.split(separator, 1)[0].strip()
                break
        existing[key.lower().replace("_", "-")] = line
    return existing


def is_probably_external(module: str, stdlib: set[str]) -> bool:
    if module in stdlib or module in INTERNAL_MODULES:
        return False
    if importlib.util.find_spec(module) is None:
        return False
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin in (None, "built-in", "frozen"):
        return False
    origin = str(spec.origin).lower()
    return "site-packages" in origin or "dist-packages" in origin


def main() -> int:
    stdlib = stdlib_modules()
    imports: set[str] = set()
    for directory in SCAN_DIRS:
        if directory.exists():
            for path in directory.rglob("*.py"):
                if "__pycache__" not in path.parts:
                    imports.update(imported_roots(path))

    existing = read_existing_requirements()
    generated: dict[str, str] = {}
    unmapped_external: set[str] = set()

    for module in sorted(imports):
        requirement = PACKAGE_MAP.get(module)
        if requirement:
            name = requirement.split(">=", 1)[0].split("==", 1)[0].lower().replace("_", "-")
            generated[name] = requirement
        elif is_probably_external(module, stdlib):
            unmapped_external.add(module)

    merged = existing | generated
    lines = [merged[name] for name in sorted(merged)]
    REQUIREMENTS.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[OK] requirements.txt sincronizado con {len(lines)} dependencia(s).")
    if unmapped_external:
        print("[WARN] Imports externos sin mapeo automatico:")
        for module in sorted(unmapped_external):
            print(f"  - {module}")
        print("[WARN] Agrega estos paquetes manualmente a PACKAGE_MAP si deben instalarse siempre.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
