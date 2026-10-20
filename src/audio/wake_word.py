import os
import re
import time
import wave
import tempfile
import threading
import queue
from collections import deque
import numpy as np
import sounddevice as sd
from typing import Callable, Optional

from config.settings import settings
from src.audio.audio_coordinator import register_wake_detector, is_tts_playing

WAKE_PATTERN = re.compile(
    r"\b("
    r"oye\s+vanshee|oye\s+vanshe|oye\s+banshee|oye\s+banshe|"
    r"hey\s+vanshee|hey\s+vanshe|ey\s+vanshee|ey\s+vanshe|"
    r"ok\s+vanshee|ok\s+vanshe|"
    r"vanshee|banshee|v-anshee|v_anshee|"
    r"vanshe|banshe|"
    r"vanchi|banchi|vanche|banche|vanji|banji|"
    r"vansi|bansi|vanshi|banshi|vanxi|banxi|vansy|bansy"
    r")\b",
    re.IGNORECASE
)

class WakeWordDetector:
    """
    Detector continuo de palabra de activación ("Banshee" / "Vanshee") en segundo plano.
    Utiliza un flujo continuo de audio sin reinicios, cola de procesamiento en hilo secundario
    y ventana de comando activo para máxima fluidez y cero pérdida de voz.
    """

    def __init__(
        self,
        stt_engine=None,
        on_wake_detected: Optional[Callable[[str, str], None]] = None,
        on_state_change: Optional[Callable[[str], None]] = None,
        sample_rate: int = 16000,
        threshold_rms: float | None = None,
        device_index: int | None = None,
    ):
        self.stt_engine = stt_engine
        self.on_wake_detected = on_wake_detected
        self.on_state_change = on_state_change
        self.sample_rate = sample_rate
        self.threshold_rms = threshold_rms if threshold_rms is not None else getattr(settings, "AUDIO_THRESHOLD_RMS", 45.0)
        self.device_index = device_index if device_index is not None else getattr(settings, "AUDIO_INPUT_DEVICE", None)

        self._running = False
        self._listen_thread: Optional[threading.Thread] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue(maxsize=10)
        self._paused = False
        self._user_paused = False
        self._active_command_until: float = 0.0
        self._last_trigger_time: float = 0.0
        self.last_rms: float = 0.0

        # Registrar en el coordinador de audio
        register_wake_detector(self)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_rms(self) -> float:
        return self.last_rms

    def start(self):
        if self._running:
            return
        self._running = True
        if not self._worker_thread or not self._worker_thread.is_alive():
            self._worker_thread = threading.Thread(target=self._transcription_worker, daemon=True, name="WakeWordWorker")
            self._worker_thread.start()

        if not self._listen_thread or not self._listen_thread.is_alive():
            self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True, name="WakeWordAudioStream")
            self._listen_thread.start()
        print(f"[WakeWord] Detector continuo de 'Vanshee' activo (Dispositivo: {self.device_index}, Umbral: {self.threshold_rms} RMS).")

    def stop(self):
        self._running = False
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=1.5)
        print("[WakeWord] Detector detenido.")

    @property
    def is_listening_active(self) -> bool:
        """Indica si el modo de escucha está activo (no pausado por el usuario)."""
        return not self._user_paused

    @property
    def is_paused(self) -> bool:
        return self._user_paused or self._paused

    @property
    def is_user_paused(self) -> bool:
        return self._user_paused

    def pause(self, user_initiated: bool = True):
        if user_initiated:
            self._user_paused = True
        self._paused = True
        if user_initiated:
            self._active_command_until = 0.0
        print(f"[WakeWord] Detector pausado (usuario={user_initiated}).")

    def resume(self, user_initiated: bool = True):
        if user_initiated:
            self._user_paused = False
        if self._user_paused and not user_initiated:
            return
        self._paused = False
        print(f"[WakeWord] Detector reanudado (usuario={user_initiated}).")

    def trigger_manual_listen(self, duration: float = 8.0):
        """Activa una ventana de escucha activa directa."""
        self._user_paused = False
        self._paused = False
        self._active_command_until = time.time() + duration
        print(f"[WakeWord] Modo de escucha activa forzado por {duration} segundos.")

    def update_settings(self, threshold_rms: float | None = None, device_index: int | None = None):
        if threshold_rms is not None:
            self.threshold_rms = threshold_rms
            print(f"[WakeWord] Umbral RMS actualizado a: {self.threshold_rms}")
        if device_index is not None and device_index != self.device_index:
            self.device_index = device_index
            print(f"[WakeWord] Dispositivo de entrada cambiado a: {self.device_index}. Reiniciando stream...")
            # Forzar reinicio del stream con el nuevo dispositivo
            self._restart_stream()

    def _restart_stream(self):
        self._running = False
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=1.5)
        self._running = True
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True, name="WakeWordAudioStream")
        self._listen_thread.start()
        print(f"[WakeWord] Stream reiniciado en Dispositivo {self.device_index} (Umbral: {self.threshold_rms} RMS).")

    def _extract_command_after_wake(self, text: str) -> tuple[bool, str]:
        """
        Verifica si contiene la palabra clave, si es un comando directo o si estamos en ventana de comando activo.
        Distingue con precisión la conversación ambiental del habla dirigida a Vanshee.
        """
        clean = re.sub(r"[^\w\s]", " ", text.lower()).strip()
        clean = re.sub(r"\s+", " ", clean)

        # 0. Filtrar alucinaciones o frases fantasma
        if any(h in clean for h in [
            "asistente de voz", "comando de voz", "asistente para windows",
            "asistente de windows", "comando de windows"
        ]):
            return False, ""

        # 1. Verificar palabra de activación explícita
        match_raw = WAKE_PATTERN.search(text)
        if match_raw:
            trailing = text[match_raw.end():].strip().lstrip(",:;- ")
            while True:
                m_sub = WAKE_PATTERN.match(trailing)
                if m_sub:
                    trailing = trailing[m_sub.end():].strip().lstrip(",:;- ")
                else:
                    break
            trailing = re.sub(
                r"^(?:por\s+favor|puedes|podr[ií]as|quiero\s+que|realiza\s+o|hazme\s+el\s+favor\s+de|dime|haz\s+el\s+favor\s+de|ejecuta)\s+",
                "",
                trailing,
                flags=re.IGNORECASE
            ).strip().lstrip(",:;- ")
            return True, trailing

        match = WAKE_PATTERN.search(clean)
        if match:
            trailing = clean[match.end():].strip().lstrip(",:;- ")
            # Eliminar palabras de activación redundantes adicionales al inicio (ej: "banshee banshee...")
            while True:
                m_sub = WAKE_PATTERN.match(trailing)
                if m_sub:
                    trailing = trailing[m_sub.end():].strip().lstrip(",:;- ")
                else:
                    break
            # Limpiar fórmulas de petición o conectores ("por favor", "realiza o", "puedes", etc.)
            trailing = re.sub(
                r"^(?:por\s+favor|puedes|podr[ií]as|quiero\s+que|realiza\s+o|hazme\s+el\s+favor\s+de|dime|haz\s+el\s+favor\s+de|ejecuta)\s+",
                "",
                trailing,
                flags=re.IGNORECASE
            ).strip().lstrip(",:;- ")
            return True, trailing

        # 2. Si estamos dentro de la ventana de escucha activa tras decir "¿Dime?"
        if (time.time() < self._active_command_until) and len(clean) >= 2:
            clean_cmd = re.sub(
                r"^(?:por\s+favor|puedes|podr[ií]as|quiero\s+que|realiza\s+o|hazme\s+el\s+favor\s+de|dime|haz\s+el\s+favor\s+de|ejecuta)\s+",
                "",
                clean,
                flags=re.IGNORECASE
            ).strip().lstrip(",:;- ")
            return True, clean_cmd

        # Si el usuario solo está hablando normalmente (en llamada, con amigos, etc.), se ignora por completo
        return False, ""

    def _transcription_worker(self):
        """Hilo dedicado a procesar los audios sin congelar el flujo del micrófono."""
        while self._running:
            try:
                audio_data = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if not self.stt_engine:
                continue

            try:
                # Inferencia directa en memoria RAM (np.ndarray) sin latencia de disco
                text = self.stt_engine.transcribe(audio_data)
                now = time.time()
                can_trigger = (time.time() < self._active_command_until) or ((now - self._last_trigger_time) > 1.0)
                if text and can_trigger:
                    is_wake, command = self._extract_command_after_wake(text)
                    if is_wake:
                        self._last_trigger_time = now
                        print(f"\n[Vanshee Detectado]: '{text}' (Comando: '{command}')")

                        # Pausar temporalmente para que no capte la respuesta TTS
                        self._paused = True
                        try:
                            if not command:
                                self._active_command_until = now + 10.0
                                self._last_trigger_time = 0.0
                            else:
                                self._active_command_until = 0.0

                            if self.on_wake_detected:
                                self.on_wake_detected(text, command)
                        finally:
                            time.sleep(0.1)
                            if not is_tts_playing():
                                self._paused = False
            except Exception as e:
                print(f"[WakeWord Worker Error]: {e}")

    def _listen_loop(self):
        """Mantiene un InputStream persistente y fluido en sounddevice."""
        chunk_duration = 0.1  # 100 ms por bloque
        chunk_size = int(self.sample_rate * chunk_duration)

        speech_chunks = []
        preroll_chunks = deque(maxlen=5)  # 500ms de pre-buffer
        has_speech = False
        silence_frames = 0
        max_silence_frames = 8   # ~800ms de silencio para permitir pausas naturales al hablar
        max_total_chunks = 80    # ~8.0 segundos de comando continuo

        def stream_callback(indata, frames, time_info, status):
            nonlocal has_speech, silence_frames, speech_chunks

            # Si Banshee está hablando o está pausado, ignorar el audio entrante
            if is_tts_playing() or self._paused:
                self.last_rms = 0.0
                speech_chunks.clear()
                preroll_chunks.clear()
                has_speech = False
                silence_frames = 0
                return

            chunk = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            self.last_rms = rms
            current_trigger = max(35.0, self.threshold_rms)

            if not has_speech:
                preroll_chunks.append(chunk)
                # Detección de inicio de voz
                if rms >= current_trigger:
                    has_speech = True
                    speech_chunks.extend(preroll_chunks)
                    speech_chunks.append(chunk)
                    silence_frames = 0
            else:
                speech_chunks.append(chunk)
                # Detección de silencio con histéresis (65% del umbral de activación)
                if rms < (current_trigger * 0.65):
                    silence_frames += 1
                else:
                    silence_frames = 0

                # Cierre de frase
                if silence_frames >= max_silence_frames or len(speech_chunks) >= max_total_chunks:
                    if len(speech_chunks) >= 4:  # Mínimo 400ms
                        full_audio = np.concatenate(speech_chunks, axis=0).flatten()
                        try:
                            self._audio_queue.put_nowait(full_audio)
                        except queue.Full:
                            pass
                    speech_chunks.clear()
                    has_speech = False
                    silence_frames = 0

        while self._running:
            try:
                with sd.InputStream(
                    device=self.device_index,
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=chunk_size,
                    callback=stream_callback
                ):
                    # El stream se mantiene abierto continuamente sin destruirse
                    while self._running:
                        time.sleep(0.1)
            except Exception as e:
                if self._running:
                    print(f"[WakeWord Stream Error]: {e}. Reintentando en 1s...")
                    time.sleep(1.0)
