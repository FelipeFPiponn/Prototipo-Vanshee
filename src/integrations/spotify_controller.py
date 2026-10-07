"""Controlador avanzado de Spotify para V.ANSHEE.

Ofrece una integración en dos niveles:
1. Inspección Local (Cero credenciales): Lee título de pista y artista en tiempo real directamente de la sesión de Windows.
2. Spotify Web API / Connect (Spotipy): Búsqueda precisa, reproducción directa en segundo plano, agregar a cola, guardar en favoritos y control de volumen porcentual.
"""

import re
import os
from typing import Dict, Any, Optional, Tuple

import win32gui
import win32process
import psutil

from config.settings import settings


class SpotifyController:
    """Controlador nativo de Spotify (Local + Web API)."""

    def __init__(self):
        self.client_id = getattr(settings, "SPOTIFY_CLIENT_ID", os.getenv("SPOTIFY_CLIENT_ID", ""))
        self.client_secret = getattr(settings, "SPOTIFY_CLIENT_SECRET", os.getenv("SPOTIFY_CLIENT_SECRET", ""))
        self.redirect_uri = getattr(settings, "SPOTIFY_REDIRECT_URI", os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback"))
        self._sp_client = None

    def _get_sp_client(self):
        """Inicializa el cliente de Spotipy bajo demanda si las credenciales están presentes."""
        if not self._sp_client and self.client_id and self.client_secret:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyOAuth
                scope = "user-read-playback-state,user-modify-playback-state,user-read-currently-playing,user-library-modify"
                auth_manager = SpotifyOAuth(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    redirect_uri=self.redirect_uri,
                    scope=scope,
                    open_browser=False
                )
                self._sp_client = spotipy.Spotify(auth_manager=auth_manager)
            except Exception as e:
                print(f"[SpotifyController Warning] No se pudo inicializar Spotify API: {e}")
        return self._sp_client

    # =========================================================================
    # Nivel 1: Inspección Local sin Claves (Win32 API)
    # =========================================================================

    def get_local_now_playing(self) -> Dict[str, Any]:
        """Obtiene la canción y artista actual leyendo el título de la ventana de Spotify en Windows."""
        spotify_windows = []

        def enum_win(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        proc = psutil.Process(pid)
                        if "spotify" in proc.name().lower():
                            spotify_windows.append(title)
                    except Exception:
                        pass
            return True

        try:
            win32gui.EnumWindows(enum_win, None)
        except Exception as e:
            print(f"[SpotifyController Local Error] {e}")

        # Spotify usa títulos como 'Artist - Track Name', o 'Spotify Free' / 'Spotify Premium' cuando está en pausa o inicio
        for title in spotify_windows:
            if " - " in title:
                parts = title.split(" - ", 1)
                artist = parts[0].strip()
                track = parts[1].strip()
                return {
                    "is_playing": True,
                    "artist": artist,
                    "track": track,
                    "raw_title": title,
                    "source": "local_window"
                }

        # Si encontramos la ventana pero no tiene guion
        if spotify_windows:
            return {
                "is_playing": False,
                "artist": "",
                "track": "",
                "raw_title": spotify_windows[0],
                "source": "local_window"
            }

        return {
            "is_playing": False,
            "artist": "",
            "track": "",
            "raw_title": "",
            "source": "not_running"
        }

    def get_now_playing_summary(self) -> str:
        """Retorna una frase amigable para que V.ANSHEE responda por voz."""
        # Intentar primero por Web API si está activa
        sp = self._get_sp_client()
        if sp:
            try:
                playback = sp.current_playback()
                if playback and playback.get("is_playing") and playback.get("item"):
                    item = playback["item"]
                    track_name = item.get("name", "")
                    artists = ", ".join(a["name"] for a in item.get("artists", []))
                    return f"Está sonando '{track_name}' de {artists} en Spotify."
            except Exception:
                pass

        # Fallback a inspección local de ventana en Windows
        local_info = self.get_local_now_playing()
        if local_info["is_playing"]:
            return f"Está sonando '{local_info['track']}' de {local_info['artist']} en Spotify."
        elif local_info["source"] == "local_window":
            return "Spotify está abierto pero actualmente no hay música en reproducción."
        return "Spotify no está abierto o reproduciendo música en este momento."

    # =========================================================================
    # Nivel 2: Control Avanzado vía Web API
    # =========================================================================

    def play_track_or_artist(self, query: str) -> Tuple[bool, str]:
        """Busca y reproduce directamente la pista o artista."""
        sp = self._get_sp_client()
        if not sp:
            # Fallback a protocolo local URI de escritorio
            import os
            import urllib.parse
            encoded = urllib.parse.quote(query)
            try:
                os.startfile(f"spotify:search:{encoded}")
                try:
                    import time
                    import pyautogui
                    time.sleep(0.5)
                    # Enfocar y reproducir primer resultado
                    for proc in psutil.process_iter(["name"]):
                        if "spotify" in (proc.info.get("name") or "").lower():
                            pyautogui.press("down")
                            time.sleep(0.1)
                            pyautogui.press("enter")
                            break
                except Exception:
                    pass
                return True, f"Reproduciendo '{query}' en la aplicación de Spotify."
            except Exception as e:
                return False, f"Error al abrir Spotify: {e}"

        try:
            results = sp.search(q=query, type="track,artist", limit=1)
            tracks = results.get("tracks", {}).get("items", [])
            if tracks:
                track_uri = tracks[0]["uri"]
                track_name = tracks[0]["name"]
                artist_name = tracks[0]["artists"][0]["name"]
                sp.start_playback(uris=[track_uri])
                msg = f"Reproduciendo '{track_name}' de {artist_name} en Spotify."
                print(f"[SpotifyController API] {msg}")
                return True, msg

            artists = results.get("artists", {}).get("items", [])
            if artists:
                artist_uri = artists[0]["uri"]
                artist_name = artists[0]["name"]
                sp.start_playback(context_uri=artist_uri)
                msg = f"Reproduciendo música de {artist_name} en Spotify."
                print(f"[SpotifyController API] {msg}")
                return True, msg

            return False, f"No encontré canciones para '{query}' en Spotify."
        except Exception as e:
            print(f"[SpotifyController API Error] {e}")
            return False, f"Error al reproducir en Spotify: {e}"

    def add_to_queue(self, query: str) -> Tuple[bool, str]:
        """Añade una canción a la cola de reproducción activa."""
        sp = self._get_sp_client()
        if not sp:
            return False, "La gestión de cola requiere configurar credenciales de Spotify API."

        try:
            results = sp.search(q=query, type="track", limit=1)
            tracks = results.get("tracks", {}).get("items", [])
            if tracks:
                uri = tracks[0]["uri"]
                name = tracks[0]["name"]
                artist = tracks[0]["artists"][0]["name"]
                sp.add_to_queue(uri)
                msg = f"'{name}' de {artist} añadida a la cola de Spotify."
                print(f"[SpotifyController API] {msg}")
                return True, msg
            return False, f"No encontré '{query}' para añadir a la cola."
        except Exception as e:
            return False, f"Error al añadir a la cola: {e}"

    def like_current_track(self) -> Tuple[bool, str]:
        """Guarda la canción que está sonando en 'Canciones que te gustan' (Favoritos)."""
        sp = self._get_sp_client()
        if not sp:
            return False, "Guardar en favoritos requiere Spotify API activa."

        try:
            playback = sp.current_playback()
            if playback and playback.get("item"):
                track_id = playback["item"]["id"]
                track_name = playback["item"]["name"]
                sp.current_user_saved_tracks_add([track_id])
                msg = f"'{track_name}' guardada en tus Canciones Favoritas de Spotify."
                print(f"[SpotifyController API] {msg}")
                return True, msg
            return False, "No hay ninguna canción reproduciéndose actualmente."
        except Exception as e:
            return False, f"Error al guardar canción: {e}"


# Instancia global compartida
spotify_controller = SpotifyController()
