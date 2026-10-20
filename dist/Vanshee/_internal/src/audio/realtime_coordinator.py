import time
import asyncio
from typing import Optional, Callable
import numpy as np

from src.audio.stream_recorder import StreamRecorder
from src.audio.streaming_stt import StreamingSTT
from src.audio.stt_whisper import WhisperSTT
from src.nlu.intent_parser import IntentParser, ParsedPipeline
from src.executor.os_executor import OSExecutor


class RealtimeVoiceCoordinator:
    """Coordinador central de la canalización de voz en tiempo real (Real-Time Voice Pipeline).
    
    Orquesta la captura continua (StreamRecorder), transcripción progresiva (StreamingSTT),
    despacho inmediato de intenciones (IntentParser) y ejecución en Windows (OSExecutor).
    """

    def __init__(
        self,
        whisper_stt: Optional[WhisperSTT] = None,
        intent_parser: Optional[IntentParser] = None,
        executor: Optional[OSExecutor] = None,
        on_event: Optional[Callable[[str, dict], None]] = None,
        silence_timeout_sec: float = 0.30,
        speech_threshold: float = 0.45,
        device_index: Optional[int] = None,
    ):
        self.stt = whisper_stt or WhisperSTT()
        self.parser = intent_parser or IntentParser()
        self.executor = executor or OSExecutor()
        self.on_event = on_event

        self.streaming_stt = StreamingSTT(
            whisper_stt=self.stt,
            on_partial=self._handle_partial,
            on_final=self._handle_final,
            partial_interval_sec=0.30
        )

        self.recorder = StreamRecorder(
            sample_rate=16000,
            chunk_samples=512,
            silence_timeout_sec=silence_timeout_sec,
            speech_threshold=speech_threshold,
            device_index=device_index,
            on_speech_start=self._handle_speech_start,
            on_speech_chunk=self._handle_speech_chunk,
            on_speech_end=self._handle_speech_end
        )

        self.is_active = False

    def _emit(self, event_type: str, data: dict):
        if self.on_event:
            try:
                self.on_event(event_type, data)
            except Exception as e:
                print(f"[RealtimeCoordinator Event Error]: {e}")

    def _handle_speech_start(self):
        print("\n[V.ANSHEE Real-Time]: Usuario empezo a hablar...")
        self.streaming_stt.on_speech_start()
        self._emit("speech_started", {"timestamp": time.time()})

    def _handle_speech_chunk(self, chunk: np.ndarray, speech_prob: float):
        self.streaming_stt.feed_chunk(chunk, speech_prob)

    def _handle_partial(self, partial_text: str):
        print(f"[Real-Time Parcial]: {partial_text}")
        self._emit("partial_transcript", {"text": partial_text, "timestamp": time.time()})

    def _handle_speech_end(self, full_audio: np.ndarray):
        t0 = time.perf_counter()
        print(f"[V.ANSHEE Real-Time]: Fin de habla detectado ({len(full_audio)/16000:.2f}s). Transcribiendo...")
        
        # 1. Transcripción consolidada
        final_text = self.streaming_stt.finalize_utterance(full_audio)
        t_stt = (time.perf_counter() - t0) * 1000.0

        if not final_text:
            print("[Real-Time]: Audio descartado (sin voz inteligible).")
            self._emit("speech_idle", {})
            return

        print(f"[Real-Time Final ({t_stt:.0f}ms)]: '{final_text}'")
        self._emit("final_transcript", {"text": final_text, "stt_latency_ms": round(t_stt, 1)})

        # 2. Despacho NLU ultra-rápido (0ms con métodos _fast_*)
        t_nlu_0 = time.perf_counter()
        pipeline = self.parser.parse(final_text)
        t_nlu = (time.perf_counter() - t_nlu_0) * 1000.0

        if not pipeline.steps:
            print(f"[Real-Time NLU]: No se detectaron pasos para '{final_text}'.")
            return

        print(f"[Real-Time NLU ({t_nlu:.0f}ms)]: {len(pipeline.steps)} paso(s) -> {[s.intent for s in pipeline.steps]}")
        self._emit("executing_command", {"pipeline": [s.model_dump() for s in pipeline.steps], "nlu_latency_ms": round(t_nlu, 1)})

        # 3. Ejecución en el sistema operativo
        t_exec_0 = time.perf_counter()
        success = self.executor.execute_pipeline(pipeline)
        t_exec = (time.perf_counter() - t_exec_0) * 1000.0
        t_total = (time.perf_counter() - t0) * 1000.0

        print(f"[Real-Time Ejecucion ({t_exec:.0f}ms) | Total E2E: {t_total:.0f}ms]: Exito={success}")
        self._emit("command_finished", {
            "success": success,
            "message": self.executor.last_action_message,
            "total_latency_ms": round(t_total, 1)
        })

    def _handle_final(self, final_text: str):
        pass

    def start(self):
        """Inicia el bucle de escucha y procesamiento en tiempo real."""
        self.is_active = True
        self.recorder.start()
        print("[RealtimeVoiceCoordinator] Canalización de voz en tiempo real activa.")

    def stop(self):
        """Detiene la canalización de audio."""
        self.is_active = False
        self.recorder.stop()
        self.streaming_stt.close()
        print("[RealtimeVoiceCoordinator] Canalización de voz detenida.")
