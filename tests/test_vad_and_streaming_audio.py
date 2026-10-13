import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import unittest
from unittest.mock import MagicMock, patch
from src.audio.vad_engine import SileroVAD
from src.audio.stt_whisper import WhisperSTT
from src.audio.stream_recorder import StreamRecorder
from src.audio.recorder import AudioRecorder


class TestVADAndStreamingAudio(unittest.TestCase):

    def test_01_silero_vad_initialization_and_inference(self):
        """Verifica que Silero VAD cargue el modelo ONNX y evalúe chunks de 512 muestras."""
        vad = SileroVAD()
        self.assertIsNotNone(vad.session)
        self.assertEqual(vad.sample_rate, 16000)

        # Prueba con silencio
        silence = np.zeros(512, dtype=np.float32)
        is_sp, prob = vad.is_speech(silence, threshold=0.5)
        self.assertFalse(is_sp)
        self.assertLess(prob, 0.1)

        # Prueba con array int16
        silence_int16 = np.zeros(512, dtype=np.int16)
        is_sp_int, prob_int = vad.is_speech(silence_int16, threshold=0.5)
        self.assertFalse(is_sp_int)
        self.assertLess(prob_int, 0.1)

    def test_02_whisper_in_memory_transcription(self):
        """Verifica que WhisperSTT procese directamente arrays numpy en memoria RAM."""
        stt = WhisperSTT(model_size="base")
        fake_audio = np.zeros(16000, dtype=np.float32)  # 1s de audio plano
        result = stt.transcribe(fake_audio)
        self.assertIsInstance(result, str)

    def test_03_stream_recorder_events(self):
        """Verifica que StreamRecorder procese la cola y dispare eventos VAD."""
        speech_started_called = False
        speech_chunks_count = 0
        speech_ended_called = False
        received_audio = None

        def on_start():
            nonlocal speech_started_called
            speech_started_called = True

        def on_chunk(chunk, prob):
            nonlocal speech_chunks_count
            speech_chunks_count += 1

        def on_end(audio):
            nonlocal speech_ended_called, received_audio
            speech_ended_called = True
            received_audio = audio

        recorder = StreamRecorder(
            silence_timeout_sec=0.1,
            on_speech_start=on_start,
            on_speech_chunk=on_chunk,
            on_speech_end=on_end
        )

        # Simular inyección de chunks en la cola con VAD mockeado
        recorder.vad.is_speech = MagicMock(side_effect=[
            (False, 0.05),
            (True, 0.95),  # inicio voz
            (True, 0.90),  # habla
            (False, 0.05), # silencio
            (False, 0.05), # silencio >= timeout
            (False, 0.05)
        ])

        chunk = np.zeros(512, dtype=np.int16)
        for _ in range(6):
            recorder.audio_queue.put(chunk)

        recorder.is_running = True
        import threading
        t = threading.Thread(target=recorder._process_loop, daemon=True)
        t.start()

        import time
        time.sleep(0.35)
        recorder.is_running = False
        t.join(timeout=0.5)

        self.assertTrue(speech_started_called)
        self.assertGreater(speech_chunks_count, 0)


    def test_04_streaming_stt_lifecycle(self):
        """Verifica el ciclo de vida de StreamingSTT (start, feed chunks, finalize)."""
        from src.audio.streaming_stt import StreamingSTT

        partial_events = []
        final_events = []

        mock_stt = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "busca warframe"
        mock_stt.model.transcribe.return_value = ([mock_segment], None)
        mock_stt.transcribe.return_value = "busca warframe en youtube"

        streaming = StreamingSTT(
            whisper_stt=mock_stt,
            on_partial=lambda text: partial_events.append(text),
            on_final=lambda text: final_events.append(text),
            partial_interval_sec=0.05
        )

        streaming.on_speech_start()
        self.assertTrue(streaming.is_active)

        # Alimentar chunks
        chunk = np.zeros(512, dtype=np.int16)
        for _ in range(20):
            streaming.feed_chunk(chunk, speech_prob=0.9)

        import time
        time.sleep(0.2)

        full_audio = np.zeros(16000 * 2, dtype=np.int16)
        result = streaming.finalize_utterance(full_audio)

        self.assertEqual(result, "busca warframe en youtube")
        self.assertIn("busca warframe en youtube", final_events)
        streaming.close()


    def test_05_realtime_voice_coordinator_end_to_end(self):
        """Verifica el flujo integral E2E en tiempo real desde habla hasta ejecución de comando."""
        from src.audio.realtime_coordinator import RealtimeVoiceCoordinator
        from src.nlu.intent_parser import ActionStep, StepParameters, ParsedPipeline

        events = []
        def track_event(evt_type, data):
            events.append((evt_type, data))

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "pausa la musica"

        mock_parser = MagicMock()
        mock_parser.parse.return_value = ParsedPipeline(
            raw_text="pausa la musica",
            steps=[ActionStep(intent="MEDIA_CONTROL", target="pause", parameters=StepParameters())],
            confidence=1.0
        )

        mock_executor = MagicMock()
        mock_executor.execute_pipeline.return_value = True
        mock_executor.last_action_message = "Música pausada."

        coordinator = RealtimeVoiceCoordinator(
            whisper_stt=mock_stt,
            intent_parser=mock_parser,
            executor=mock_executor,
            on_event=track_event
        )

        # Simular ciclo de habla
        coordinator._handle_speech_start()
        self.assertTrue(any(e[0] == "speech_started" for e in events))

        fake_audio = np.zeros(16000 * 2, dtype=np.int16)
        coordinator._handle_speech_end(fake_audio)

        # Verificar transcripción final, ejecución y evento de finalización
        self.assertTrue(any(e[0] == "final_transcript" for e in events))
        self.assertTrue(any(e[0] == "executing_command" for e in events))
        self.assertTrue(any(e[0] == "command_finished" for e in events))
        mock_executor.execute_pipeline.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
