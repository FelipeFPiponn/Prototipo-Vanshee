import os
import sys
import asyncio
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sounddevice as sd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from src.routines.db import init_db
from src.brain import VansheeBrain
from src.executor.app_indexer import AppIndexer
from src.context_awareness import ContextAwarenessEngine
from src.audio.tts_engine import TTSEngine
from src.audio.wake_word import WakeWordDetector
from src.utils.autostart import is_autostart_enabled, set_autostart
from src.nlu.intent_parser import ParsedPipeline, ActionStep, StepParameters

app = FastAPI(title="V.ANSHEE Core Assistant Console", version="2.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global singleton state
class SystemState:
    def __init__(self):
        self.brain: Optional[VansheeBrain] = None
        self.app_indexer: Optional[AppIndexer] = None
        self.context_engine: Optional[ContextAwarenessEngine] = None
        self.tts: Optional[TTSEngine] = None
        self.stt = None
        self.is_stt_loading: bool = False
        self.active_connections: list[WebSocket] = []
        self.speak_tts_enabled: bool = True
        self.wake_detector: Optional[WakeWordDetector] = None

state = SystemState()

def get_brain() -> VansheeBrain:
    if state.brain is None:
        init_db()
        state.tts = TTSEngine(voice=getattr(settings, "TTS_VOICE", "es-ES-ElviraNeural"))
        state.brain = VansheeBrain(
            tts=state.tts,
            interactive_voice=False,
            speak_tts=state.speak_tts_enabled
        )
        state.context_engine = state.brain.context_engine
    return state.brain

def get_app_indexer() -> AppIndexer:
    if state.app_indexer is None:
        state.app_indexer = AppIndexer()
    return state.app_indexer

def get_stt():
    if state.stt is None and not state.is_stt_loading:
        state.is_stt_loading = True
        try:
            from src.audio.stt_whisper import WhisperSTT
            state.stt = WhisperSTT(model_size=settings.STT_MODEL_SIZE)
        except Exception as e:
            print(f"[Server Warning] No se pudo inicializar Whisper: {e}")
        finally:
            state.is_stt_loading = False
    return state.stt

def get_tts() -> TTSEngine:
    if state.tts is None:
        state.tts = TTSEngine(voice=getattr(settings, "TTS_VOICE", "es-ES-ElviraNeural"))
    return state.tts

# Broadcast event to connected WebSockets
async def broadcast_ws(event_type: str, data: Any):
    dead = []
    message = {"type": event_type, "data": data, "timestamp": time.time()}
    for ws in state.active_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in state.active_connections:
            state.active_connections.remove(ws)

# Global command deduplication & debouncing
import re

class CommandDebouncer:
    def __init__(self, window_seconds: float = 2.5):
        self.window_seconds = window_seconds
        self.last_command = ""
        self.last_time = 0.0
        self.last_result = None

    def is_duplicate(self, command: str) -> bool:
        now = time.time()
        norm = re.sub(r"[^\w\s]", "", command.lower()).strip()
        if not norm:
            return False
        if norm == self.last_command and (now - self.last_time) < self.window_seconds:
            return True
        self.last_command = norm
        self.last_time = now
        return False

debouncer = CommandDebouncer(window_seconds=2.5)

# Callback when Wake Word "Banshee" is heard in background
def on_wake_word_detected(full_phrase: str, trailing_command: str):
    print(f"\n[Banshee Wake Trigger] Frase: '{full_phrase}' | Comando detectado: '{trailing_command}'")
    
    # Broadcast wake word event to all UI clients
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    clean_cmd = trailing_command.strip()
    if clean_cmd:
        if debouncer.is_duplicate(clean_cmd):
            print(f"[Server Debounce] Comando duplicado ignorado desde WakeWord: '{clean_cmd}'")
            loop.close()
            return

        # User said "Banshee abre chrome" in one sentence
        loop.run_until_complete(broadcast_ws("wake_word_command", {
            "phrase": full_phrase,
            "command": clean_cmd
        }))
        # Execute directly
        brain = get_brain()
        res = brain.handle_user_input(clean_cmd)
        res_payload = {
            "source": "wake_word",
            "success": res.success,
            "response_text": res.response_text,
            "plan_summary": res.plan_summary,
            "context": {
                "app_name": res.context.app_name,
                "window_title": res.context.window_title,
                "suggestion": res.context.suggestion
            }
        }
        debouncer.last_result = res_payload
        loop.run_until_complete(broadcast_ws("command_completed", res_payload))
    else:
        # User said "Banshee" only -> acknowledge
        tts = get_tts()
        tts.speak("¿Dime?", block=False)
        loop.run_until_complete(broadcast_ws("wake_word_listening", {
            "phrase": full_phrase
        }))
    
    loop.close()

def init_wake_word():
    if state.wake_detector is None and getattr(settings, "WAKE_WORD_ENABLED", True):
        stt = get_stt()
        if stt:
            state.wake_detector = WakeWordDetector(
                stt_engine=stt,
                on_wake_detected=on_wake_word_detected,
                threshold_rms=getattr(settings, "AUDIO_THRESHOLD_RMS", 180.0),
                device_index=getattr(settings, "AUDIO_INPUT_DEVICE", None)
            )
            state.wake_detector.start()
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(broadcast_ws("stt_ready", {
                    "status": "ready",
                    "model": settings.STT_MODEL_SIZE
                }))
                loop.close()
            except Exception:
                pass

# Models
class CommandRequest(BaseModel):
    command: str
    speak_tts: bool = True

class DeviceSelectRequest(BaseModel):
    device_index: Optional[int]
    device_name: Optional[str] = ""

class VoiceSelectRequest(BaseModel):
    voice_id: str

class AutostartRequest(BaseModel):
    enabled: bool

class WakeWordToggleRequest(BaseModel):
    enabled: bool

class SettingsUpdateRequest(BaseModel):
    speak_tts: bool
    threshold_rms: float
    device_index: Optional[int] = None
    voice_id: Optional[str] = None
    wakeword_enabled: Optional[bool] = None

# API Routes
@app.get("/api/status")
async def get_status():
    init_db()
    brain = get_brain()
    context = brain.context_engine.observe(action_hint="status")
    indexer = get_app_indexer()

    # DB Stats
    with sqlite3.connect(settings.DB_PATH) as conn:
        fact_count = conn.execute("SELECT COUNT(*) FROM brain_facts").fetchone()[0]
        interaction_count = conn.execute("SELECT COUNT(*) FROM brain_interactions").fetchone()[0]
        learned_count = conn.execute("SELECT COUNT(*) FROM learned_commands").fetchone()[0]

    # Current audio device name
    cur_dev_name = getattr(settings, "AUDIO_DEVICE_NAME", "")
    cur_dev_idx = getattr(settings, "AUDIO_INPUT_DEVICE", None)
    if not cur_dev_name and cur_dev_idx is not None:
        try:
            d = sd.query_devices(cur_dev_idx)
            cur_dev_name = d.get("name", f"Dispositivo {cur_dev_idx}")
        except Exception:
            pass

    return {
        "status": "online",
        "project_name": settings.PROJECT_NAME,
        "llm_model": settings.OLLAMA_MODEL,
        "stt_model": settings.STT_MODEL_SIZE,
        "stt_ready": state.stt is not None,
        "stt_loading": state.is_stt_loading,
        "speak_tts_enabled": state.speak_tts_enabled,
        "threshold_rms": getattr(settings, "AUDIO_THRESHOLD_RMS", 100.0),
        "selected_device_index": cur_dev_idx,
        "selected_device_name": cur_dev_name or "Predeterminado de Windows",
        "selected_voice": getattr(settings, "TTS_VOICE", "es-ES-ElviraNeural"),
        "wakeword_enabled": getattr(settings, "WAKE_WORD_ENABLED", True),
        "autostart_enabled": is_autostart_enabled(),
        "indexed_apps_count": len(indexer.app_index),
        "database": {
            "facts": fact_count,
            "interactions": interaction_count,
            "learned_commands": learned_count,
        },
        "active_context": {
            "app_name": context.app_name,
            "window_title": context.window_title,
            "suggestion": context.suggestion,
        }
    }

@app.get("/api/context")
async def get_context():
    brain = get_brain()
    context = brain.context_engine.observe(action_hint="ui_poll")
    return {
        "app_name": context.app_name,
        "window_title": context.window_title,
        "screen_size": context.screen_size,
        "confidence": context.confidence,
        "suggestion": context.suggestion,
    }

# Audio Devices Management
@app.get("/api/audio/devices")
async def list_audio_devices():
    """Enumera todos los micrófonos y entradas de audio disponibles en Windows."""
    devices = []
    default_input_idx = None
    try:
        def_devs = sd.default.device
        default_input_idx = def_devs[0] if def_devs else None
    except Exception:
        pass

    current_selected = getattr(settings, "AUDIO_INPUT_DEVICE", None)

    try:
        all_devs = sd.query_devices()
        for idx, d in enumerate(all_devs):
            if d.get("max_input_channels", 0) > 0:
                name = d.get("name", f"Micrófono {idx}")
                is_default = (idx == default_input_idx)
                is_selected = (idx == current_selected) or (current_selected is None and is_default)
                devices.append({
                    "index": idx,
                    "name": name,
                    "channels": d.get("max_input_channels", 1),
                    "default_samplerate": int(d.get("default_samplerate", 16000)),
                    "is_default": is_default,
                    "is_selected": is_selected
                })
    except Exception as e:
        print(f"[Audio Error] enumerando dispositivos: {e}")

    return {
        "devices": devices,
        "selected_index": current_selected,
        "default_index": default_input_idx
    }

@app.post("/api/audio/devices/select")
async def select_audio_device(req: DeviceSelectRequest):
    settings.AUDIO_INPUT_DEVICE = req.device_index
    settings.AUDIO_DEVICE_NAME = req.device_name or ""
    
    # Actualizar detector de wake word si está activo
    if state.wake_detector:
        state.wake_detector.update_settings(device_index=req.device_index)

    return {
        "status": "updated",
        "device_index": req.device_index,
        "device_name": settings.AUDIO_DEVICE_NAME
    }

# Voices Management
@app.get("/api/audio/voices")
async def list_voices():
    tts = get_tts()
    voices = tts.get_available_voices()
    cur_voice = getattr(settings, "TTS_VOICE", "es-ES-ElviraNeural")
    return {
        "current_voice": cur_voice,
        "voices": voices
    }

@app.post("/api/audio/voices/select")
async def select_voice(req: VoiceSelectRequest):
    tts = get_tts()
    tts.set_voice(req.voice_id)
    return {
        "status": "updated",
        "voice_id": req.voice_id
    }

@app.post("/api/audio/tts")
async def speak_tts_test(text: str = Form(...), voice_id: Optional[str] = Form(None)):
    tts = get_tts()
    chosen_voice = voice_id or getattr(settings, "TTS_VOICE", "es-ES-ElviraNeural")
    
    def _speak():
        original = tts.voice
        tts.voice = chosen_voice
        tts.speak(text, block=True)
        tts.voice = original

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _speak)
    return {"status": "ok", "spoken": text, "voice": chosen_voice}

# Autostart Management
@app.get("/api/settings/autostart")
async def check_autostart():
    enabled = is_autostart_enabled()
    return {"enabled": enabled}

@app.post("/api/settings/autostart")
async def toggle_autostart(req: AutostartRequest):
    success = set_autostart(req.enabled)
    settings.AUTOSTART_ENABLED = req.enabled if success else is_autostart_enabled()
    return {"status": "ok" if success else "error", "enabled": settings.AUTOSTART_ENABLED}

# Wake Word Management
@app.post("/api/settings/wakeword")
async def toggle_wakeword(req: WakeWordToggleRequest):
    settings.WAKE_WORD_ENABLED = req.enabled
    if req.enabled:
        init_wake_word()
        if state.wake_detector:
            state.wake_detector.resume()
    else:
        if state.wake_detector:
            state.wake_detector.pause()
    return {"status": "ok", "enabled": settings.WAKE_WORD_ENABLED}

# Command Execution
@app.post("/api/command")
async def execute_command(req: CommandRequest):
    brain = get_brain()
    brain.speak_tts = req.speak_tts and state.speak_tts_enabled

    clean = req.command.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="El comando no puede estar vacío.")

    # Protección contra ejecuciones duplicadas simultáneas
    if debouncer.is_duplicate(clean):
        print(f"[Server Debounce] Comando duplicado ignorado en <2.5s: '{clean}'")
        if debouncer.last_result:
            return debouncer.last_result
        return {
            "source": "web_api",
            "success": True,
            "response_text": "Comando en proceso.",
            "plan_summary": "omitido_duplicado",
            "context": {"app_name": "", "window_title": "", "suggestion": ""}
        }

    await broadcast_ws("command_started", {"command": clean})

    def _execute():
        return brain.handle_user_input(clean)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _execute)

    res_payload = {
        "source": "web_api",
        "success": result.success,
        "response_text": result.response_text,
        "plan_summary": result.plan_summary,
        "context": {
            "app_name": result.context.app_name,
            "window_title": result.context.window_title,
            "suggestion": result.context.suggestion,
        }
    }

    debouncer.last_result = res_payload
    await broadcast_ws("command_completed", res_payload)
    return res_payload

@app.post("/api/audio/wake_trigger")
async def manual_wake_trigger():
    """Activa la ventana de escucha activa de Banshee para hablarle de inmediato."""
    if state.wake_detector:
        state.wake_detector.trigger_manual_listen()
    tts = get_tts()
    tts.speak("¿Dime?", block=False)
    await broadcast_ws("wake_word_listening", {"phrase": "manual_click"})
    return {"status": "ok", "mode": "active_listening"}

@app.post("/api/voice/command")
async def voice_command(audio: UploadFile = File(...), speak_tts: bool = Form(True)):
    stt = get_stt()
    if not stt:
        raise HTTPException(status_code=503, detail="Motor STT no inicializado.")

    suffix = Path(audio.filename or "voice.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, lambda: stt.transcribe(tmp_path))
        if not text.strip():
            return {
                "transcription": "",
                "success": False,
                "response_text": "No se detectó voz clara en la grabación.",
                "plan_summary": "sin_audio"
            }

        brain = get_brain()
        brain.speak_tts = speak_tts and state.speak_tts_enabled
        result = await loop.run_in_executor(None, lambda: brain.handle_user_input(text))

        return {
            "transcription": text,
            "success": result.success,
            "response_text": result.response_text,
            "plan_summary": result.plan_summary,
            "context": {
                "app_name": result.context.app_name,
                "window_title": result.context.window_title,
                "suggestion": result.context.suggestion,
            }
        }
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

@app.post("/api/audio/test_mic")
async def test_mic(duration: float = Form(3.0), device_index: Optional[int] = Form(None)):
    """Graba la voz del usuario durante 3 segundos, guarda el WAV para reproducción y analiza calidad y volumen."""
    import numpy as np
    import wave

    target_dev = device_index if device_index is not None else getattr(settings, "AUDIO_INPUT_DEVICE", None)

    # Pausar el detector de fondo mientras se hace la prueba
    if state.wake_detector:
        state.wake_detector.pause()

    def _sample():
        sr = 16000
        samples = sd.rec(int(sr * duration), samplerate=sr, channels=1, dtype="int16", device=target_dev)
        sd.wait()
        rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        peak = float(np.max(np.abs(samples)))

        # Guardar audio en archivo estático para que el usuario pueda escucharlo inmediatamente
        audio_dir = Path(__file__).resolve().parent / "web" / "static" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        wav_path = audio_dir / "mic_test_sample.wav"

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(samples.tobytes())

        return rms, peak

    loop = asyncio.get_running_loop()
    try:
        rms, peak = await loop.run_in_executor(None, _sample)
    except Exception as e:
        if state.wake_detector:
            state.wake_detector.resume()
        return {
            "rms": 0,
            "peak": 0,
            "level_percent": 0,
            "status": f"Error en dispositivo: {e}",
            "advice": "No se pudo acceder al micrófono seleccionado.",
            "recommended_threshold": 100.0,
            "audio_url": ""
        }
    finally:
        if state.wake_detector:
            state.wake_detector.resume()

    percent = min(100.0, max(0.0, (rms / 350.0) * 100.0))

    if rms < 45.0:
        quality_status = "Volumen muy bajo / Casi inaudible"
        advice = "El micrófono capta poco sonido. Te recomendamos acercarte más o subir el volumen del micrófono en la Configuración de Sonido de Windows (80-100%)."
        rec_thresh = 45.0
    elif rms < 85.0:
        quality_status = "Volumen moderado"
        advice = "La voz se escucha bien para comandos cercanos. Un umbral sensible de 60 - 75 RMS es adecuado."
        rec_thresh = max(45.0, round(rms * 0.75, 0))
    elif rms <= 260.0:
        quality_status = "Excelente claridad y volumen"
        advice = "La potencia y nitidez de tu voz son ideales. Banshee te entenderá de forma óptima."
        rec_thresh = max(60.0, round(rms * 0.7, 0))
    else:
        quality_status = "Volumen muy alto / Posible saturación"
        advice = "El micrófono está captando niveles muy intensos. Te recomendamos alejarte unos centímetros para evitar saturación."
        rec_thresh = 140.0

    return {
        "rms": round(rms, 1),
        "peak": round(peak, 1),
        "level_percent": round(percent, 1),
        "status": quality_status,
        "advice": advice,
        "recommended_threshold": rec_thresh,
        "audio_url": f"/static/audio/mic_test_sample.wav?t={int(time.time()*1000)}"
    }

@app.post("/api/settings/update")
async def update_settings(req: SettingsUpdateRequest):
    state.speak_tts_enabled = req.speak_tts
    settings.AUDIO_THRESHOLD_RMS = req.threshold_rms
    
    if req.device_index is not None:
        settings.AUDIO_INPUT_DEVICE = req.device_index
    if req.voice_id:
        get_tts().set_voice(req.voice_id)
    if req.wakeword_enabled is not None:
        settings.WAKE_WORD_ENABLED = req.wakeword_enabled

    if state.wake_detector:
        state.wake_detector.update_settings(
            threshold_rms=req.threshold_rms,
            device_index=req.device_index
        )

    return {
        "status": "updated",
        "speak_tts": state.speak_tts_enabled,
        "threshold_rms": settings.AUDIO_THRESHOLD_RMS,
        "device_index": settings.AUDIO_INPUT_DEVICE,
        "voice_id": getattr(settings, "TTS_VOICE", "es-ES-ElviraNeural"),
        "wakeword_enabled": getattr(settings, "WAKE_WORD_ENABLED", True)
    }

# Apps Catalog
@app.get("/api/apps")
async def list_apps(query: str = ""):
    indexer = get_app_indexer()
    q = query.lower().strip()
    apps = []

    for name, path in indexer.app_index.items():
        if q and q not in name and q not in path.lower():
            continue

        category = "utility"
        name_lower = name.lower()
        if any(w in name_lower for w in ["code", "visual studio", "pycharm", "git", "terminal", "sublime", "notepad++"]):
            category = "developer"
        elif any(w in name_lower for w in ["chrome", "edge", "firefox", "brave", "opera"]):
            category = "browser"
        elif any(w in name_lower for w in ["spotify", "vlc", "media", "music", "audio", "video"]):
            category = "media"
        elif any(w in name_lower for w in ["steam", "epic", "game", "discord", "xbox"]):
            category = "gaming"
        elif any(w in name_lower for w in ["panel", "configuraci", "settings", "powershell", "cmd", "regedit", "task"]):
            category = "system"

        apps.append({
            "name": name.title(),
            "target": name,
            "path": path,
            "category": category
        })

    apps.sort(key=lambda x: x["name"])
    return {"total": len(apps), "apps": apps}

@app.post("/api/apps/launch")
async def launch_app(req: dict):
    target = req.get("target", "")
    brain = get_brain()
    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, lambda: brain.executor._launch_target(target))
    return {"target": target, "success": success}

# Memory Endpoints
@app.get("/api/memory/interactions")
async def get_interactions(limit: int = 15):
    init_db()
    with sqlite3.connect(settings.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, user_text, app_name, window_title, plan_summary, response_text, success, confidence, created_at
            FROM brain_interactions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return {"interactions": [dict(r) for r in rows]}

# WebSockets
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.active_connections.append(websocket)
    try:
        brain = get_brain()
        ctx = brain.context_engine.observe(action_hint="ws_connect")
        await websocket.send_json({
            "type": "context_update",
            "data": {
                "app_name": ctx.app_name,
                "window_title": ctx.window_title,
                "suggestion": ctx.suggestion
            }
        })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if websocket in state.active_connections:
            state.active_connections.remove(websocket)
    except Exception:
        if websocket in state.active_connections:
            state.active_connections.remove(websocket)

# Static files & Web UI
web_dir = Path(__file__).resolve().parent / "web"
web_dir.mkdir(parents=True, exist_ok=True)
static_dir = web_dir / "static"
static_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = web_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>V.ANSHEE Web UI Loading...</h1>")

@app.on_event("startup")
async def on_startup():
    # Iniciar detector de Wake Word y modelo STT en un hilo en segundo plano
    # para que el servidor HTTP y la interfaz inicien de forma inmediata e interactiva (< 0.5s).
    import threading
    threading.Thread(target=init_wake_word, daemon=True, name="WakeWordInit").start()
