import os
import sys
import site
import wave
from pathlib import Path
import numpy as np

def _setup_cuda_dlls():
    """Registra las DLLs de NVIDIA (cuBLAS, cuDNN, etc.) instaladas en el entorno virtual."""
    try:
        for sp in site.getsitepackages():
            n_dir = os.path.join(sp, "nvidia")
            if os.path.isdir(n_dir):
                for sub in os.listdir(n_dir):
                    b_dir = os.path.join(n_dir, sub, "bin")
                    if os.path.isdir(b_dir):
                        try:
                            os.add_dll_directory(b_dir)
                        except Exception:
                            pass
                        if b_dir not in os.environ.get("PATH", ""):
                            os.environ["PATH"] = b_dir + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

_setup_cuda_dlls()

from faster_whisper import WhisperModel
from config.settings import settings

class WhisperSTT:
    def __init__(self, model_size: str | None = None, device: str | None = None):
        _setup_cuda_dlls()
        size = model_size or getattr(settings, "STT_MODEL_SIZE", "medium")
        
        # Detección automática de GPU NVIDIA (CUDA)
        if device is None:
            try:
                import ctranslate2
                if ctranslate2.get_cuda_device_count() > 0:
                    device = "cuda"
                    compute_type = "float16"
                else:
                    device = "cpu"
                    compute_type = "int8"
            except Exception:
                device = "cpu"
                compute_type = "int8"
        else:
            compute_type = "float16" if device == "cuda" else "int8"

        # Intento de carga con fallback automático a CPU si falta alguna librería
        try:
            print(f"[STT] Cargando modelo Faster-Whisper '{size}' en {device.upper()} ({compute_type})...")
            self.model = WhisperModel(size, device=device, compute_type=compute_type)
            self.current_model = size
            self.current_device = device
        except Exception as e:
            print(f"[STT Warning] Fallo al iniciar en {device.upper()}: {e}. Cambiando a CPU (int8)...")
            device = "cpu"
            compute_type = "int8"
            self.model = WhisperModel(size, device=device, compute_type=compute_type)
            self.current_model = size
            self.current_device = device

    def transcribe(self, audio_input: str | Path | np.ndarray) -> str:
        """Transcribe audio desde una ruta de archivo .wav o directamente desde un array numpy en memoria RAM."""
        # 1. Normalización de entrada y verificación de duración
        audio_data = None
        prompt = "Banshee, asistente de voz para Windows. Comandos: abrir, cerrar, buscar, ejecutar, YouTube, Brave, Chrome, VS Code."

        if isinstance(audio_input, np.ndarray):
            if audio_input.dtype == np.int16:
                audio_data = audio_input.astype(np.float32) / 32768.0
            else:
                audio_data = audio_input.astype(np.float32)

            duration = len(audio_data) / 16000.0
            if duration < 0.25:
                return ""
            if float(np.max(np.abs(audio_data))) < 0.002:
                return ""
            transcribe_target = audio_data
        else:
            audio_path = str(audio_input)
            try:
                with wave.open(audio_path, "rb") as wf:
                    n_frames = wf.getnframes()
                    sample_rate = wf.getframerate()
                    duration = n_frames / float(sample_rate) if sample_rate > 0 else 0

                    if duration < 0.25:
                        return ""

                    frames = wf.readframes(n_frames)
                    audio_raw = np.frombuffer(frames, dtype=np.int16)
                    if float(np.max(np.abs(audio_raw))) < 50.0:
                        return ""
            except Exception as e:
                print(f"[STT Pre-check Error]: {e}")
                return ""
            transcribe_target = audio_path

        # 2. Inferencia con Faster-Whisper
        try:
            segments, _ = self.model.transcribe(
                transcribe_target,
                language="es",
                initial_prompt=prompt,
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.35,
                    min_silence_duration_ms=300,
                    speech_pad_ms=200
                )
            )
            text = " ".join([segment.text for segment in segments]).strip()
        except Exception as e:
            # Fallback automático a CPU
            if self.current_device == "cuda":
                print(f"[STT Warning] Inferencia en CUDA falló: {e}. Conmutando permanentemente a CPU (int8)...")
                try:
                    self.model = WhisperModel(self.current_model, device="cpu", compute_type="int8")
                    self.current_device = "cpu"
                    segments, _ = self.model.transcribe(
                        transcribe_target,
                        language="es",
                        initial_prompt=prompt,
                        vad_filter=True,
                        vad_parameters=dict(threshold=0.35, min_silence_duration_ms=300, speech_pad_ms=200)
                    )
                    return " ".join([segment.text for segment in segments]).strip()
                except Exception as ex2:
                    print(f"[STT CPU Fallback Error]: {ex2}")
                    return ""
            print(f"[STT Transcribe Error]: {e}")
            return ""

        # 3. Filtrar alucinaciones comunes
        hallucination_phrases = {
            "subtítulos realizados por",
            "comunidad de amara.org",
            "gracias por ver el video",
            "gracias por ver",
            "suscríbete al canal",
            "muchas gracias por su atención",
        }
        lowered = text.lower().strip()
        for phrase in hallucination_phrases:
            if phrase in lowered and len(text) < 45:
                return ""

        return text