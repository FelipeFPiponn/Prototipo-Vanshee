"""Módulo de Visión Multimodal (Gemini Vision API) para Depuración de Pantalla en V.ANSHEE.

Permite capturar en memoria la pantalla completa o la ventana activa (IDE, terminal, navegador)
y enviarla a Gemini Vision para analizar errores, trazas de consola, problemas de CSS/UI o código.
"""

import io
import os
import json
import base64
import urllib.request
import urllib.error
from typing import Tuple, Optional

try:
    from PIL import ImageGrab, Image
except ImportError:
    ImageGrab = None
    Image = None

try:
    import win32gui
except ImportError:
    win32gui = None

from config.settings import settings


class ScreenVisionAnalyzer:
    """Captura la pantalla o ventana activa y la analiza con Gemini Vision API."""

    def __init__(self):
        self.system_instruction = (
            "Eres V.ANSHEE, una asistente experta en ingeniería de software y depuración visual integrada en Windows. "
            "Analiza la captura de pantalla del desarrollador (terminal, editor de código, navegador o interfaz) "
            "y responde su consulta en español de forma directa, clara, hablada y accionable (máximo 2 a 4 oraciones concisas). "
            "Si ves un error o excepción en consola o código, identifica exactamente la causa y di cómo solucionarlo."
        )

    def _get_gemini_key(self) -> str:
        key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        return key.strip()

    def _get_active_window_info(self) -> Tuple[str, Optional[Tuple[int, int, int, int]]]:
        """Obtiene el título y el rectángulo (left, top, right, bottom) de la ventana activa."""
        if not win32gui:
            return "Pantalla completa", None
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return "Pantalla completa", None
            title = win32gui.GetWindowText(hwnd).strip()
            cls_name = win32gui.GetClassName(hwnd).strip().lower()
            if cls_name in ("progman", "workerw", "shell_traywnd") or "vanshee" in title.lower():
                return "Escritorio", None
            l, t, r, b = win32gui.GetWindowRect(hwnd)
            if (r - l) > 200 and (b - t) > 150:
                return title or "Ventana activa", (max(0, l), max(0, t), r, b)
            return title or "Pantalla completa", None
        except Exception:
            return "Pantalla completa", None

    def capture_screen_jpeg_b64(self, active_window_only: bool = False) -> Tuple[Optional[str], str]:
        """Captura la pantalla o ventana activa y retorna (base64_jpeg, window_title)."""
        if ImageGrab is None:
            return None, "PIL.ImageGrab no está disponible."

        win_title, bbox = self._get_active_window_info()
        try:
            if active_window_only and bbox:
                img = ImageGrab.grab(bbox=bbox)
            else:
                img = ImageGrab.grab()

            # Redimensionar si supera 1440px de ancho para baja latencia
            max_w = 1440
            if img.width > max_w:
                ratio = max_w / float(img.width)
                new_h = int(img.height * ratio)
                img = img.resize((max_w, new_h), Image.Resampling.LANCZOS)

            if img.mode != "RGB":
                img = img.convert("RGB")

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=82, optimize=True)
            b64_data = base64.b64encode(buf.getvalue()).decode("ascii")
            return b64_data, win_title
        except Exception as e:
            return None, f"Error al capturar pantalla: {e}"

    def analyze_screen(self, user_query: str = "", active_window_only: bool = False) -> Tuple[bool, str]:
        """Captura la pantalla actual y la envía a Gemini Vision junto con la pregunta del usuario."""
        api_key = self._get_gemini_key()
        if not api_key:
            return False, "Necesitas configurar tu Gemini API Key en los Ajustes de Vanshee para usar el análisis visual de pantalla."

        b64_img, win_title = self.capture_screen_jpeg_b64(active_window_only=active_window_only)
        if not b64_img:
            return False, f"No pude capturar la pantalla en este momento ({win_title})."

        prompt = user_query.strip() if user_query and user_query.strip() else (
            "Analiza lo que aparece en mi pantalla. Si hay algún error de código, terminal o problema visual, dime cuál es y cómo solucionarlo."
        )
        full_prompt = f"Ventana activa detectada: '{win_title}'.\nConsulta del desarrollador: {prompt}"

        primary_model = getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite") or "gemini-3.1-flash-lite"
        candidate_models = [primary_model]
        for fallback_m in ("gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-3-flash-preview"):
            if fallback_m not in candidate_models:
                candidate_models.append(fallback_m)

        payload = {
            "systemInstruction": {
                "parts": [{"text": self.system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": full_prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": b64_img
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.25,
                "maxOutputTokens": 350
            }
        }
        encoded_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        last_err = None
        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=encoded_payload,
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=14) as resp:
                    raw_body = json.loads(resp.read().decode("utf-8"))
                    candidates = raw_body.get("candidates") or []
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts") or []
                    for part in parts:
                        txt = part.get("text", "").strip()
                        if txt:
                            return True, txt
            except Exception as e:
                last_err = e
                continue

        return False, f"No se pudo completar el análisis visual con Gemini Vision: {last_err}"


screen_vision = ScreenVisionAnalyzer()
