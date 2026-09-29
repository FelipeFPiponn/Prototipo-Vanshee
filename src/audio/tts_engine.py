import os
import sys
import asyncio
import hashlib
import tempfile
import threading
from pathlib import Path
from typing import Any

from config.settings import settings
from src.audio.audio_coordinator import get_tts_lock, notify_tts_start, notify_tts_end

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
        self.voice = voice or getattr(settings, "TTS_VOICE", "es-ES-ElviraNeural")
        self.temp_dir = Path(tempfile.gettempdir()) / "vanshee_tts"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_available_voices(self) -> list[dict[str, Any]]:
        """Devuelve las voces neuronales de alta fidelidad y las voces locales SAPI de Windows."""
        voices = list(NATURAL_NEURAL_VOICES)

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
        settings.TTS_VOICE = voice_id

    def generate_audio_file(self, text: str, voice: str | None = None) -> str:
        """Genera un archivo de audio MP3 usando la voz seleccionada."""
        v = voice or self.voice
        # Hash seguro de texto y voz para caché
        txt_hash = hashlib.md5(f"{text}_{v}".encode("utf-8")).hexdigest()
        out_path = str(self.temp_dir / f"tts_{txt_hash}.mp3")

        # Reutilizar archivo si ya existe y es válido
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            return out_path

        # 1. Si es voz neuronal de Edge-TTS
        if not v.startswith("sapi:"):
            try:
                import edge_tts
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                comm = edge_tts.Communicate(text, v)
                loop.run_until_complete(comm.save(out_path))
                loop.close()
                if os.path.exists(out_path) and os.path.getsize(out_path) > 200:
                    return out_path
            except Exception as e:
                print(f"[TTSEngine] Fallo Edge-TTS ({e}), usando fallback SAPI.")

        # 2. Fallback o si es SAPI
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
                    # 1. Intentar audio neuronal de Edge-TTS
                    if not self.voice.startswith("sapi:"):
                        try:
                            audio_path = self.generate_audio_file(clean, self.voice)
                            if audio_path and os.path.exists(audio_path):
                                import soundfile as sf
                                import sounddevice as sd
                                data, fs = sf.read(audio_path)
                                sd.play(data, fs)
                                sd.wait()
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
