from dataclasses import dataclass

from src.audio.tts_engine import TTSEngine
from src.context_awareness import ContextAwarenessEngine, ContextSnapshot
from src.executor.os_executor import OSExecutor
from src.memory_store import MemoryStore
from src.nlu.intent_parser import IntentParser, ParsedPipeline
from src.semantic_memory import SemanticMemory


@dataclass
class BrainResult:
    success: bool
    response_text: str
    plan_summary: str
    context: ContextSnapshot


class VansheeBrain:
    """Coordinador central: percepción, memoria, razonamiento, acción y aprendizaje."""

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

        self._learn_obvious_preferences(clean_text, context)
        semantic_context = self.semantic_memory.summarize_matches(clean_text)
        print(f"[Brain] Memoria semántica relevante: {semantic_context}")
        pipeline = self.parser.parse(clean_text)
        plan_summary = self._summarize_plan(pipeline)
        print(f"[Brain] Plan: {plan_summary}")

        if not pipeline.steps:
            response = self._fallback_response(context)
            if self.speak_tts:
                self.tts.speak(response)
            return self._finish(clean_text, context, pipeline, response, False)

        success = self.executor.execute_pipeline(pipeline)
        if success:
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
