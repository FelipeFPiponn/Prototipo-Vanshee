"""Controlador nativo de OBS Studio mediante OBS-WebSocket v5.

Permite iniciar/detener grabación, transmisiones, cambiar de escena, silenciar micrófonos
y guardar clips de repetición instantánea por voz sin atajos de teclado.
"""

import json
import time
from typing import Dict, Any, Optional, Tuple
import asyncio
import websockets

from config.settings import settings


class OBSStudioController:
    """Gestiona la comunicación con OBS Studio mediante OBS-WebSocket v5."""

    def __init__(self, host: str = "localhost", port: int = 4455, password: str = ""):
        self.host = host
        self.port = port
        self.password = password
        self.ws_url = f"ws://{self.host}:{self.port}"

    async def _send_request(self, request_type: str, request_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Envía una solicitud individual a OBS Studio vía WebSocket."""
        try:
            async with websockets.connect(self.ws_url, open_timeout=1.5) as ws:
                # 1. Recibir Hello
                hello_raw = await ws.recv()
                hello = json.loads(hello_raw)

                # 2. Enviar Identify (con o sin autenticación)
                identify = {
                    "op": 1,
                    "d": {
                        "rpcVersion": 1,
                    }
                }
                await ws.send(json.dumps(identify))
                identified_raw = await ws.recv()

                # 3. Enviar Request
                req_id = f"obs_{int(time.time()*1000)}"
                req = {
                    "op": 6,
                    "d": {
                        "requestType": request_type,
                        "requestId": req_id,
                        "requestData": request_data or {}
                    }
                }
                await ws.send(json.dumps(req))

                # 4. Esperar respuesta
                resp_raw = await ws.recv()
                resp = json.loads(resp_raw)
                if resp.get("op") == 7 and resp.get("d", {}).get("requestStatus", {}).get("result"):
                    return resp.get("d", {}).get("responseData", {})
                return None
        except Exception as e:
            # OBS no está abierto o WebSocket deshabilitado
            return None

    def _run_sync(self, coro) -> Optional[Dict[str, Any]]:
        """Ejecuta una corrutina de forma segura incluso si ya existe un event loop activo en el hilo actual."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: asyncio.run(coro))
                    return future.result(timeout=4.0)
            else:
                return asyncio.run(coro)
        except Exception:
            return None

    def toggle_recording(self) -> Tuple[bool, str]:
        """Alterna el estado de grabación de OBS Studio."""
        res = self._run_sync(self._send_request("ToggleRecord"))
        if res is not None:
            active = res.get("outputActive", False)
            msg = "Grabación iniciada en OBS Studio." if active else "Grabación detenida en OBS Studio."
            print(f"[OBSController] {msg}")
            return True, msg
        return False, "OBS Studio no está abierto o su WebSocket no está habilitado."

    def start_recording(self) -> Tuple[bool, str]:
        res = self._run_sync(self._send_request("StartRecord"))
        if res is not None:
            return True, "Grabación iniciada en OBS Studio."
        return False, "No se pudo iniciar grabación en OBS Studio."

    def stop_recording(self) -> Tuple[bool, str]:
        res = self._run_sync(self._send_request("StopRecord"))
        if res is not None:
            return True, "Grabación finalizada y guardada en OBS Studio."
        return False, "No se pudo detener grabación en OBS Studio."

    def set_scene(self, scene_name: str) -> Tuple[bool, str]:
        """Cambia la escena activa en OBS Studio."""
        res = self._run_sync(self._send_request("SetCurrentProgramScene", {"sceneName": scene_name}))
        if res is not None:
            msg = f"Escena cambiada a '{scene_name}' en OBS Studio."
            print(f"[OBSController] {msg}")
            return True, msg
        return False, f"No se pudo cambiar a la escena '{scene_name}' en OBS."

    def save_replay_buffer(self) -> Tuple[bool, str]:
        """Guarda el clip de repetición instantánea (Replay Buffer)."""
        res = self._run_sync(self._send_request("SaveReplayBuffer"))
        if res is not None:
            msg = "¡Clip de repetición guardado con éxito en OBS Studio!"
            print(f"[OBSController] {msg}")
            return True, msg
        return False, "El búfer de repetición no está activo en OBS."


# Instancia global compartida
obs_controller = OBSStudioController()
