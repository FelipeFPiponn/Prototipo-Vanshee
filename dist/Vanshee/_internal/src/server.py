import os
import sys
import json
import asyncio
import sqlite3
import tempfile
import time
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sounddevice as sd

ROOT_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
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
from src.integrations.editor_hub import editor_hub

app = FastAPI(title="V.ANSHEE Core Assistant Console", version="2.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    # Prevent browser caching of UI static assets and HTML
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

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
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None

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

def broadcast_sync(event_type: str, data: Any):
    """Transmite de manera segura a todos los WebSockets desde hilos secundarios sin romper el loop de Uvicorn."""
    if state.main_loop and state.main_loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(broadcast_ws(event_type, data), state.main_loop)
            return
        except Exception as e:
            print(f"[BroadcastSync Error]: {e}")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_ws(event_type, data), loop)
        else:
            loop.run_until_complete(broadcast_ws(event_type, data))
    except Exception as e:
        print(f"[BroadcastSync Fallback Error]: {e}")

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

# Callback when Wake Word "Vanshe" / "Banshee" is heard in background
def on_wake_word_detected(full_phrase: str, trailing_command: str):
    print(f"\n[Vanshee Wake Trigger] Frase: '{full_phrase}' | Comando detectado: '{trailing_command}'")
    
    # Mostrar y enfocar automáticamente la ventana de chat al hablar
    window_bridge.show_chat()
    
    clean_cmd = trailing_command.strip()
    if clean_cmd:
        if debouncer.is_duplicate(clean_cmd):
            print(f"[Server Debounce] Comando duplicado ignorado desde WakeWord: '{clean_cmd}'")
            return

        display_phrase = full_phrase.strip()
        # Asegurar que en el chat el usuario siempre vea "vanshe [comando]" si el prefijo fue podado
        if not re.search(r"\b(vanshe|banshe|vanshee|banshee)\b", display_phrase, re.IGNORECASE):
            display_phrase = f"vanshe {clean_cmd}"

        # 1. Mostrar de inmediato la burbuja del usuario con su comando en el chat
        broadcast_sync("wake_word_command", {
            "phrase": display_phrase,
            "command": clean_cmd
        })

        # 2. Ejecutar la acción correspondiente con el cerebro de Vanshee
        brain = get_brain()
        res = brain.handle_user_input(clean_cmd)
        if brain.is_awaiting_user_feedback() and state.wake_detector is not None:
            state.wake_detector.trigger_manual_listen(duration=15.0)

        res_payload = {
            "source": "wake_word",
            "success": res.success,
            "response_text": res.response_text,
            "plan_summary": res.plan_summary,
            "context": {
                "app_name": res.context.app_name if res.context else "",
                "window_title": res.context.window_title if res.context else "",
                "suggestion": res.context.suggestion if res.context else ""
            }
        }
        debouncer.last_result = res_payload
        broadcast_sync("command_completed", res_payload)
    else:
        # El usuario solo dijo "Vanshe" -> responder con "¿Dime?" y abrir escucha activa
        tts = get_tts()
        tts.speak("¿Dime?", block=True)
        if state.wake_detector:
            state.wake_detector.trigger_manual_listen(duration=10.0)
        broadcast_sync("wake_word_listening", {
            "phrase": full_phrase
        })

def init_wake_word():
    if state.wake_detector is None and getattr(settings, "WAKE_WORD_ENABLED", True):
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass

        # Auto-enlazar al micrófono real activo del sistema si no ha sido configurado manualmente
        if getattr(settings, "AUDIO_INPUT_DEVICE", None) is None:
            try:
                devices, def_idx, def_name = get_system_available_microphones()
                if def_idx is not None:
                    settings.AUDIO_INPUT_DEVICE = def_idx
                    settings.AUDIO_DEVICE_NAME = def_name or ""
                    print(f"[Audio] Micrófono activo detectado y auto-asignado: Dispositivo {def_idx} ({def_name})")
            except Exception as e:
                print(f"[Audio] Error auto-detectando micrófono: {e}")

        stt = get_stt()
        if stt:
            state.wake_detector = WakeWordDetector(
                stt_engine=stt,
                on_wake_detected=on_wake_word_detected,
                is_awaiting_feedback=lambda: state.brain.is_awaiting_user_feedback() if state.brain else False,
                threshold_rms=getattr(settings, "AUDIO_THRESHOLD_RMS", 45.0),
                device_index=getattr(settings, "AUDIO_INPUT_DEVICE", None)
            )
            state.wake_detector.start()
            broadcast_sync("stt_ready", {
                "status": "ready",
                "model": settings.STT_MODEL_SIZE
            })
            broadcast_sync("mic_state_changed", {
                "is_listening": True,
                "mode": "listening"
            })

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

class PinWindowRequest(BaseModel):
    topmost: bool

class MoveWindowRequest(BaseModel):
    x: int
    y: int

class WindowBridge:
    def __init__(self):
        self.chat_window = None
        self.launcher_window = None
        self.is_chat_visible: bool = True
        self.last_toggle_time: float = 0.0

    def show_chat(self) -> bool:
        self.is_chat_visible = True
        shown = False
        if self.chat_window:
            try:
                self.chat_window.show()
                self.chat_window.restore()
                shown = True
            except Exception:
                pass
        if self.launcher_window and hasattr(self.launcher_window, "hide"):
            try:
                self.launcher_window.hide()
            except Exception:
                pass
        try:
            import win32gui
            import win32con
            for title in ["Vanshee Chat", "Vanshee", "Banshee Chat", "Banshee"]:
                hwnd = win32gui.FindWindow(None, title)
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
                    win32gui.SetForegroundWindow(hwnd)
                    shown = True
        except Exception:
            pass
        return shown

    def hide_chat(self) -> bool:
        self.is_chat_visible = False
        hidden = False
        if self.chat_window:
            try:
                self.chat_window.hide()
                hidden = True
            except Exception:
                pass
        if self.launcher_window and hasattr(self.launcher_window, "show"):
            try:
                self.launcher_window.show()
            except Exception:
                pass
        try:
            import win32gui
            import win32con
            for title in ["Vanshee Chat", "Vanshee", "Banshee Chat", "Banshee"]:
                hwnd = win32gui.FindWindow(None, title)
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                    hidden = True
        except Exception:
            pass
        return hidden

    def toggle_chat(self) -> bool:
        now = time.time()
        if (now - self.last_toggle_time) < 0.4:
            return self.is_chat_visible
        self.last_toggle_time = now

        if self.is_chat_visible:
            return self.hide_chat()
        else:
            return self.show_chat()

window_bridge = WindowBridge()

# API Routes
@app.post("/api/window/move")
async def move_window(req: MoveWindowRequest):
    """Mueve la ventana de chat a las coordenadas especificadas."""
    if window_bridge.chat_window:
        try:
            window_bridge.chat_window.move(req.x, req.y)
            return {"status": "ok", "x": req.x, "y": req.y}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "no chat window"}

@app.post("/api/window/pin")
async def toggle_window_pin(req: PinWindowRequest):
    """Fija o desfija la ventana de Banshee como 'Siempre visible' (HWND_TOPMOST) en Windows."""
    pinned = False
    if window_bridge.chat_window:
        try:
            window_bridge.chat_window.on_top = req.topmost
            pinned = True
        except Exception:
            pass
    try:
        import ctypes
        import win32gui
        brain = get_brain()
        hwnd = 0
        if win32gui:
            for title in ["Vanshee Chat", "Vanshee", "Banshee Chat", "Banshee"]:
                h = win32gui.FindWindow(None, title)
                if h:
                    hwnd = h
                    break
            if not hwnd:
                win = brain.executor.window_manager.find_window("vanshee")
                if win:
                    hwnd = win["hwnd"]
            if not hwnd:
                hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            flag = -1 if req.topmost else -2  # HWND_TOPMOST = -1, HWND_NOTOPMOST = -2
            ctypes.windll.user32.SetWindowPos(hwnd, flag, 0, 0, 0, 0, 0x0001 | 0x0002)  # SWP_NOSIZE | SWP_NOMOVE
            return {"status": "ok", "topmost": req.topmost, "hwnd": hwnd}
    except Exception as e:
        print(f"[Pin Window Error] {e}")
    return {"status": "ok", "topmost": req.topmost}


@app.post("/api/window/show_chat")
async def show_chat_window():
    """Muestra y trae al frente la ventana de Chat."""
    success = window_bridge.show_chat()
    await broadcast_ws("window_state", {"visible": True})
    return {"status": "ok", "action": "show", "success": success}

@app.post("/api/window/hide_chat")
async def hide_chat_window():
    """Oculta la ventana de Chat liberando el 100% de la pantalla para otras aplicaciones."""
    success = window_bridge.hide_chat()
    await broadcast_ws("window_state", {"visible": False})
    return {"status": "ok", "action": "hide", "success": success}

@app.post("/api/window/toggle_chat")
async def toggle_chat_window():
    """Alterna la visibilidad de la ventana de Chat."""
    success = window_bridge.toggle_chat()
    await broadcast_ws("window_state", {"visible": window_bridge.is_chat_visible})
    return {"status": "ok", "visible": window_bridge.is_chat_visible, "success": success}

@app.post("/api/system/shutdown")
async def shutdown_system():
    """Cierra y finaliza completamente la aplicación Banshee y el proceso de terminal."""
    def _delayed_exit():
        time.sleep(0.2)
        if state.wake_detector:
            try:
                state.wake_detector.stop()
            except Exception:
                pass
        import os
        os._exit(0)

    import threading
    threading.Thread(target=_delayed_exit, daemon=True).start()
    return {"status": "shutting_down", "message": "Vanshee se está cerrando por completo."}

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
        "mic_listening": state.wake_detector.is_listening_active if (state.wake_detector and getattr(settings, "WAKE_WORD_ENABLED", True)) else True,
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

def get_system_available_microphones(refresh: bool = False) -> tuple[list[dict], Optional[int], Optional[str]]:
    """
    Detecta exclusivamente los dispositivos de entrada de audio realmente DISPONIBLES y activos en el sistema.
    Filtra duplicados entre APIs de PortAudio (MME, DirectSound, WASAPI, WDM-KS), descarta dispositivos
    desconectados/deshabilitados, mapeadores genéricos y dispositivos de loopback.
    """
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass

    if refresh:
        was_paused = False
        if state.wake_detector:
            was_paused = state.wake_detector.is_paused
            state.wake_detector.pause()
            time.sleep(0.15)
        try:
            sd._terminate()
            sd._initialize()
        except Exception as e:
            print(f"[Audio] Error reinicializando PortAudio: {e}")
        if state.wake_detector and not was_paused:
            time.sleep(0.15)
            state.wake_detector.resume()

    active_windows_mics = {}
    default_mic_id = None
    default_friendly_name = None

    # 1. Consultar a la API nativa de Windows (CoreAudio / pycaw) el estado real del hardware
    try:
        from pycaw.pycaw import AudioUtilities, AudioDeviceState
        try:
            def_mic = AudioUtilities.GetMicrophone()
            if def_mic:
                default_mic_id = def_mic.GetId()
        except Exception:
            pass

        for d in AudioUtilities.GetAllDevices():
            st = getattr(d, "state", None)
            is_active = (st == AudioDeviceState.Active) or (st == 1)
            if is_active:
                fname = getattr(d, "FriendlyName", "").strip()
                if fname:
                    is_def = (d.id == default_mic_id)
                    if is_def:
                        default_friendly_name = fname
                    active_windows_mics[fname.lower()] = {
                        "name": fname,
                        "is_default": is_def,
                        "id": d.id
                    }
    except Exception as e:
        print(f"[Audio] Warning consultando pycaw: {e}")

    # 2. Elegir Host API en PortAudio (DirectSound ofrece nombres completos y conversión de muestreo nativa)
    hostapis = sd.query_hostapis()
    chosen_api_idx = None
    for i, h in enumerate(hostapis):
        if "directsound" in h["name"].lower():
            chosen_api_idx = i
            break
    if chosen_api_idx is None:
        for i, h in enumerate(hostapis):
            if "mme" in h["name"].lower():
                chosen_api_idx = i
                break
    if chosen_api_idx is None:
        chosen_api_idx = sd.default.hostapi

    current_selected = getattr(settings, "AUDIO_INPUT_DEVICE", None)
    current_selected_name = getattr(settings, "AUDIO_DEVICE_NAME", "")

    all_devs = sd.query_devices()
    devices = []
    seen_names = set()
    found_default_idx = None

    for idx, d in enumerate(all_devs):
        if d.get("max_input_channels", 0) <= 0:
            continue
        if d.get("hostapi") != chosen_api_idx:
            continue

        raw_name = d.get("name", "").strip()
        lower_name = raw_name.lower()

        # Omitir entradas virtuales / genéricas de Windows
        if any(term in lower_name for term in [
            "sound mapper", "controlador primario", "primary sound capture",
            "mezcla estéreo", "stereo mix", "bthhfenum"
        ]):
            continue

        # Verificar si sounddevice puede abrir el stream de captura sin fallar
        try:
            sd.check_input_settings(device=idx, channels=1, samplerate=16000)
        except Exception:
            continue

        # Validar contra los dispositivos activos reales de Windows si pycaw devolvió resultados
        is_default = False
        if active_windows_mics:
            matched = False
            for act_lower, act_info in active_windows_mics.items():
                if act_lower in lower_name or lower_name in act_lower:
                    matched = True
                    if act_info["is_default"]:
                        is_default = True
                    break
            if not matched:
                continue
        else:
            is_default = (idx == sd.default.device[0])

        if is_default:
            found_default_idx = idx

        clean_name = raw_name
        if clean_name in seen_names:
            continue
        seen_names.add(clean_name)

        is_selected = False
        if current_selected is not None and current_selected == idx:
            is_selected = True
        elif current_selected_name and current_selected_name.lower() in clean_name.lower():
            is_selected = True

        devices.append({
            "index": idx,
            "name": clean_name,
            "channels": d.get("max_input_channels", 1),
            "default_samplerate": int(d.get("default_samplerate", 16000)),
            "is_default": is_default,
            "is_selected": is_selected
        })

    return devices, found_default_idx, default_friendly_name

# Audio Devices Management
@app.get("/api/audio/devices")
async def list_audio_devices(refresh: bool = False):
    """Enumera únicamente los micrófonos físicos o activos realmente disponibles en Windows."""
    devices, default_idx, default_name = get_system_available_microphones(refresh=refresh)
    current_selected = getattr(settings, "AUDIO_INPUT_DEVICE", None)
    current_selected_name = getattr(settings, "AUDIO_DEVICE_NAME", "")
    return {
        "devices": devices,
        "selected_index": current_selected,
        "selected_name": current_selected_name,
        "default_index": default_idx,
        "default_name": default_name
    }

@app.post("/api/audio/devices/refresh")
async def refresh_audio_devices():
    """Fuerza la re-enumeración de hardware de audio en Windows para detectar dispositivos recién conectados."""
    devices, default_idx, default_name = get_system_available_microphones(refresh=True)
    current_selected = getattr(settings, "AUDIO_INPUT_DEVICE", None)
    current_selected_name = getattr(settings, "AUDIO_DEVICE_NAME", "")
    return {
        "status": "refreshed",
        "devices": devices,
        "selected_index": current_selected,
        "selected_name": current_selected_name,
        "default_index": default_idx,
        "default_name": default_name
    }

@app.post("/api/audio/devices/select")
async def select_audio_device(req: DeviceSelectRequest):
    target_idx = None if (req.device_index is None or req.device_index < 0) else req.device_index
    
    # Si seleccionó 'Predeterminado de Windows', resolver al micrófono físico activo
    if target_idx is None:
        try:
            devices, def_idx, def_name = get_system_available_microphones(refresh=False)
            if def_idx is not None:
                target_idx = def_idx
                req.device_name = def_name or req.device_name
        except Exception as e:
            print(f"[Audio] Error resolviendo dispositivo predeterminado: {e}")

    settings.AUDIO_INPUT_DEVICE = target_idx
    settings.AUDIO_DEVICE_NAME = req.device_name or ""
    
    # Actualizar detector de wake word si está activo asegurando escucha continua
    if state.wake_detector:
        state.wake_detector.update_settings(device_index=target_idx)
        state.wake_detector.resume(user_initiated=False)
        await broadcast_ws("mic_state_changed", {"is_listening": state.wake_detector.is_listening_active, "mode": "listening"})

    return {
        "status": "updated",
        "device_index": target_idx,
        "device_name": settings.AUDIO_DEVICE_NAME,
        "is_listening": state.wake_detector.is_listening_active if state.wake_detector else True
    }

@app.post("/api/audio/listen_toggle")
async def toggle_audio_listening():
    """
    Alterna la escucha del micrófono entre Activo y Pausado (Mute / Unmute):
    - Si está escuchando: pausa la escucha (micrófono en mute).
    - Si está pausado: activa la escucha continua normal.
    """
    init_wake_word()
    
    if not state.wake_detector:
        return {"status": "error", "message": "Detector de voz no disponible", "is_listening": False}

    is_currently_listening = state.wake_detector.is_listening_active
    
    if is_currently_listening:
        state.wake_detector.pause(user_initiated=True)
        await broadcast_ws("mic_state_changed", {"is_listening": False, "mode": "paused"})
        return {"status": "ok", "is_listening": False, "mode": "paused"}
    else:
        state.wake_detector.resume(user_initiated=True)
        await broadcast_ws("mic_state_changed", {"is_listening": True, "mode": "listening"})
        return {"status": "ok", "is_listening": True, "mode": "listening"}

@app.get("/api/audio/listening_status")
async def get_listening_status():
    is_listening = True
    if state.wake_detector and getattr(settings, "WAKE_WORD_ENABLED", True):
        is_listening = state.wake_detector.is_listening_active
    return {"is_listening": is_listening, "mode": "listening" if is_listening else "paused"}

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
    """Activa la ventana de escucha activa de Vanshee para hablarle de inmediato."""
    init_wake_word()
    if state.wake_detector:
        state.wake_detector.resume()
        state.wake_detector.trigger_manual_listen(duration=8.0)
    tts = get_tts()
    tts.speak("¿Dime?", block=False)
    await broadcast_ws("mic_state_changed", {"is_listening": True, "mode": "listening"})
    await broadcast_ws("wake_word_listening", {"phrase": "manual_click"})
    return {"status": "ok", "is_listening": True, "mode": "active_listening"}

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

import numpy as np
import wave

class LiveMicTester:
    def __init__(self):
        self.is_running = False
        self.stream = None
        self.buffer = []
        self.start_time = 0.0
        self.last_rms = 0.0
        self.max_rms = 0.0
        self.device_index = None
        self.was_wake_paused = False
        self._lock = threading.Lock()

    def start(self, device_index=None) -> bool:
        with self._lock:
            if self.is_running:
                self.stop_internal()

            self.buffer = []
            self.max_rms = 0.0
            self.last_rms = 0.0
            self.device_index = device_index
            self.start_time = time.time()
            self.is_running = True

            # Pausar temporalmente wake_detector de fondo para evitar conflictos de hardware en Windows
            self.was_wake_paused = False
            if state.wake_detector:
                self.was_wake_paused = state.wake_detector.is_user_paused
                state.wake_detector.pause(user_initiated=False)

            def stream_callback(indata, frames, time_info, status):
                if not self.is_running:
                    return
                chunk = indata.copy()
                self.buffer.append(chunk)
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                self.last_rms = rms
                if rms > self.max_rms:
                    self.max_rms = rms

            try:
                self.stream = sd.InputStream(
                    device=self.device_index,
                    channels=1,
                    samplerate=16000,
                    dtype="int16",
                    blocksize=1600,
                    callback=stream_callback
                )
                self.stream.start()
                return True
            except Exception as e:
                print(f"[LiveMicTester Error]: {e}")
                self.is_running = False
                if state.wake_detector and not self.was_wake_paused:
                    state.wake_detector.resume(user_initiated=False)
                return False

    def stop_internal(self):
        self.is_running = False
        s = self.stream
        self.stream = None
        if s:
            try:
                s.stop()
                s.close()
            except Exception:
                pass

    def stop(self) -> dict:
        with self._lock:
            if not self.is_running and not self.buffer:
                return {
                    "status": "ok",
                    "action": "stopped",
                    "is_testing": False,
                    "duration": 0.0,
                    "volume_rms": 0.0,
                    "max_rms": 0.0,
                    "quality_verdict": "Sin prueba realizada",
                    "has_sound": False,
                    "advice": "Presiona el botón para iniciar la prueba de detección.",
                    "audio_url": ""
                }

            self.stop_internal()
            dur = max(0.1, time.time() - self.start_time)

            if state.wake_detector and not self.was_wake_paused:
                state.wake_detector.resume(user_initiated=False)

            if not self.buffer:
                return {
                    "status": "ok",
                    "action": "stopped",
                    "is_testing": False,
                    "duration": round(dur, 1),
                    "volume_rms": 0.0,
                    "max_rms": 0.0,
                    "quality_verdict": "No se escucha al no percibir sonido alguno",
                    "has_sound": False,
                    "advice": "No se recibieron datos de audio del micrófono.",
                    "audio_url": ""
                }

            try:
                full_audio = np.concatenate(self.buffer, axis=0)
                avg_rms = float(np.sqrt(np.mean(full_audio.astype(np.float32) ** 2)))
                max_rms = float(self.max_rms)

                # Guardar WAV para reproducción inmediata
                audio_dir = web_dir / "static" / "audio"
                audio_dir.mkdir(parents=True, exist_ok=True)
                wav_path = audio_dir / "mic_test_sample.wav"

                with wave.open(str(wav_path), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(full_audio.tobytes())

                audio_url = f"/static/audio/mic_test_sample.wav?t={int(time.time()*1000)}"
            except Exception as e:
                print(f"[LiveMicTester Save Error]: {e}")
                avg_rms = float(self.last_rms)
                max_rms = float(self.max_rms)
                audio_url = ""

            has_sound = max_rms >= 38.0
            if max_rms >= 60.0:
                quality_status = "Se escucha fuerte y claro"
                advice = "¡Excelente! El micrófono capta tu voz de forma legítima, nítida y con volumen adecuado."
                rec_thresh = max(55.0, round(avg_rms * 0.7, 0))
            elif max_rms >= 38.0:
                quality_status = "Voz moderada percibida"
                advice = "El micrófono capta sonido pero con volumen algo bajo. Recomendamos acercarte más o subir el volumen en Windows (80-100%)."
                rec_thresh = 45.0
            else:
                quality_status = "No se escucha al no percibir sonido alguno"
                advice = "No se detectó sonido alguno. Verifica que el micrófono no tenga botón físico de silencio o esté en mute en Windows."
                rec_thresh = 100.0

            return {
                "status": "ok",
                "action": "stopped",
                "is_testing": False,
                "duration": round(dur, 1),
                "volume_rms": round(avg_rms, 1),
                "max_rms": round(max_rms, 1),
                "quality_verdict": quality_status,
                "has_sound": has_sound,
                "advice": advice,
                "recommended_threshold": rec_thresh,
                "audio_url": audio_url
            }

    def get_current_meter(self) -> dict:
        rms = self.last_rms
        pct = min(100.0, round((rms / 240.0) * 100.0, 1))
        if rms >= 60.0:
            verdict = "🎙️ Se escucha fuerte y claro"
            status_type = "clear"
        elif rms >= 38.0:
            verdict = "🔉 Voz moderada / Sonido captado"
            status_type = "moderate"
        else:
            verdict = "🔇 No se escucha al no percibir sonido alguno"
            status_type = "silence"

        return {
            "is_testing": self.is_running,
            "rms": round(rms, 1),
            "max_rms": round(self.max_rms, 1),
            "level_percent": pct,
            "verdict": verdict,
            "status_type": status_type,
            "has_sound": self.max_rms >= 38.0,
            "is_speaking": rms >= 38.0
        }

mic_tester = LiveMicTester()

@app.post("/api/audio/test/start")
async def start_mic_test_endpoint(request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    dev_idx = body.get("device_index", None)
    if dev_idx is None:
        dev_idx = getattr(settings, "AUDIO_INPUT_DEVICE", None)

    success = await asyncio.to_thread(mic_tester.start, dev_idx)
    if not success:
        return {"status": "error", "message": "No se pudo acceder al micrófono seleccionado.", "is_testing": False}

    async def _broadcast_tester():
        while mic_tester.is_running:
            if state.active_connections:
                await broadcast_ws("mic_test_meter", mic_tester.get_current_meter())
            await asyncio.sleep(0.08)

    asyncio.create_task(_broadcast_tester())
    await broadcast_ws("mic_test_state", {"is_testing": True})
    return {"status": "ok", "action": "started", "is_testing": True}

@app.post("/api/audio/test/stop")
async def stop_mic_test_endpoint():
    res = await asyncio.to_thread(mic_tester.stop)
    await broadcast_ws("mic_test_state", {"is_testing": False, "result": res})
    return res

@app.post("/api/audio/test/toggle")
@app.post("/api/audio/mic_record_test")
@app.post("/api/audio/test_mic")
async def toggle_mic_test_endpoint(request: Request):
    """
    Alterna la prueba de micrófono en tiempo real de forma no bloqueante:
    - Si está activa: la detiene de inmediato, devuelve veredicto verídico y WAV.
    - Si está inactiva: inicia la detección en vivo.
    """
    if mic_tester.is_running:
        res = await asyncio.to_thread(mic_tester.stop)
        await broadcast_ws("mic_test_state", {"is_testing": False, "result": res})
        return res
    else:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        dev_idx = body.get("device_index", None)
        if dev_idx is None:
            dev_idx = getattr(settings, "AUDIO_INPUT_DEVICE", None)

        success = await asyncio.to_thread(mic_tester.start, dev_idx)
        if not success:
            return {"status": "error", "message": "No se pudo acceder al micrófono seleccionado.", "is_testing": False}

        async def _broadcast_tester():
            while mic_tester.is_running:
                if state.active_connections:
                    await broadcast_ws("mic_test_meter", mic_tester.get_current_meter())
                await asyncio.sleep(0.08)

        asyncio.create_task(_broadcast_tester())
        await broadcast_ws("mic_test_state", {"is_testing": True})
        return {"status": "ok", "action": "started", "is_testing": True}

@app.get("/api/audio/test/meter")
async def get_test_meter_endpoint():
    return mic_tester.get_current_meter()

@app.get("/api/audio/mic_level")
async def get_mic_level_endpoint():
    """Devuelve el nivel RMS y veredicto real del micrófono en uso (sea en prueba o escucha continua)."""
    rms = 0.0
    if mic_tester.is_running:
        return mic_tester.get_current_meter()
    elif state.wake_detector and state.wake_detector.is_listening_active:
        rms = getattr(state.wake_detector, "last_rms", 0.0)

    pct = min(100.0, round((rms / 240.0) * 100.0, 1))
    if rms >= 60.0:
        verdict = "🎙️ Se escucha fuerte y claro"
        status_type = "clear"
    elif rms >= 38.0:
        verdict = "🔉 Voz moderada / Sonido captado"
        status_type = "moderate"
    else:
        verdict = "🔇 No se escucha al no percibir sonido alguno"
        status_type = "silence"

    return {
        "is_testing": False,
        "rms": round(rms, 1),
        "level_percent": pct,
        "verdict": verdict,
        "status_type": status_type,
        "has_sound": rms >= 38.0,
        "is_listening": state.wake_detector.is_listening_active if state.wake_detector else True
    }

@app.post("/api/settings")
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
    seen_paths = set()

    # 1. Primero agregar los juegos oficiales de Steam
    if hasattr(indexer, "steam_indexer") and indexer.steam_indexer:
        for appid, game in indexer.steam_indexer.games.items():
            g_name = game["name"]
            g_uri = game["uri"]
            if q and q not in g_name.lower() and q not in g_uri.lower():
                continue
            seen_paths.add(g_uri)
            apps.append({
                "name": g_name,
                "target": g_name.lower(),
                "path": g_uri,
                "category": "gaming"
            })

    # 2. Agregar aplicaciones locales indexadas (evitando duplicados por alias)
    for name, path in indexer.app_index.items():
        if path in seen_paths:
            continue
        if q and q not in name and q not in path.lower():
            continue

        seen_paths.add(path)
        category = "utility"
        name_lower = name.lower()
        path_lower = path.lower()

        if path_lower.startswith("steam://") or any(w in name_lower for w in ["steam", "epic", "game", "discord", "xbox", "riot"]):
            category = "gaming"
        elif any(w in name_lower for w in ["code", "visual studio", "pycharm", "git", "terminal", "sublime", "notepad++"]):
            category = "developer"
        elif any(w in name_lower for w in ["chrome", "edge", "firefox", "brave", "opera"]):
            category = "browser"
        elif any(w in name_lower for w in ["spotify", "vlc", "media", "music", "audio", "video"]):
            category = "media"
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

@app.websocket("/ws/editor")
async def editor_websocket_endpoint(websocket: WebSocket):
    """Canal WebSocket bidireccional de baja latencia para extensiones de IDE (Antigravity, VS Code, Cursor)."""
    await websocket.accept()
    session_id = f"session_{int(time.time()*1000)}_{id(websocket)}"
    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                msg = json.loads(raw_msg)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")
            method = msg.get("method", "")

            # 1. Registro inicial de la extensión del editor
            if msg_type == "register" or method == "register":
                editor_name = msg.get("editor_name") or msg.get("params", {}).get("editor_name", "editor")
                metadata = msg.get("metadata") or msg.get("params", {})
                editor_hub.register_session(
                    session_id=session_id,
                    editor_name=editor_name,
                    ws=websocket,
                    metadata=metadata,
                    loop=asyncio.get_running_loop()
                )
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "id": msg.get("id", "init"),
                    "result": {"status": "connected", "session_id": session_id}
                })

            # 2. Actualización de contexto activo desde el IDE
            elif msg_type == "context_update" or method == "context_update":
                context_data = msg.get("data") or msg.get("params", {})
                editor_hub.update_session_context(session_id, context_data)

            # 3. Respuesta a una llamada RPC iniciada por V.ANSHEE
            elif "id" in msg and ("result" in msg or "error" in msg):
                editor_hub.handle_rpc_response(msg)

            # 4. Ping / Heartbeat
            elif msg.get("method") == "ping" or msg_type == "ping":
                await websocket.send_json({"jsonrpc": "2.0", "id": msg.get("id"), "result": "pong"})

    except WebSocketDisconnect:
        editor_hub.unregister_session(session_id)
    except Exception as e:
        print(f"[Server WS Editor Error] {e}")
        editor_hub.unregister_session(session_id)

# Endpoints REST para inspección y control de editores
@app.get("/api/editor/sessions")
async def list_editor_sessions():
    """Retorna las sesiones activas de editores de código conectados."""
    sessions = []
    for s in editor_hub.sessions.values():
        sessions.append({
            "session_id": s.session_id,
            "editor_name": s.editor_name,
            "workspace_root": s.workspace_root,
            "active_file": s.active_file,
            "language_id": s.language_id,
            "cursor_line": s.cursor_line,
            "cursor_column": s.cursor_column,
            "connected_at": s.connected_at
        })
    return {"total": len(sessions), "sessions": sessions}

@app.post("/api/editor/send_prompt")
async def editor_send_prompt(req: dict):
    prompt = req.get("prompt", "")
    editor_hint = req.get("editor_hint", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="El prompt no puede estar vacío.")
    success = editor_hub.send_prompt(prompt, editor_hint=editor_hint)
    return {"success": success, "prompt": prompt}

@app.post("/api/editor/insert_code")
async def editor_insert_code(req: dict):
    code = req.get("code", "")
    file_path = req.get("file_path", "")
    editor_hint = req.get("editor_hint", "")
    success = editor_hub.insert_code(code, file_path=file_path, editor_hint=editor_hint)
    return {"success": success}

# Static files & Web UI
def _resolve_web_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cand = Path(meipass) / "src" / "web"
            if cand.exists():
                return cand
            cand = Path(meipass) / "web"
            if cand.exists():
                return cand
        exe_dir = Path(sys.executable).resolve().parent
        for sub in [exe_dir / "src" / "web", exe_dir / "_internal" / "src" / "web", exe_dir / "web"]:
            if sub.exists():
                return sub
    return Path(__file__).resolve().parent / "web"

web_dir = _resolve_web_dir()
web_dir.mkdir(parents=True, exist_ok=True)
static_dir = web_dir / "static"
static_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = web_dir / "index.html"
    if index_file.exists():
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        return FileResponse(index_file, headers=headers)
    return HTMLResponse("<h1>V.ANSHEE Web UI Loading...</h1>")

@app.get("/launcher", response_class=HTMLResponse)
async def serve_launcher():
    launcher_file = web_dir / "launcher.html"
    if launcher_file.exists():
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        return FileResponse(launcher_file, headers=headers)
    return HTMLResponse("<h1>Vanshee Launcher Loading...</h1>")

@app.on_event("startup")
async def on_startup():
    state.main_loop = asyncio.get_running_loop()
    # Iniciar detector de Wake Word y modelo STT en un hilo en segundo plano
    # para que el servidor HTTP y la interfaz inicien de forma inmediata e interactiva (< 0.5s).
    import threading
    threading.Thread(target=init_wake_word, daemon=True, name="WakeWordInit").start()
