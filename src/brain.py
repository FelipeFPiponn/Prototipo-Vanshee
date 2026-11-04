import re
import time
import random
import threading
from datetime import datetime
from dataclasses import dataclass

from src.audio.tts_engine import TTSEngine
from src.context_awareness import ContextAwarenessEngine, ContextSnapshot
from src.executor.os_executor import OSExecutor
from src.memory_store import MemoryStore
from src.nlu.intent_parser import IntentParser, ParsedPipeline, ActionStep, StepParameters
from src.semantic_memory import SemanticMemory


@dataclass
class BrainResult:
    success: bool
    response_text: str
    plan_summary: str
    context: ContextSnapshot


class VansheeBrain:
    """Coordinador central: percepción, memoria, razonamiento híbrido (Gemini + Ollama Offline), acción y ejecución de baja latencia."""

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

    def _build_context_prompt(self, context: ContextSnapshot, semantic_context: str) -> str:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        memory_summary = self.memory.summarize_for_prompt(context.app_name)
        return (
            f"- Fecha y hora local: {now_str}\n"
            f"- Aplicación activa en pantalla: {context.app_name or 'Escritorio'}\n"
            f"- Título de ventana activa: {context.window_title or 'N/A'}\n"
            f"- Memoria reciente y hechos del usuario: {memory_summary}\n"
            f"- Recuerdos semánticos relevantes: {semantic_context}"
        )

    def _build_lazy_context_prompt(self, clean_text: str, context: ContextSnapshot) -> str:
        """Solo consulta SQLite y memoria semántica cuando el comando requiere razonamiento del LLM."""
        semantic_context = self.semantic_memory.summarize_matches(clean_text)
        return self._build_context_prompt(context, semantic_context)

    def parse_only(self, user_text: str) -> ParsedPipeline:
        clean_text = user_text.strip()
        if not clean_text:
            return ParsedPipeline(raw_text="", steps=[])
        context = self.context_engine.observe(action_hint="parse_only", user_command=clean_text, log_db=False)
        return self.parser.parse(clean_text, context_prompt=lambda: self._build_lazy_context_prompt(clean_text, context))

    def handle_user_input(self, user_text: str) -> BrainResult:
        clean_text = user_text.strip()
        context = self.context_engine.observe(action_hint="user_input", user_command=clean_text, log_db=False)

        if not clean_text:
            response = "No detecté ninguna instrucción clara."
            if self.speak_tts:
                self.tts.speak(response, block=False)
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

        polite_terms = {
            "gracias", "muchas gracias", "ok", "vale", "perfecto", "genial",
            "excelente", "bueno", "bien", "listo", "de acuerdo", "entendido", "si"
        }
        if norm in polite_terms:
            if "gracias" in norm:
                response = random.choice([
                    "¡Con mucho gusto! Aquí estoy para lo que necesites.",
                    "¡De nada! ¡Es un placer ayudarte!",
                    "¡Siempre a tu servicio!"
                ])
            else:
                response = random.choice([
                    "¡Perfecto! Seguimos atentos.",
                    "¡Genial! Avísame si necesitas algo más.",
                    "¡Excelente!"
                ])
            if self.speak_tts:
                self.tts.speak(response, block=False)
            return self._finish(clean_text, context, None, response, True)

        # 1. Comandos aprendidos previamente en base de datos (0ms)
        learned_target = self.executor.resolver.get_learned_command(clean_text)
        if learned_target:
            pipeline = ParsedPipeline(
                raw_text=clean_text,
                steps=[ActionStep(intent="OPEN_APP", target=learned_target, parameters=StepParameters())]
            )
            success = self.executor.execute_pipeline(pipeline)
            response = getattr(self.executor, "last_action_message", "") or f"Ejecutando '{learned_target}' que aprendí anteriormente."
            if self.speak_tts:
                self.tts.speak(response, block=False)
            return self._finish(clean_text, context, pipeline, response, success)

        # 2. Parsear con el motor NLU Híbrido (Fast-paths 0ms -> Lazy Context -> Gemini Online -> Ollama Offline)
        pipeline = self.parser.parse(
            clean_text,
            context_prompt=lambda: self._build_lazy_context_prompt(clean_text, context)
        )
        plan_summary = self._summarize_plan(pipeline)
        print(f"[Brain] Plan ({pipeline.provider_used}): {plan_summary}")

        # 2.5 Respuesta conversacional directa (CHAT)
        if pipeline.steps and all(s.intent == "CHAT" for s in pipeline.steps):
            response = pipeline.reply or pipeline.steps[0].parameters.content or "Aquí estoy para ayudarte."
            print(f"[Brain Chat]: {response}")
            if self.speak_tts:
                self.tts.speak(response, block=False)
            return self._finish(clean_text, context, pipeline, response, True)

        if not pipeline.steps or any(s.intent == "UNKNOWN" for s in pipeline.steps):
            response = pipeline.reply or self._fallback_response(context)
            if self.speak_tts:
                self.tts.speak(response, block=False)
            return self._finish(clean_text, context, pipeline, response, bool(pipeline.reply))

        success = self.executor.execute_pipeline(pipeline)
        if success:
            response = pipeline.reply or getattr(self.executor, "last_action_message", "") or "¡Listo! Instrucción ejecutada."
        else:
            response = getattr(self.executor, "last_action_message", "") or "Mmm, no pude completar esa acción."
        print(f"[Brain] Resultado: {response}")

        if self.speak_tts:
            self.tts.speak(response, block=False)

        return self._finish(clean_text, context, pipeline, response, success)

    def execute_parsed_pipeline(self, pipeline: ParsedPipeline, user_text: str = "") -> BrainResult:
        raw = user_text.strip() if user_text else pipeline.raw_text
        context = self.context_engine.observe(action_hint="user_input", user_command=raw, log_db=False)
        
        if not pipeline.steps:
            response = pipeline.reply or self._fallback_response(context)
            if self.speak_tts:
                self.tts.speak(response, block=False)
            return self._finish(raw, context, pipeline, response, bool(pipeline.reply))

        success = self.executor.execute_pipeline(pipeline)
        if success:
            response = getattr(self.executor, "last_action_message", "") or pipeline.reply or "Instrucción ejecutada correctamente."
        else:
            response = getattr(self.executor, "last_action_message", "") or "La instrucción no pudo completarse con éxito."

        if self.speak_tts:
            self.tts.speak(response, block=False)

        return self._finish(raw, context, pipeline, response, success)

    def observe_current_context(self) -> ContextSnapshot:
        context = self.context_engine.observe(action_hint="idle", log_db=False)
        return context

    def _persist_memory_async(
        self,
        user_text: str,
        context: ContextSnapshot,
        pipeline: ParsedPipeline | None,
        plan_summary: str,
        response: str,
        success: bool,
    ):
        try:
            self._learn_obvious_preferences(user_text, context)
            if success and pipeline:
                self._learn_from_success(user_text, context, pipeline)
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
        except Exception as e:
            print(f"[Brain Memory Async Warning]: {e}")

    def _finish(
        self,
        user_text: str,
        context: ContextSnapshot,
        pipeline: ParsedPipeline | None,
        response: str,
        success: bool,
    ) -> BrainResult:
        plan_summary = self._summarize_plan(pipeline) if pipeline else "sin_plan"
        threading.Thread(
            target=self._persist_memory_async,
            args=(user_text, context, pipeline, plan_summary, response, success),
            daemon=True,
            name="BrainMemoryPersistThread",
        ).start()
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
