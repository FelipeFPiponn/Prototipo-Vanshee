import re
import time
from dataclasses import dataclass

from src.audio.tts_engine import TTSEngine
from src.context_awareness import ContextAwarenessEngine, ContextSnapshot
from src.executor.os_executor import OSExecutor
from src.memory_store import MemoryStore
from src.nlu.intent_parser import IntentParser, ParsedPipeline, ActionStep, StepParameters
from src.semantic_memory import SemanticMemory


@dataclass
class LearningSession:
    original_command: str
    proposed_target: str = ""
    proposed_type: str = "app"
    state: str = "PROBING"  # "PROBING" (esperando app/enlace) | "CONFIRMING" (esperando confirmación sí/no)
    trial_executed: bool = False
    attempt_count: int = 1


@dataclass
class BrainResult:
    success: bool
    response_text: str
    plan_summary: str
    context: ContextSnapshot


class VansheeBrain:
    """Coordinador central: percepción, memoria, razonamiento, acción y aprendizaje con confirmación en cadena."""

    def __init__(
        self,
        tts: TTSEngine | None = None,
        parser: IntentParser | None = None,
        executor: OSExecutor | None = None,
        memory: MemoryStore | None = None,
        semantic_memory: SemanticMemory | None = None,
        context_engine: ContextAwarenessEngine | None = None,
        interactive_voice: bool = False,
        speak_tts: bool = True,
    ):
        self.speak_tts = speak_tts
        self.tts = tts or TTSEngine()
        self.memory = memory or MemoryStore()
        self.semantic_memory = semantic_memory or SemanticMemory()
        self.parser = parser or IntentParser()
        self.executor = executor or OSExecutor(tts=self.tts, interactive_voice=interactive_voice)
        self.context_engine = context_engine or self.executor.context_engine
        self.learning_session: LearningSession | None = None
        self.last_executed_command: str = ""
        self.last_executed_target: str = ""
        self.last_executed_type: str = "app"
        self.last_execution_time: float = 0.0

    def is_awaiting_user_feedback(self) -> bool:
        """Indica si Vanshee está actualmente en un diálogo interactivo de sondeo para aprender una acción."""
        return self.learning_session is not None

    def parse_only(self, user_text: str) -> ParsedPipeline:
        clean_text = user_text.strip()
        if not clean_text:
            return ParsedPipeline(raw_text="", steps=[])
        return self.parser.parse(clean_text)

    def handle_user_input(self, user_text: str) -> BrainResult:
        clean_text = user_text.strip()
        context = self.context_engine.observe(action_hint="user_input", user_command=clean_text)
        print(f"[Brain] Contexto activo: {context.app_name} | {context.window_title}")

        if not clean_text:
            response = "No detecté ninguna instrucción clara."
            if self.speak_tts:
                self.tts.speak(response)
            return self._finish(clean_text, context, None, response, False)

        lowered = clean_text.lower().strip()
        norm = (
            lowered.strip("¿?¡!.,;: \t")
            .replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
        )

        # -------------------------------------------------------------
        # 1. SI HAY UNA SESIÓN DE APRENDIZAJE ACTIVA (PROBING)
        # -------------------------------------------------------------
        if self.learning_session:
            session = self.learning_session

            # Cancelación explícita
            if norm in ["cancela", "cancelar", "nada", "olvidalo", "olvídalo", "dejalo asi", "déjalo así", "ignora", "salir", "detener"]:
                self.learning_session = None
                response = "Entendido, proceso de aprendizaje cancelado."
                print(f"[Brain Aprendizaje]: {response}")
                if self.speak_tts:
                    self.tts.speak(response)
                return self._finish(clean_text, context, None, response, True)

            # Extraer el programa o enlace indicado por el usuario
            extracted_target = re.sub(
                r"^(?:es\s+|abre\s+|ejecuta\s+|inicia\s+|es\s+una\s+app\s+|es\s+un\s+programa\s+|es\s+la\s+app\s+de\s+|es\s+el\s+programa\s+de\s+|es\s+la\s+web\s+de\s+|la\s+app\s+de\s+|el\s+programa\s+de\s+|la\s+web\s+de\s+|el\s+|la\s+)",
                "",
                clean_text,
                flags=re.IGNORECASE
            ).strip().rstrip(".")
            if not extracted_target:
                extracted_target = clean_text

            is_url = (
                extracted_target.startswith("http://") or
                extracted_target.startswith("https://") or
                any(extracted_target.lower().endswith(ext) for ext in [".com", ".cl", ".org", ".net", ".io", ".tv", ".app", ".es"]) or
                "www." in extracted_target.lower()
            )
            cmd_type = "url" if is_url else "app"
            if is_url and not extracted_target.startswith("http"):
                extracted_target = f"https://{extracted_target}"

            # Ejecutar inmediatamente la acción por voz con máxima prioridad
            pipeline = ParsedPipeline(
                raw_text=session.original_command,
                steps=[ActionStep(intent="OPEN_APP", target=extracted_target, parameters=StepParameters())]
            )
            success = self.executor.execute_pipeline(pipeline)

            if success:
                # Si la tarea se realiza con normalidad, se guarda y se mantiene sin preguntar si está correcta
                self.executor.resolver.save_learned_command(
                    session.original_command, extracted_target, command_type=cmd_type
                )
                self.memory.remember_fact(
                    f"learned_cmd_{session.original_command}", extracted_target,
                    source="user_probe", confidence=1.0
                )
                self.semantic_memory.remember(
                    text=session.original_command,
                    kind="learned_association",
                    metadata={"target": extracted_target, "type": cmd_type},
                    importance=1.0,
                    success=True
                )
                self.last_executed_command = session.original_command
                self.last_executed_target = extracted_target
                self.last_executed_type = cmd_type
                self.last_execution_time = time.time()
                self.learning_session = None

                response = f"Listo, ejecuté '{extracted_target}' y lo guardé para '{session.original_command}'."
                print(f"[Brain Aprendizaje Completado]: {response}")
                if self.speak_tts:
                    self.tts.speak(response)
                return self._finish(clean_text, context, pipeline, response, True)
            else:
                # Solo si falla al ejecutarse (no se encontró), solicita otro nombre/ruta
                response = (
                    f"Intenté ejecutar '{extracted_target}', pero no se encontró en el equipo. "
                    f"¿Qué otro programa o enlace exacto deberíamos probar para '{session.original_command}'?"
                )
                print(f"[Brain Prueba Fallida]: {response}")
                if self.speak_tts:
                    self.tts.speak(response)
                return self._finish(clean_text, context, pipeline, response, False)

        # -------------------------------------------------------------
        # 2. REMODELADO POR DEMANDA DEL USUARIO
        # Solo si el usuario indica que la tarea previa NO se realizó correctamente
        # -------------------------------------------------------------
        recent_time = (time.time() - self.last_execution_time)
        rejection_terms = {
            "no", "no era eso", "eso no era", "esta malo", "está malo", "esta mal", "está mal",
            "malo", "incorrecto", "te equivocaste", "te equivocaste de app", "esa no era",
            "esa no es", "cambiar", "remodelar", "cambia", "cambialo", "cambiala", "otra cosa",
            "no era esa", "no funciona", "esta equivocado", "está equivocado",
            "era eso", "era esa", "es eso", "es esa", "no es eso", "no es esa", "eso no", "esa no", "no era", "no es"
        }
        is_rejection_phrase = (
            norm in rejection_terms or
            bool(re.search(r"^(?:no[,\s]+|cambia(?:lo)?\s+(?:a|por)\s+|remodela\s+(?:a|por)\s+|est[aá]\s+mal[oa][,\s]*|te\s+equivocaste\s*)", clean_text, re.IGNORECASE))
        )

        if is_rejection_phrase and self.last_executed_command and recent_time < 45.0:
            prev_cmd = self.last_executed_command
            # 1. Olvidar de inmediato la asociación anterior en base de datos
            self.executor.resolver.forget_command(prev_cmd)

            # 2. ¿El usuario especificó el nuevo programa/enlace en la misma frase? (ej: "no, cambia a la calculadora", "está malo, abre opera gx")
            candidate_text = re.sub(
                r"^(?:no[,\s]+|cambia(?:lo)?\s+(?:a|por)\s+|cambiar\s+(?:a|por)\s+|remodela\s+(?:a|por)\s+|remodelar\s+(?:a|por)\s+|mejor\s+(?:a\s+)?|est[aá]\s+mal[oa][,\s]*)+",
                "",
                clean_text,
                flags=re.IGNORECASE
            ).strip()
            candidate_norm = candidate_text.lower().strip("¿?¡!.,;: \t")

            is_pure_rejection = (
                (not candidate_norm) or
                (candidate_norm in rejection_terms) or
                (norm in rejection_terms) or
                candidate_norm in ["era eso", "era esa", "es eso", "es esa", "eso no", "esa no"]
            )

            if not is_pure_rejection and len(candidate_text) >= 2:
                extracted_target = re.sub(
                    r"^(?:es\s+|abre\s+|ejecuta\s+|inicia\s+|es\s+una\s+app\s+|es\s+un\s+programa\s+|es\s+la\s+app\s+de\s+|es\s+el\s+programa\s+de\s+|es\s+la\s+web\s+de\s+|la\s+app\s+de\s+|el\s+programa\s+de\s+|la\s+web\s+de\s+|el\s+|la\s+)",
                    "",
                    candidate_text,
                    flags=re.IGNORECASE
                ).strip().rstrip(".")
                if not extracted_target:
                    extracted_target = candidate_text

                is_url = (
                    extracted_target.startswith("http://") or
                    extracted_target.startswith("https://") or
                    any(extracted_target.lower().endswith(ext) for ext in [".com", ".cl", ".org", ".net", ".io", ".tv", ".app", ".es"]) or
                    "www." in extracted_target.lower()
                )
                cmd_type = "url" if is_url else "app"
                if is_url and not extracted_target.startswith("http"):
                    extracted_target = f"https://{extracted_target}"

                pipeline = ParsedPipeline(
                    raw_text=prev_cmd,
                    steps=[ActionStep(intent="OPEN_APP", target=extracted_target, parameters=StepParameters())]
                )
                success = self.executor.execute_pipeline(pipeline)

                if success:
                    self.executor.resolver.save_learned_command(prev_cmd, extracted_target, command_type=cmd_type)
                    self.last_executed_command = prev_cmd
                    self.last_executed_target = extracted_target
                    self.last_executed_type = cmd_type
                    self.last_execution_time = time.time()
                    self.learning_session = None

                    response = f"Entendido. Remodelé la acción a '{extracted_target}' para '{prev_cmd}'."
                    print(f"[Brain Remodelado Directo]: {response}")
                    if self.speak_tts:
                        self.tts.speak(response)
                    return self._finish(clean_text, context, pipeline, response, True)
                else:
                    self.learning_session = LearningSession(original_command=prev_cmd, state="PROBING")
                    response = f"Intenté ejecutar '{extracted_target}', pero no se encontró en el equipo. ¿Qué otro programa o enlace exacto deberíamos probar para '{prev_cmd}'?"
                    print(f"[Brain Remodelado Fallido]: {response}")
                    if self.speak_tts:
                        self.tts.speak(response)
                    return self._finish(clean_text, context, pipeline, response, False)
            else:
                # El usuario solo indicó que la tarea estuvo mala -> iniciar sondeo para remodelar
                self.learning_session = LearningSession(original_command=prev_cmd, state="PROBING")
                response = f"Entendido, la acción anterior fue descartada. Vamos a remodelarla: ¿Qué programa, aplicación o enlace exacto debería ejecutar para '{prev_cmd}'?"
                print(f"[Brain Inicio de Remodelado]: {response}")
                if self.speak_tts:
                    self.tts.speak(response)
                return self._finish(clean_text, context, None, response, False)

        # -------------------------------------------------------------
        # 3. AFIRMACIONES Y CORTESÍAS SUELTAS (ej: "gracias", "ok", "perfecto")
        # -------------------------------------------------------------
        polite_terms = {
            "gracias", "muchas gracias", "ok", "vale", "perfecto", "genial",
            "excelente", "bueno", "bien", "listo", "de acuerdo", "entendido", "si"
        }
        if norm in polite_terms:
            response = "¡A tu servicio!" if "gracias" in norm else "¡Perfecto!"
            if self.speak_tts:
                self.tts.speak(response)
            return self._finish(clean_text, context, None, response, True)

        self._learn_obvious_preferences(clean_text, context)
        semantic_context = self.semantic_memory.summarize_matches(clean_text)
        print(f"[Brain] Memoria semántica relevante: {semantic_context}")

        # -------------------------------------------------------------
        # 4. EJECUCIÓN DIRECTA: PRIORIDAD ABSOLUTA A LA ACCIÓN POR VOZ
        # -------------------------------------------------------------
        # 4.1. Verificar si la frase ya fue aprendida previamente en la base de datos
        learned_target = self.executor.resolver.get_learned_command(clean_text)
        if learned_target:
            pipeline = ParsedPipeline(
                raw_text=clean_text,
                steps=[ActionStep(intent="OPEN_APP", target=learned_target, parameters=StepParameters())]
            )
            success = self.executor.execute_pipeline(pipeline)
            if success:
                self.last_executed_command = clean_text
                self.last_executed_target = learned_target
                self.last_execution_time = time.time()
            response = getattr(self.executor, "last_action_message", "") or f"Ejecutando '{learned_target}' que aprendí anteriormente."
            if self.speak_tts:
                self.tts.speak(response)
            return self._finish(clean_text, context, pipeline, response, success)

        # 4.2. Parsear con el motor NLU
        pipeline = self.parser.parse(clean_text)
        plan_summary = self._summarize_plan(pipeline)
        print(f"[Brain] Plan: {plan_summary}")

        # 4.3. Si la acción no se reconoce o la aplicación objetivo no existe, activar sondeo de aprendizaje
        needs_probe = (
            not pipeline.steps or
            any(s.intent == "UNKNOWN" for s in pipeline.steps) or
            (
                len(pipeline.steps) == 1 and
                pipeline.steps[0].intent == "OPEN_APP" and
                not self.executor.resolver.resolve(pipeline.steps[0].target)[0]
            )
        )

        if needs_probe:
            self.learning_session = LearningSession(original_command=clean_text, state="PROBING")
            response = f"No tengo registrada la acción '{clean_text}'. ¿Qué programa, aplicación o página web te gustaría que ejecute cuando me lo pidas?"
            print(f"[Brain Sondeo de Aprendizaje Inicial]: {response}")
            if self.speak_tts:
                self.tts.speak(response)
            return self._finish(clean_text, context, pipeline, response, False)

        success = self.executor.execute_pipeline(pipeline)
        if success:
            self.last_executed_command = clean_text
            self.last_executed_target = getattr(pipeline.steps[0], "target", "") if pipeline.steps else ""
            self.last_execution_time = time.time()
            response = getattr(self.executor, "last_action_message", "") or "Instrucción ejecutada correctamente."
        else:
            response = getattr(self.executor, "last_action_message", "") or "La instrucción no pudo completarse con éxito."
        print(f"[Brain] Resultado: {response}")

        if self.speak_tts:
            self.tts.speak(response)

        if success:
            self._learn_from_success(clean_text, context, pipeline)

        return self._finish(clean_text, context, pipeline, response, success)

    def execute_parsed_pipeline(self, pipeline: ParsedPipeline, user_text: str = "") -> BrainResult:
        raw = user_text.strip() if user_text else pipeline.raw_text
        context = self.context_engine.observe(action_hint="user_input", user_command=raw)
        
        if not pipeline.steps:
            response = self._fallback_response(context)
            if self.speak_tts:
                self.tts.speak(response)
            return self._finish(raw, context, pipeline, response, False)

        success = self.executor.execute_pipeline(pipeline)
        if success:
            response = getattr(self.executor, "last_action_message", "") or "Instrucción ejecutada correctamente."
        else:
            response = getattr(self.executor, "last_action_message", "") or "La instrucción no pudo completarse con éxito."

        if self.speak_tts:
            self.tts.speak(response)

        if success:
            self._learn_from_success(raw, context, pipeline)

        return self._finish(raw, context, pipeline, response, success)

    def observe_current_context(self) -> ContextSnapshot:
        context = self.context_engine.observe(action_hint="idle")
        print(f"[Brain] Observación: {context.suggestion}")
        return context

    def _finish(
        self,
        user_text: str,
        context: ContextSnapshot,
        pipeline: ParsedPipeline | None,
        response: str,
        success: bool,
    ) -> BrainResult:
        plan_summary = self._summarize_plan(pipeline) if pipeline else "sin_plan"
        self.memory.log_interaction(
            user_text=user_text,
            app_name=context.app_name,
            window_title=context.window_title,
            plan_summary=plan_summary,
            response_text=response,
            success=success,
            confidence=context.confidence,
        )
        self.semantic_memory.remember(
            text=user_text,
            kind="successful_command" if success else "attempted_command",
            metadata={
                "app_name": context.app_name,
                "window_title": context.window_title,
                "plan_summary": plan_summary,
                "response": response,
            },
            importance=0.85 if success else 0.35,
            success=success,
        )
        return BrainResult(
            success=success,
            response_text=response,
            plan_summary=plan_summary,
            context=context,
        )

    def _summarize_plan(self, pipeline: ParsedPipeline | None) -> str:
        if not pipeline or not pipeline.steps:
            return "sin_acciones"
        return " -> ".join(f"{step.intent}:{step.target}" for step in pipeline.steps)

    def _fallback_response(self, context: ContextSnapshot) -> str:
        if context.suggestion:
            return context.suggestion
        return "No entendí con suficiente claridad. Puedo observar el contexto actual y ayudarte paso a paso."

    def _learn_obvious_preferences(self, user_text: str, context: ContextSnapshot):
        lowered = user_text.lower()
        if context.app_name:
            self.memory.remember_fact("last_active_app", context.app_name, source="context", confidence=context.confidence)
        if "escritorio" in lowered:
            self.memory.remember_fact("preferred_location_hint", "Desktop", source="voice", confidence=0.8)
        elif "documentos" in lowered or "documento" in lowered:
            self.memory.remember_fact("preferred_location_hint", "Documents", source="voice", confidence=0.8)

    def _learn_from_success(self, user_text: str, context: ContextSnapshot, pipeline: ParsedPipeline):
        self.memory.remember_fact("last_successful_command", user_text, source="executor", confidence=1.0)
        self.memory.remember_fact("last_successful_app", context.app_name, source="context", confidence=context.confidence)
        if pipeline.steps:
            self.memory.remember_fact("last_successful_plan", self._summarize_plan(pipeline), source="brain", confidence=1.0)
