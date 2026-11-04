import os
import sys
import json
import asyncio
import hashlib
import tempfile
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from config.settings import settings
from src.audio.audio_coordinator import get_tts_lock, notify_tts_start, notify_tts_end, set_tts_level

# Predefined Natural ElevenLabs Multilingual Voices
ELEVENLABS_VOICES = [
    {
        "id": "elevenlabs:FGY2WhTYpPnrIDTdsKH5",
        "name": "Laura (ElevenLabs - Femenina, Expresiva y Viva)",
        "gender": "Female",
        "locale": "multilingual",
        "type": "elevenlabs"
    },
    {
        "id": "elevenlabs:cgSgspJ2msm6clMCkdW9",
        "name": "Jessica (ElevenLabs - Femenina, Joven y Dinámica)",
        "gender": "Female",
        "locale": "multilingual",
        "type": "elevenlabs"
    },
    {
        "id": "elevenlabs:XrExE9yKIg1WjnnlVkGX",
        "name": "Matilda (ElevenLabs - Femenina, Cálida y Amigable)",
        "gender": "Female",
        "locale": "multilingual",
        "type": "elevenlabs"
    },
    {
        "id": "elevenlabs:EXAVITQu4vr4xnSDxMaL",
        "name": "Sarah (ElevenLabs - Femenina, Suave y Natural)",
        "gender": "Female",
        "locale": "multilingual",
        "type": "elevenlabs"
    },
    {
        "id": "elevenlabs:Xb7hH8MSUJpSbSDYk0k2",
        "name": "Alice (ElevenLabs - Femenina, Confiada y Profesional)",
        "gender": "Female",
        "locale": "multilingual",
        "type": "elevenlabs"
    },
    {
        "id": "elevenlabs:pFZP5JQG7iQjIQuC4Bku",
        "name": "Lily (ElevenLabs - Femenina, Serena)",
        "gender": "Female",
        "locale": "multilingual",
        "type": "elevenlabs"
    },
    {
        "id": "elevenlabs:onwK4e9ZLuTAKqWW03F9",
        "name": "Daniel (ElevenLabs - Masculino, Profundo y Claro)",
        "gender": "Male",
        "locale": "multilingual",
        "type": "elevenlabs"
    },
    {
        "id": "elevenlabs:cjVigY5qzO86Huf0OWal",
        "name": "Eric (ElevenLabs - Masculino, Fluido y Natural)",
        "gender": "Male",
        "locale": "multilingual",
        "type": "elevenlabs"
    },
]

# Predefined Natural Spanish Neural Voices via Edge-TTS
NATURAL_NEURAL_VOICES = [
    {
        "id": "es-ES-ElviraNeural",
        "name": "Elvira (España - Femenina, Natural)",
        "gender": "Female",
        "locale": "es-ES",
        "type": "neural"
    },
    {
        "id": "es-ES-AlvaroNeural",
        "name": "Álvaro (España - Masculino, Formal)",
        "gender": "Male",
        "locale": "es-ES",
        "type": "neural"
    },
    {
        "id": "es-MX-DaliaNeural",
        "name": "Dalia (México - Femenina, Cálida)",
        "gender": "Female",
        "locale": "es-MX",
        "type": "neural"
    },
    {
        "id": "es-MX-JorgeNeural",
        "name": "Jorge (México - Masculino, Fluido)",
        "gender": "Male",
        "locale": "es-MX",
        "type": "neural"
    },
    {
        "id": "es-AR-TomasNeural",
        "name": "Tomás (Argentina - Masculino)",
        "gender": "Male",
        "locale": "es-AR",
        "type": "neural"
    },
    {
        "id": "es-CO-SalomeNeural",
        "name": "Salomé (Colombia - Femenina)",
        "gender": "Female",
        "locale": "es-CO",
        "type": "neural"
    },
    {
        "id": "es-US-PalomaNeural",
        "name": "Paloma (EE.UU. / Latino - Femenina)",
        "gender": "Female",
        "locale": "es-US",
        "type": "neural"
    },
]


class TTSEngine:
    def __init__(self, voice: str | None = None):
        default_voice = "elevenlabs:FGY2WhTYpPnrIDTdsKH5" if self._get_elevenlabs_key() else "es-ES-ElviraNeural"
        self.voice = voice or getattr(settings, "TTS_VOICE", default_voice)
        self.temp_dir = Path(tempfile.gettempdir()) / "vanshee_tts"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _get_elevenlabs_key(self) -> str:
        return (getattr(settings, "ELEVENLABS_API_KEY", "") or os.getenv("ELEVENLABS_API_KEY", "")).strip()

    def _is_elevenlabs_voice(self, voice_id: str) -> bool:
        if voice_id.startswith("elevenlabs:"):
            return True
        if voice_id.startswith("sapi:") or voice_id.startswith("es-") or voice_id.startswith("en-"):
            return False
        return getattr(settings, "TTS_ENGINE", "") == "elevenlabs" and bool(self._get_elevenlabs_key())

    def get_available_voices(self) -> list[dict[str, Any]]:
        """Devuelve las voces de ElevenLabs, las voces neuronales Edge-TTS y las voces SAPI de Windows."""
        voices: list[dict[str, Any]] = []

        if self._get_elevenlabs_key():
            voices.extend(ELEVENLABS_VOICES)

        voices.extend(NATURAL_NEURAL_VOICES)

        # Consultar también voces SAPI locales de Windows
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            sp_voice = win32com.client.Dispatch("SAPI.SpVoice")
            for v in sp_voice.GetVoices():
                desc = v.GetDescription()
                voices.append({
                    "id": f"sapi:{desc}",
                    "name": f"{desc} (Windows Local)",
                    "gender": "Female" if "sabina" in desc.lower() or "zira" in desc.lower() or "helena" in desc.lower() else "Male",
                    "locale": "es" if "spanish" in desc.lower() or "español" in desc.lower() or "sabina" in desc.lower() else "en",
                    "type": "sapi"
                })
            pythoncom.CoUninitialize()
        except Exception as e:
            print(f"[TTSEngine] Error enumerando voces SAPI: {e}")

        return voices

    def set_voice(self, voice_id: str):
        self.voice = voice_id
        from config.settings import save_setting
        save_setting("TTS_VOICE", voice_id)
        if voice_id.startswith("elevenlabs:"):
            save_setting("TTS_ENGINE", "elevenlabs")
        elif voice_id.startswith("sapi:"):
            save_setting("TTS_ENGINE", "sapi")
        else:
            save_setting("TTS_ENGINE", "edge-tts")

    @staticmethod
    def _enhance_prosody_text(text: str) -> str:
        """Limpia símbolos técnicos y mejora la puntuación para que ElevenLabs entone con naturalidad."""
        import re
        t = text.strip()
        # Evitar que lea barras '/' o guiones bajos literalmente
        t = re.sub(r"\s*/\s*", " o ", t)
        t = t.replace("_", " ")
        # Si es una frase corta afirmativa sin signos expresivos, añadir calidez
        if len(t) < 65 and not any(ch in t for ch in ("¡", "!", "¿", "?")):
            t = f"¡{t.rstrip('.')}!"
        return t

    def _generate_elevenlabs_audio(self, text: str, voice_id: str, out_path: str) -> bool:
        api_key = self._get_elevenlabs_key()
        if not api_key:
            return False

        clean_voice_id = voice_id.replace("elevenlabs:", "").strip()
        if not clean_voice_id:
            clean_voice_id = "FGY2WhTYpPnrIDTdsKH5"

        expressive_text = self._enhance_prosody_text(text)
        model_id = getattr(settings, "ELEVENLABS_MODEL", "eleven_multilingual_v2") or "eleven_multilingual_v2"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{clean_voice_id}"
        payload = json.dumps({
            "text": expressive_text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.32,
                "similarity_boost": 0.80,
                "style": 0.45,
                "use_speaker_boost": True
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            audio_bytes = resp.read()
            if audio_bytes and len(audio_bytes) > 200:
                with open(out_path, "wb") as f:
                    f.write(audio_bytes)
                return True
        return False

    def generate_audio_file(self, text: str, voice: str | None = None) -> str:
        """Genera un archivo de audio MP3 usando la voz seleccionada (ElevenLabs o Edge-TTS)."""
        v = voice or self.voice
        expressive_text = self._enhance_prosody_text(text)
        # Hash seguro de texto, voz y perfil expresivo v2 para caché
        txt_hash = hashlib.md5(f"{expressive_text}_{v}_v2".encode("utf-8")).hexdigest()
        out_path = str(self.temp_dir / f"tts_{txt_hash}.mp3")

        # Reutilizar archivo si ya existe y es válido
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            return out_path

        # 1. Si es voz de ElevenLabs y hay API Key configurada
        if self._is_elevenlabs_voice(v) and self._get_elevenlabs_key():
            try:
                if self._generate_elevenlabs_audio(text, v, out_path):
                    return out_path
            except Exception as e:
                print(f"[TTSEngine] Fallo ElevenLabs ({e}), usando fallback Edge-TTS.")

        # 2. Si es voz neuronal de Edge-TTS (o fallback de ElevenLabs)
        if not v.startswith("sapi:"):
            edge_voice = v if v.startswith("es-") or v.startswith("en-") else "es-ES-ElviraNeural"
            try:
                import edge_tts
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                comm = edge_tts.Communicate(text, edge_voice)
                loop.run_until_complete(comm.save(out_path))
                loop.close()
                if os.path.exists(out_path) and os.path.getsize(out_path) > 200:
                    return out_path
            except Exception as e:
                print(f"[TTSEngine] Fallo Edge-TTS ({e}), usando fallback SAPI.")

        # 3. Fallback o si es SAPI
        return ""

    def speak(self, text: str, block: bool = True):
        clean = text.strip()
        if not clean:
            return

        # Impresión segura sin caracteres emoji que rompan cp1252 en Windows
        try:
            print(f"\n[V.ANSHEE Voz]: \"{clean}\"")
        except Exception:
            pass

        def _say():
            lock = get_tts_lock()
            with lock:
                notify_tts_start()
                try:
                    # 1. Intentar audio neuronal (ElevenLabs o Edge-TTS)
                    if not self.voice.startswith("sapi:"):
                        try:
                            audio_path = self.generate_audio_file(clean, self.voice)
                            if audio_path and os.path.exists(audio_path):
                                import time
                                import numpy as np
                                import soundfile as sf
                                import sounddevice as sd
                                data, fs = sf.read(audio_path)
                                sd.play(data, fs)
                                # Emitir envolvente de amplitud real (25 FPS) para reactividad visual del fondo holográfico
                                mono = data.mean(axis=1) if getattr(data, "ndim", 1) > 1 else data
                                total_samples = len(mono)
                                step_sec = 0.04
                                step_samples = max(1, int(fs * step_sec))
                                peak = float(np.max(np.abs(mono))) if total_samples > 0 else 1.0
                                if peak < 1e-4:
                                    peak = 1.0
                                start_play = time.time()
                                while True:
                                    elapsed = time.time() - start_play
                                    idx = int(elapsed * fs)
                                    if idx >= total_samples:
                                        break
                                    chunk = mono[idx:min(total_samples, idx + step_samples)]
                                    if len(chunk) > 0:
                                        rms = float(np.sqrt(np.mean(np.square(chunk))))
                                        norm_lvl = min(1.0, (rms / (peak * 0.42)) ** 0.75)
                                        set_tts_level(norm_lvl)
                                    time.sleep(step_sec)
                                sd.wait()
                                set_tts_level(0.0)
                                return
                        except Exception as e:
                            print(f"[TTSEngine Error Neural]: {e}, recurriendo a SAPI.")

                    # 2. Fallback a Windows SAPI
                    try:
                        import pythoncom
                        import win32com.client
                        pythoncom.CoInitialize()
                        sp_voice = win32com.client.Dispatch("SAPI.SpVoice")
                        
                        target_desc = self.voice.replace("sapi:", "").strip()
                        selected = False
                        for v in sp_voice.GetVoices():
                            desc = v.GetDescription()
                            if target_desc and target_desc in desc:
                                sp_voice.Voice = v
                                selected = True
                                break

                        if not selected:
                            for v in sp_voice.GetVoices():
                                desc = v.GetDescription().lower()
                                if any(w in desc for w in ["spanish", "español", "sabina", "helena", "raul"]):
                                    sp_voice.Voice = v
                                    break

                        sp_voice.Speak(clean)
                    except Exception as e:
                        print(f"[TTSEngine Error SAPI]: {e}")
                    finally:
                        try:
                            pythoncom.CoUninitialize()
                        except Exception:
                            pass
                finally:
                    notify_tts_end()

        if block:
            _say()
        else:
            threading.Thread(target=_say, daemon=True, name="TTSPlaybackThread").start()
