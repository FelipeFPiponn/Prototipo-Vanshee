import os
import urllib.request
from pathlib import Path
from typing import Optional
import numpy as np
import onnxruntime as ort

MODEL_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"


class SileroVAD:
    """Motor de detección de actividad vocal (VAD) neuronal basado en Silero VAD (ONNX).
    
    Permite detectar inicio y fin de voz en tiempo real con < 1ms de latencia por bloque de 30ms,
    reduciendo el tiempo de espera por silencio de 1.4s a ~200-300ms.
    """

    def __init__(self, model_path: Optional[str | Path] = None):
        if model_path is None:
            root = Path(__file__).resolve().parent.parent.parent
            model_dir = root / "data" / "models"
            model_dir.mkdir(parents=True, exist_ok=True)
            self.model_path = model_dir / "silero_vad.onnx"
        else:
            self.model_path = Path(model_path)

        self._ensure_model()

        # Opciones de sesión optimizadas para CPU de baja latencia
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            str(self.model_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"]
        )

        self.sample_rate = 16000
        self.sr_tensor = np.array(self.sample_rate, dtype=np.int64)
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.reset()

    def _ensure_model(self):
        """Descarga el modelo ONNX automáticamente si no existe."""
        if not self.model_path.exists() or self.model_path.stat().st_size < 1000:
            print(f"[Silero VAD] Descargando modelo ONNX desde {MODEL_URL}...")
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(MODEL_URL, str(self.model_path))
            print(f"[Silero VAD] Modelo descargado exitosamente ({self.model_path.stat().st_size} bytes).")

    def reset(self):
        """Reinicia el estado recurrente del modelo VAD."""
        self.state = np.zeros((2, 1, 128), dtype=np.float32)

    def is_speech(self, chunk: np.ndarray, threshold: float = 0.5) -> tuple[bool, float]:
        """Evalúa un bloque de audio de 512 muestras (32ms a 16kHz).
        
        Args:
            chunk: Array numpy 1D de muestras (float32 normalizadas [-1, 1] o int16).
            threshold: Umbral de probabilidad [0.0 - 1.0] para clasificar como voz.
            
        Returns:
            tuple[bool, float]: (es_voz, probabilidad)
        """
        # Normalizar a float32 [-1.0, 1.0]
        if chunk.dtype == np.int16:
            audio_f32 = chunk.astype(np.float32) / 32768.0
        else:
            audio_f32 = chunk.astype(np.float32)

        # Ajustar a longitud de 512 muestras requerida por Silero VAD a 16kHz
        if len(audio_f32) < 512:
            padded = np.zeros(512, dtype=np.float32)
            padded[:len(audio_f32)] = audio_f32
            audio_f32 = padded
        elif len(audio_f32) > 512:
            audio_f32 = audio_f32[:512]

        input_tensor = np.expand_dims(audio_f32, axis=0)  # Shape (1, 512)

        try:
            outputs = self.session.run(
                None,
                {
                    "input": input_tensor,
                    "sr": self.sr_tensor,
                    "state": self.state
                }
            )
            prob = float(outputs[0][0][0])
            self.state = outputs[1]
            return (prob >= threshold), prob
        except Exception as e:
            print(f"[Silero VAD Warning] Error en inferencia: {e}")
            return False, 0.0
