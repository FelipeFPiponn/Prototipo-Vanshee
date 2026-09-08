import os
import subprocess
import webbrowser
from pathlib import Path
from src.nlu.intent_parser import ParsedPipeline, ActionStep
from src.executor.dynamic_resolver import DynamicResolver
from src.routines.habit_engine import HabitEngine

class OSExecutor:
    def __init__(self):
        self.resolver = DynamicResolver()
        self.habit_engine = HabitEngine()

    def execute(self, pipeline: ParsedPipeline) -> bool:
        return self.execute_pipeline(pipeline)

    def execute_pipeline(self, pipeline: ParsedPipeline) -> bool:
        if not pipeline or not pipeline.steps:
            print("[OSExecutor] No hay intenciones válidas para ejecutar.")
            return False

        overall_success = True
        print(f"\n[OSExecutor] Ejecutando pipeline de {len(pipeline.steps)} acción(es)...")

        for idx, step in enumerate(pipeline.steps, start=1):
            print(f" -> Paso {idx}: Intent='{step.intent}' | Target='{step.target}'")
            success = self._execute_step(step)
            if not success:
                print(f"[OSExecutor Error] Falló la ejecución en el paso {idx}: '{step.target}'")
                overall_success = False
                break

        if overall_success:
            self.habit_engine.log_execution(pipeline.raw_text)

        return overall_success

    def _execute_step(self, step: ActionStep) -> bool:
        intent = str(step.intent).upper().strip()
        target = str(step.target).lower().strip()

        # Prioridad 1: Apertura de aplicaciones o accesos web (Aislar falsos positivos)
        if "OPEN" in intent or "LAUNCH" in intent or "APP" in intent or not intent or intent == "UNKNOWN":
            return self._launch_target(target)

        # Prioridad 2: Borrado explícito de la memoria
        elif "FORGET" in intent and "OPEN" not in intent:
            return self.resolver.forget_command(target)

        # Prioridad 3: Creación de proyectos de desarrollo
        elif "CREATE" in intent or "PROJECT" in intent:
            p_type = getattr(step.parameters, "project_type", "python") if hasattr(step, "parameters") and step.parameters else "python"
            p_name = getattr(step.parameters, "project_name", "nuevo_proyecto") if hasattr(step, "parameters") and step.parameters else "nuevo_proyecto"
            return self._create_and_open_project(
                app_target=target,
                p_type=p_type,
                p_name=p_name
            )

        # Fallback de ejecución directa por nombre de target
        if target:
            return self._launch_target(target)

        return False

    def _launch_target(self, target: str) -> bool:
        execution_target, target_type = self.resolver.resolve(target)
        if not execution_target:
            print(f"[OSExecutor] No se encontró ruta ejecutable para: '{target}'")
            return False

        try:
            if target_type in ["url", "protocol"] or execution_target.startswith(("http", "steam://", "discord://", "spotify://")):
                webbrowser.open(execution_target)
            elif hasattr(os, "startfile"):
                os.startfile(execution_target)
            else:
                subprocess.Popen(execution_target, shell=True)

            self.resolver.save_learned_command(target, execution_target, target_type)
            return True
        except Exception as e:
            print(f"[OSExecutor Error] Falla al invocar '{execution_target}': {e}")
            return False

    def _create_and_open_project(self, app_target: str, p_type: str, p_name: str) -> bool:
        base_dir = Path.home() / "Desktop" / "VANSHEE_Projects" / p_name
        base_dir.mkdir(parents=True, exist_ok=True)

        print(f"[ProjectCreator] Creando entorno '{p_name}' ({p_type}) en: {base_dir}")

        if p_type == "python":
            subprocess.run(f"python -m venv \"{base_dir / '.venv'}\"", shell=True)
            main_file = base_dir / "main.py"
            if not main_file.exists():
                main_file.write_text("# Auto-generado por V.ANSHEE\nprint('Proyecto V.ANSHEE listo.')\n", encoding="utf-8")
        elif p_type in ["node", "web"]:
            subprocess.run("npm init -y", cwd=base_dir, shell=True)

        ide_path, _ = self.resolver.resolve(app_target if app_target else "vscode")
        if ide_path:
            try:
                subprocess.Popen(f'"{ide_path}" "{base_dir}"', shell=True)
                return True
            except Exception as e:
                print(f"[ProjectCreator Error] No se pudo abrir el IDE: {e}")
        return False