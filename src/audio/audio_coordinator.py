import time
import threading
from typing import Callable, Optional

_lock = threading.Lock()
_is_speaking = False
_current_tts_level: float = 0.0
_active_wake_detector = None
_level_callbacks: list[Callable[[bool, float], None]] = []


def register_wake_detector(detector):
    global _active_wake_detector
    _active_wake_detector = detector


def register_tts_level_callback(cb: Callable[[bool, float], None]):
    if cb not in _level_callbacks:
        _level_callbacks.append(cb)


def is_tts_playing() -> bool:
    return _is_speaking


def get_tts_level() -> float:
    return _current_tts_level if _is_speaking else 0.0


def set_tts_level(level: float):
    global _current_tts_level
    _current_tts_level = max(0.0, min(1.0, float(level)))
    for cb in list(_level_callbacks):
        try:
            cb(_is_speaking, _current_tts_level)
        except Exception:
            pass


def notify_tts_start():
    global _is_speaking, _current_tts_level
    _is_speaking = True
    _current_tts_level = 0.25
    if _active_wake_detector:
        try:
            _active_wake_detector.pause(user_initiated=False)
        except Exception:
            pass
    for cb in list(_level_callbacks):
        try:
            cb(True, _current_tts_level)
        except Exception:
            pass


def notify_tts_end():
    global _is_speaking, _current_tts_level
    _current_tts_level = 0.0
    for cb in list(_level_callbacks):
        try:
            cb(False, 0.0)
        except Exception:
            pass
    time.sleep(0.35)  # Breve margen para que el eco ambiental no active el micrófono
    _is_speaking = False
    if _active_wake_detector:
        try:
            _active_wake_detector.resume(user_initiated=False)
        except Exception:
            pass


def get_tts_lock() -> threading.Lock:
    return _lock
