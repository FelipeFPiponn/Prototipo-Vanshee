import os
import subprocess
import webbrowser
import urllib.parse
from pathlib import Path
from config.settings import settings
from src.context_awareness import ContextAwarenessEngine, ensure_file_extension, safe_filename
from src.nlu.intent_parser import ParsedPipeline, ActionStep
from src.executor.dynamic_resolver import DynamicResolver
from src.routines.habit_engine import RoutineEngine
from src.executor.screen_mapper import ScreenMapper
from src.audio.tts_engine import TTSEngine
from src.audio.voice_dialog import VoiceDialog
from src.executor.window_manager import WindowManager
from src.executor.search_registry import SearchProviderRegistry
from src.utils.query_cleaner import clean_search_term

class OSExecutor:
    def __init__(self, tts: TTSEngine | None = None, dialog: VoiceDialog | None = None, interactive_voice: bool | None = None):
        self.resolver = DynamicResolver()
        self.routine_engine = RoutineEngine()
        self.tts = tts or TTSEngine()
        self.dialog = dialog
        self.interactive_voice = settings.ENABLE_VOICE_VERIFICATION if interactive_voice is None else interactive_voice
        self.window_manager = WindowManager()
        self.search_registry = SearchProviderRegistry()
        self.screen_mapper = ScreenMapper()
        self.context_engine = ContextAwarenessEngine(screen_mapper=self.screen_mapper)
        self.last_action_message = ""

    def execute(self, pipeline: ParsedPipeline) -> bool:
        """Punto de entrada compatible con el bucle principal main.py."""
        return self.execute_pipeline(pipeline)

    def execute_pipeline(self, pipeline: ParsedPipeline) -> bool:
        if not pipeline or not pipeline.steps:
            print("[OSExecutor] No hay intenciones válidas para ejecutar.")
            return False

        # Optimización de pipeline: Evitar abrir una ventana vacía de la app si también se va a crear/abrir un proyecto en ella
        has_create_project = any("CREATE_PROJECT" in s.intent.upper() for s in pipeline.steps)
        if has_create_project:
            create_targets = {
                self.resolver.resolve(s.target if s.target else "vscode")[0]
                for s in pipeline.steps if "CREATE_PROJECT" in s.intent.upper()
            }
            filtered_steps = []
            for s in pipeline.steps:
                if "OPEN_APP" in s.intent.upper():
                    app_res = self.resolver.resolve(s.target)[0]
                    if app_res and app_res in create_targets:
                        print(f"[OSExecutor Optimización] Omitiendo apertura de ventana vacía de '{s.target}' (se abrirá directamente con el nuevo proyecto).")
                        continue
                filtered_steps.append(s)
            pipeline.steps = filtered_steps

        # Optimización de pipeline: Evitar abrir una página vacía si también se va a realizar una búsqueda en ella
        has_search = any("SEARCH" in s.intent.upper() for s in pipeline.steps)
        if has_search:
            search_targets = {
                s.target.lower().strip() for s in pipeline.steps if "SEARCH" in s.intent.upper()
            }
            filtered_steps = []
            for s in pipeline.steps:
                if "OPEN_APP" in s.intent.upper() and any(st in s.target.lower() for st in search_targets):
                    print(f"[OSExecutor Optimización] Omitiendo apertura de página inicial de '{s.target}' (se abrirá directamente con la búsqueda).")
                    continue
                if "FORGET" in s.intent.upper() and ("busca" in pipeline.raw_text.lower() or "youtube" in pipeline.raw_text.lower()):
                    continue
                filtered_steps.append(s)
            pipeline.steps = filtered_steps

        overall_success = True
        print(f"\n[OSExecutor] Ejecutando pipeline de {len(pipeline.steps)} acción(es)...")
        self._announce_context(action_hint="pipeline", user_command=pipeline.raw_text, ask=False)

        for idx, step in enumerate(pipeline.steps, start=1):
            print(f" -> Paso {idx}: Intent='{step.intent}' | Target='{step.target}'")
            success = self._execute_step(step)
            if not success:
                print(f"[OSExecutor Error] Falló la ejecución en el paso {idx}: '{step.target}'")
                overall_success = False
                break

        # Si el comando completo se ejecutó con éxito, se registra en el motor de hábitos
        if overall_success:
            self.routine_engine.log_execution(pipeline.raw_text)

        return overall_success

    def _get_dialog(self) -> VoiceDialog:
        if self.dialog is None:
            self.dialog = VoiceDialog(tts=self.tts)
        return self.dialog

    def _execute_step(self, step: ActionStep) -> bool:
        intent = step.intent.upper()
        target = step.target.lower().strip()

        if "FORGET" in intent:
            success = self.resolver.forget_command(target)
            msg = "Aprendizaje anterior eliminado correctamente de la memoria." if success else "No encontré registros en memoria para eliminar."
            print(f"[OSExecutor] {msg}")
            self.last_action_message = msg
            return success

        elif "SEARCH" in intent or intent == "SEARCH_CONTENT":
            return self._search_content(step)

        elif "OPEN_APP" in intent or intent == "OPEN_APP":
            return self._launch_target(target)

        elif "CREATE_PROJECT" in intent or intent == "CREATE_PROJECT":
            return self._create_and_open_project(
                app_target=target,
                p_type=step.parameters.project_type,
                p_name=step.parameters.project_name
            )

        elif "CREATE_FILE" in intent or intent == "CREATE_FILE":
            return self._create_contextual_file(step)

        elif "WRITE_TEXT" in intent or intent == "WRITE_TEXT":
            return self._write_contextual_text(step)

        elif "SYSTEM_CONTROL" in intent or intent == "SYSTEM_CONTROL":
            if target:
                return self._launch_target(target)
            self.last_action_message = "Comando de sistema ejecutado."
            return True

        print(f"[OSExecutor Error] Intent no reconocido o no soportado: '{step.intent}'")
        self.last_action_message = f"Instrucción no soportada: {step.intent}"
        return False

    def _search_content(self, step: ActionStep) -> bool:
        target = step.target.lower().strip()
        query = step.parameters.content or step.parameters.file_name or ""
        
        # Si la consulta no está en parameters.content, inferirla del target
        if not query:
            for srv in ["youtube", "google", "spotify", "brave", "chrome", "steam", "netflix", "github"]:
                if srv in target:
                    query = target.replace(srv, "").replace("busca", "").replace("en", "").strip()
                    target = srv
                    break
        if not query:
            query = step.target

        # Limpieza de prefijos de relleno ('canciones de', 'videos de', etc.)
        query = clean_search_term(query)

        success, msg = self.search_registry.dispatch_search(
            target=target,
            query=query,
            window_manager=self.window_manager,
            app_indexer=self.resolver.indexer
        )
        self.last_action_message = msg
        return success

    def _launch_target(self, target: str) -> bool:
        target_clean = target.lower().strip()

        # 0. Priorizar ventana o app que ya esté abierta en el sistema
        focused, win_title = self.window_manager.find_and_focus(target_clean)
        if focused:
            msg = f"{target} ya estaba abierto; pasando a primer plano."
            print(f"[OSExecutor Ventana Abierta] {msg} ('{win_title}')")
            self.last_action_message = msg
            return True

        execution_target, target_type = self.resolver.resolve(target)
        if not execution_target:
            msg = f"No encontré una aplicación o sitio para {target}."
            print(f"[OSExecutor] {msg}")
            self.last_action_message = msg
            return False

        try:
            if target_type == "url" or execution_target.startswith("http"):
                webbrowser.open_new_tab(execution_target)
                self.last_action_message = f"Abriendo {target} en el navegador."
            else:
                subprocess.Popen(
                    f'start "" "{execution_target}"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.last_action_message = f"Abriendo {target}."

            self.resolver.save_learned_command(target, execution_target, target_type)

            # Dar 1.5s a la aplicación para desplegarse en pantalla antes de mapear
            import time
            time.sleep(1.5)

            # Mapeo y escaneo del panorama en pantalla en tiempo real
            screen_context = self.screen_mapper.map_screen_context(action_hint=target)
            self._announce_context(action_hint=target, user_command=target, ask=False)

            # Obviedad: Si estamos en YouTube o resultados de búsqueda
            if self.interactive_voice and (screen_context.get("is_youtube") or "youtube" in target.lower()):
                q_play = "Veo los resultados en pantalla. ¿Deseas que inicie la reproducción del contenido?"
                answer_play = self._get_dialog().ask_voice(q_play, listen_seconds=10)
                if answer_play:
                    ans_clean = answer_play.lower()
                    if any(w in ans_clean for w in ["si", "sí", "play", "iniciar", "reproducir", "reprodúcelo", "dale"]):
                        self.screen_mapper.trigger_play_content()
                        self.tts.speak("Iniciando reproducción.")

            # Consulta por voz de Verificación y Obviedad del Aprendizaje con Pausa Activa
            if self.interactive_voice:
                q_verify = f"¿Se ejecutó {target} correctamente como lo esperabas?"
                answer_verify = self._get_dialog().ask_voice(q_verify, listen_seconds=10)
                if answer_verify:
                    ans_clean = answer_verify.lower()
                    if any(w in ans_clean for w in ["no", "incorrecto", "fallo", "error", "otra cosa", "mal"]):
                        print(f"[Aprendizaje Descartado] El usuario indicó que '{target}' no se ejecutó como esperaba. Eliminando de memoria...")
                        self.resolver.forget_command(target)
                        self.tts.speak("Entendido, elimino ese aprendizaje para no repetirlo.")
                    elif any(w in ans_clean for w in ["si", "sí", "correcto", "perfecto", "bien", "funciona", "claro"]):
                        self.tts.speak("Excelente, rutina memorizada.")

            return True
        except Exception as e:
            print(f"[OSExecutor Error] Falla al invocar '{execution_target}': {e}")
            return False

    def _voice_consultation_for_project(self, p_name: str, p_type: str) -> tuple[str, str, Path]:
        print("\n==========================================================")
        print("     [V.ANSHEE 🎙️ - Consulta de Proyecto por Voz]        ")
        print("==========================================================")

        # 1. Lenguaje / Tecnología por VOZ con Pausa Activa
        learned_type = self.routine_engine.get_preference("default_project_type")
        if p_type and p_type in ["python", "node", "web"]:
            final_type = p_type
        elif learned_type:
            final_type = learned_type
        elif self.interactive_voice:
            q1 = "¿Con qué lenguaje o tecnología deseas iniciar el proyecto? Por ejemplo Python, Node o Web."
            answer1 = self._get_dialog().ask_voice(q1, listen_seconds=15)
            extracted_type = self._get_dialog().parse_voice_answer("project_type", q1, answer1, ["python", "node", "web"])
            final_type = extracted_type if extracted_type in ["python", "node", "web"] else "python"
            self.routine_engine.save_preference("default_project_type", final_type)
        else:
            final_type = "python"
            self.routine_engine.save_preference("default_project_type", final_type)

        # 2. Ubicación / Carpeta por VOZ con Pausa Activa
        learned_location = self.routine_engine.get_preference("default_project_location")
        target_base = None
        if self.interactive_voice:
            q2 = "¿En qué carpeta deseas alojar el proyecto? Puedes decir Escritorio, Documentos o tu ubicación habitual."
            answer2 = self._get_dialog().ask_voice(q2, listen_seconds=15)
            if answer2:
                ans_clean = answer2.lower()
                if "escritorio" in ans_clean or "desktop" in ans_clean:
                    target_base = Path.home() / "Desktop" / "VANSHEE_Projects"
                elif "documento" in ans_clean or "document" in ans_clean:
                    target_base = Path.home() / "Documents" / "VANSHEE_Projects"
                else:
                    extracted_path = self._get_dialog().parse_voice_answer("location", q2, answer2)
                    if extracted_path and ("/" in extracted_path or "\\" in extracted_path or ":" in extracted_path):
                        target_base = Path(extracted_path)

        if not target_base:
            target_base = Path(learned_location) if learned_location else (Path.home() / "Desktop" / "VANSHEE_Projects")

        self.routine_engine.save_preference("default_project_location", str(target_base))

        # 3. Nombre del proyecto por VOZ con Pausa Activa
        if p_name and p_name != "nuevo_proyecto":
            final_name = p_name
        elif self.interactive_voice:
            q3 = "¿Qué nombre deseas darle al proyecto?"
            answer3 = self._get_dialog().ask_voice(q3, listen_seconds=15)
            extracted_name = self._get_dialog().parse_voice_answer("project_name", q3, answer3)
            final_name = extracted_name.replace(" ", "_") if extracted_name else "mi_proyecto"
        else:
            final_name = "mi_proyecto"

        base_dir = target_base / final_name
        print("==========================================================\n")
        return final_name, final_type, base_dir

    def _create_and_open_project(self, app_target: str, p_type: str, p_name: str) -> bool:
        final_name, final_type, base_dir = self._voice_consultation_for_project(p_name, p_type)
        base_dir.mkdir(parents=True, exist_ok=True)

        msg = f"Creando entorno de proyecto {final_name} en formato {final_type}."
        print(f"[ProjectCreator] {msg} en: {base_dir}")
        self.tts.speak(msg)

        if final_type == "python":
            subprocess.run(f"python -m venv \"{base_dir / '.venv'}\"", shell=True)
            main_file = base_dir / "main.py"
            if not main_file.exists():
                main_file.write_text("# Auto-generado por V.ANSHEE\nprint('Proyecto V.ANSHEE listo.')\n", encoding="utf-8")
        elif final_type in ["node", "web"]:
            subprocess.run("npm init -y", cwd=base_dir, shell=True)

        ide_path, _ = self.resolver.resolve(app_target if app_target else "vscode")
        if ide_path:
            try:
                subprocess.Popen(
                    f'start "" "{ide_path}" "{base_dir}"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.tts.speak("Proyecto creado y cargado en tu editor.")
                return True
            except Exception as e:
                print(f"[ProjectCreator Error] No se pudo abrir el IDE: {e}")
        return False

    def _announce_context(self, action_hint: str = "", user_command: str = "", ask: bool = False) -> str:
        snapshot = self.context_engine.observe(action_hint=action_hint, user_command=user_command)
        print(f"[Contexto V.ANSHEE] App='{snapshot.app_name}' | Ventana='{snapshot.window_title}' | Confianza={snapshot.confidence:.2f}")
        print(f"[Contexto V.ANSHEE] {snapshot.suggestion}")
        if ask and snapshot.suggestion:
            self.tts.speak(snapshot.suggestion)
        return snapshot.app_name

    def _resolve_output_dir(self, requested_path: str = "") -> Path:
        if requested_path:
            path = Path(os.path.expandvars(requested_path)).expanduser()
            if path.suffix:
                return path.parent
            return path
        learned_location = self.routine_engine.get_preference("default_project_location")
        if learned_location:
            return Path(learned_location)
        return Path.home() / "Desktop" / "VANSHEE_Projects"

    def _create_contextual_file(self, step: ActionStep) -> bool:
        app_name = self._announce_context(action_hint=step.target, user_command=step.target, ask=False)
        params = step.parameters
        language = params.language or params.project_type or "txt"
        file_name = safe_filename(params.file_name or params.project_name or "nuevo_archivo")
        base_dir = self._resolve_output_dir(params.path)
        file_path = ensure_file_extension(base_dir / file_name, language)

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if not file_path.exists():
                initial_content = params.content or self._template_for_file(file_path, language)
                file_path.write_text(initial_content, encoding="utf-8")

            msg = f"Archivo creado o disponible: {file_path}"
            print(f"[FileCreator] {msg}")
            self.tts.speak("Archivo creado y listo.")

            if app_name == "vscode" or step.target.lower() in ["vscode", "vs code", "visual code", "visual studio code"]:
                ide_path, _ = self.resolver.resolve("vscode")
                if ide_path:
                    subprocess.Popen(
                        f'start "" "{ide_path}" "{file_path}"',
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            return True
        except Exception as e:
            print(f"[FileCreator Error] No se pudo crear archivo: {e}")
            self.tts.speak("No pude crear el archivo solicitado.")
            return False

    def _write_contextual_text(self, step: ActionStep) -> bool:
        params = step.parameters
        content = params.content or step.target
        if not content:
            self.tts.speak("Necesito el texto que deseas escribir.")
            return False

        file_name = safe_filename(params.file_name or "nota_vanshee", default="nota_vanshee")
        base_dir = self._resolve_output_dir(params.path)
        file_path = ensure_file_extension(base_dir / file_name, params.language or "txt")

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("a", encoding="utf-8") as handle:
                handle.write(content.strip() + "\n")
            print(f"[TextWriter] Texto escrito en: {file_path}")
            self.tts.speak("Texto escrito correctamente.")
            return True
        except Exception as e:
            print(f"[TextWriter Error] No se pudo escribir texto: {e}")
            self.tts.speak("No pude escribir el texto solicitado.")
            return False

    def _template_for_file(self, file_path: Path, language: str) -> str:
        suffix = file_path.suffix.lower()
        if language == "python" or suffix == ".py":
            return "def main():\n    print('Archivo creado por V.ANSHEE')\n\n\nif __name__ == '__main__':\n    main()\n"
        if language in ["javascript", "node"] or suffix == ".js":
            return "console.log('Archivo creado por V.ANSHEE');\n"
        if language == "typescript" or suffix == ".ts":
            return "const message: string = 'Archivo creado por V.ANSHEE';\nconsole.log(message);\n"
        if language in ["web", "html"] or suffix == ".html":
            return "<!doctype html>\n<html lang=\"es\">\n<head>\n  <meta charset=\"utf-8\">\n  <title>V.ANSHEE</title>\n</head>\n<body>\n</body>\n</html>\n"
        if language == "markdown" or suffix == ".md":
            return "# Archivo creado por V.ANSHEE\n"
        return ""
