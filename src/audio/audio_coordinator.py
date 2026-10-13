import time
import threading
from typing import Optional

_lock = threading.Lock()
_is_speaking = False
_active_wake_detector = None

def register_wake_detector(detector):
    global _active_wake_detector
    _active_wake_detector = detector

def is_tts_playing() -> bool:
    return _is_speaking

def notify_tts_start():
    global _is_speaking
    _is_speaking = True
    if _active_wake_detector:
        try:
            _active_wake_detector.pause()
        except Exception:
            pass

def notify_tts_end():
    global _is_speaking
    time.sleep(0.35)  # Breve margen para que el eco ambiental no active el micrófono
    _is_speaking = False
    if _active_wake_detector:
        try:
            _active_wake_detector.resume()
        except Exception:
            pass

def get_tts_lock() -> threading.Lock:
    return _lock
