import re
import json
import ollama
from pydantic import BaseModel, Field
from config.settings import settings

from src.utils.query_cleaner import clean_search_term

class StepParameters(BaseModel):
    project_type: str = "none"         # Ej: 'python', 'node', 'cpp', 'none'
    project_name: str = "nuevo_proyecto"
    path: str = ""
    file_name: str = ""
    content: str = ""
    language: str = "txt"
    position: str = ""                # Ej: 'left', 'right', 'top', 'bottom', 'top_left', 'top_right', 'bottom_left', 'bottom_right', 'center', 'maximize', 'minimize', 'restore'

class ActionStep(BaseModel):
    intent: str                        # OPEN_APP | SEARCH_CONTENT | WINDOW_CONTROL | CREATE_PROJECT | CREATE_FILE | WRITE_TEXT | SYSTEM_CONTROL | FORGET_COMMAND
    target: str                        # Ej: 'vscode', 'youtube', 'chatgpt', 'spotify', 'active', 'next_tab', 'close_tab'
    parameters: StepParameters = Field(default_factory=StepParameters)

class ParsedPipeline(BaseModel):
    raw_text: str
    steps: list[ActionStep]
    confidence: float = 1.0

class IntentParser:
    def __init__(self):
        self.system_prompt = (
            "Eres el motor NLU de V.ANSHEE para automatización en Windows OS.\n"
            "Analiza el texto del usuario y descompón la solicitud en una lista ordenada de PASOS INDEPENDIENTES (pipeline).\n\n"
            "REGLA CRÍTICA DE COMANDOS COMPUESTOS Y MÚLTIPLES:\n"
            "Si la frase contiene conectores como 'y', 'e', 'luego', 'además', 'después' o múltiples acciones independientes:\n"
            "Genera un objeto paso separado para CADA ACCIÓN DISTINTA en el orden en que deben ejecutarse.\n"
            "Ejemplo: 'abre youtube a la izquierda y antigravity a la derecha' genera DOS pasos: uno para youtube (position='left') y otro para antigravity (position='right').\n\n"
            "REGLA DE BÚSQUEDA VERSUS APERTURA:\n"
            "Si el usuario pide abrir un servicio y buscar algo en él (ej: 'abre youtube y busca videos de monster hunter'),\n"
            "NO abras la página principal vacía: genera UN SOLO PASO con intent 'SEARCH_CONTENT'.\n\n"
            "REGLA DE BÚSQUEDA Y REPRODUCCIÓN EN YOUTUBE / SPOTIFY / WEB:\n"
            "Si el usuario pide buscar y reproducir un video o música (ej: 'busca videos de warframe y reproduce el primer video', 'reproduce musica de queen en youtube'):\n"
            "Genera UN SOLO PASO con intent 'SEARCH_CONTENT' hacia el servicio correspondiente y NO agregues un paso 'MEDIA_CONTROL'.\n\n"
            "REGLA CRÍTICA DE PRESERVACIÓN DE MARCAS Y NOMBRES COMPUESTOS:\n"
            "NUNCA elimines ni acortes palabras que forman parte del nombre de una marca o plataforma (ejemplos: 'solo todo', 'solotodo', 'solo leveling', 'pc factory', 'mercado libre').\n\n"
            "REGLAS STRICTAS DE INTENT:\n"
            "- 'WINDOW_CONTROL' (para mover, ajustar o posicionar ventanas en la pantalla: 'left', 'right', 'top', 'bottom', 'top_left', 'top_right', 'bottom_left', 'bottom_right', 'center', 'maximize', 'minimize', 'restore', o gestionar pestañas: 'next_tab', 'prev_tab', 'new_tab', 'close_tab', 'reopen_tab')\n"
            "- 'HARDWARE_STATUS' (para consultar temperaturas de CPU/GPU, uso de RAM, disco o estado del sistema)\n"
            "- 'SPOTIFY_NOW_PLAYING' (para preguntar qué canción está sonando o qué música suena)\n"
            "- 'SPOTIFY_LIKE' (para guardar la canción actual en favoritos o darle like)\n"
            "- 'SPOTIFY_QUEUE' (para añadir canciones a la cola de Spotify)\n"
            "- 'SET_APP_VOLUME' (para ajustar volumen porcentual de una app como Spotify, Discord o volumen general)\n"
            "- 'MUTE_APP' (para silenciar o mutear una app específica como Discord, juego o navegador)\n"
            "- 'DISCORD_CONNECT_VOICE' (para conectarse o entrar a un canal de voz de Discord)\n"
            "- 'DISCORD_DISCONNECT_VOICE' (para desconectarse o salir del canal de voz de Discord)\n"
            "- 'VALORANT_STORE' (para consultar las skins u ofertas de la tienda de Valorant)\n"
            "- 'VALORANT_LOCK' (para seleccionar o bloquear agentes en Valorant)\n"
            "- 'LOL_ACCEPT' / 'LOL_DECLINE' / 'LOL_START_QUEUE' / 'LOL_CANCEL_QUEUE' / 'LOL_STATUS' / 'LOL_PICK' / 'LOL_BAN' (para League of Legends)\n"
            "- 'OBS_START_RECORD' / 'OBS_STOP_RECORD' / 'OBS_RECORD' / 'OBS_REPLAY' (para control de OBS Studio)\n"
            "- 'OBSIDIAN_NOTE' / 'OBSIDIAN_TODO' (para anotar en el diario o agregar tareas en Obsidian)\n"
            "- 'INTERACT_SCREEN' (para abrir el primer enlace o reproducir el primer video/resultado en pantalla)\n"
            "- 'MEDIA_CONTROL' (para pausar, reanudar/play, siguiente pista, pista anterior, silenciar, subir/bajar volumen)\n"
            "- 'SEARCH_CONTENT' (para buscar videos, música o información en YouTube, Google, Spotify o internet)\n"
            "- 'OPEN_APP' (para abrir programas locales, páginas web o accesos directos, permitiendo 'parameters.position' para ubicarlos en la pantalla)\n"
            "- 'CREATE_PROJECT' (para crear o iniciar nuevos proyectos de código)\n"
            "- 'CREATE_FILE' (para crear archivos en una ruta o proyecto activo)\n"
            "- 'WRITE_TEXT' (para redactar notas o dictados en archivos de texto .txt o prompt a agentes)\n"
            "- 'SYSTEM_CONTROL' (para apagar, reiniciar o comandos del SO)\n"
            "- 'FORGET_COMMAND' (para olvidar o borrar un comando aprendido)\n"
            "- 'UNKNOWN' (si la instrucción no es clara o no coincide con nada)\n\n"
            "REGLAS DE PARÁMETRO 'position' EN 'OPEN_APP' Y 'WINDOW_CONTROL':\n"
            "- 'left': mitad izquierda de la pantalla\n"
            "- 'right': mitad derecha de la pantalla\n"
            "- 'top': mitad superior de la pantalla\n"
            "- 'bottom': mitad inferior de la pantalla\n"
            "- 'top_left', 'top_right', 'bottom_left', 'bottom_right': cuadrantes de pantalla\n"
            "- 'center': centrar ventana en pantalla\n"
            "- 'maximize': maximizar / pantalla completa\n"
            "- 'minimize': minimizar / ocultar\n"
            "- 'restore': restaurar tamaño\n\n"
            "Formato JSON Estricto Requerido:\n"
            "{\n"
            '  "steps": [\n'
            '    {\n'
            '      "intent": "OPEN_APP",\n'
            '      "target": "youtube",\n'
            '      "parameters": {\n'
            '        "position": "left"\n'
            '      }\n'
            '    },\n'
            '    {\n'
            '      "intent": "OPEN_APP",\n'
            '      "target": "antigravity",\n'
            '      "parameters": {\n'
            '        "position": "right"\n'
            '      }\n'
            '    }\n'
            '  ],\n'
            '  "confidence": 1.0\n'
            "}\n\n"
            "EJEMPLOS OBLIGATORIOS:\n"
            "1. 'abre a la izquierda de mi pantalla youtube y a la derecha antigravity':\n"
            '   {"steps": [{"intent": "OPEN_APP", "target": "youtube", "parameters": {"position": "left"}}, {"intent": "OPEN_APP", "target": "antigravity", "parameters": {"position": "right"}}], "confidence": 1.0}\n'
            "2. 'abre youtube a la izquierda de mi pantalla':\n"
            '   {"steps": [{"intent": "OPEN_APP", "target": "youtube", "parameters": {"position": "left"}}], "confidence": 1.0}\n'
            "3. 'mueve la ventana actual a la derecha':\n"
            '   {"steps": [{"intent": "WINDOW_CONTROL", "target": "active", "parameters": {"position": "right"}}], "confidence": 1.0}\n'
            "4. 'maximiza spotify':\n"
            '   {"steps": [{"intent": "WINDOW_CONTROL", "target": "spotify", "parameters": {"position": "maximize"}}], "confidence": 1.0}\n'
            "5. 'siguiente pestana':\n"
            '   {"steps": [{"intent": "WINDOW_CONTROL", "target": "next_tab", "parameters": {}}], "confidence": 1.0}\n'
            "6. 'cierra la pestana':\n"
            '   {"steps": [{"intent": "WINDOW_CONTROL", "target": "close_tab", "parameters": {}}], "confidence": 1.0}\n'
            "7. 'abre spotify y pon el volumen al 50':\n"
            '   {"steps": [{"intent": "OPEN_APP", "target": "spotify", "parameters": {}}, {"intent": "SET_APP_VOLUME", "target": "master", "parameters": {"content": "50"}}], "confidence": 1.0}\n'
            "8. 'busca videos de warframe y reproduce el primer video':\n"
            '   {"steps": [{"intent": "SEARCH_CONTENT", "target": "youtube", "parameters": {"content": "warframe"}}], "confidence": 1.0}\n'
            "9. 'pausa la musica de spotify':\n"
            '   {"steps": [{"intent": "MEDIA_CONTROL", "target": "pause", "parameters": {}}], "confidence": 1.0}\n'
            "10. 'abre antigravity y pon el siguiente prompt escribe hola mundo':\n"
            '   {"steps": [{"intent": "OPEN_APP", "target": "antigravity", "parameters": {}}, {"intent": "WRITE_TEXT", "target": "antigravity", "parameters": {"content": "hola mundo"}}], "confidence": 1.0}\n'
            "Responde ÚNICAMENTE con el objeto JSON."
        )

    def _fast_prompt_check(self, text: str) -> ParsedPipeline | None:
        """Detección ultra-rápida y determinista de comandos para escribir prompts en agentes/IDEs."""
        clean = text.strip()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye banshee)[,\s]*", "", clean, flags=re.IGNORECASE).strip()

        verbs = r"(?:dile|dilo|dila|di|pide|pidele|pidale|preguntale|pregunta|consultale|consulta|mandale|manda|enviale|envia)"
        apps = r"(?:antigravity|anti[\s\-]?gravity|cursor|claude|codex|opencode|windsurf|vscode|vs code|agente|el\s+agente|agente\s+de\s+c[oó]digo|el\s+agente\s+de\s+c[oó]digo|editor|el\s+editor|editor\s+de\s+c[oó]digo|el\s+editor\s+de\s+c[oó]digo|ide)"

        def _resolve_target(raw: str) -> str:
            r = raw.lower().strip()
            if any(k in r for k in ["anti", "agente", "editor", "ide", "chat"]):
                return "antigravity"
            if "vs" in r or "code" in r:
                return "vscode"
            return r

        # 1. abre <app> y dile/ponle/escribe [prompt] <texto> (ej: 'abre Antigravity y dile hola mundo')
        m1 = re.search(
            rf"^(?:abre|abrir|inicia|ejecuta)\s+({apps})\s+y\s+(?:pon|ponle|escribe|escribele|dile|dilo|envia|enviar|redacta|mandale|manda)(?:\s+(?:a|al)\s+|\s+)?(?:(?:el\s+)?(?:siguiente\s+)?(?:prompt|mensaje|texto)[:,\s\.]*|[:,\s\.]*)(?:escribe\s+)?(?:que\s+)?(.+)$",
            clean,
            flags=re.IGNORECASE
        )
        if m1:
            app_target = _resolve_target(m1.group(1))
            prompt_content = m1.group(2).strip().rstrip(".")
            return ParsedPipeline(
                raw_text=text,
                steps=[
                    ActionStep(intent="OPEN_APP", target=app_target, parameters=StepParameters()),
                    ActionStep(intent="WRITE_TEXT", target=app_target, parameters=StepParameters(content=prompt_content))
                ],
                confidence=1.0
            )

        # 2. pon/escribe/envía [el prompt] [al agente / al editor]: <texto>
        m2 = re.search(
            rf"^(?:pon|escribe|envia|enviar|dicta|redacta|manda)\s+(?:el\s+)?(?:siguiente\s+)?(?:prompt|mensaje)?(?:\s+(?:a|al|en)\s+(?:el\s+)?({apps}))?[:,\s\.]+(?:escribe\s+)?(?:que\s+)?(.+)$",
            clean,
            flags=re.IGNORECASE
        )
        if m2:
            raw_tgt = m2.group(1) or "antigravity"
            app_target = _resolve_target(raw_tgt)
            prompt_content = m2.group(2).strip().rstrip(".")
            return ParsedPipeline(
                raw_text=text,
                steps=[
                    ActionStep(intent="WRITE_TEXT", target=app_target, parameters=StepParameters(content=prompt_content))
                ],
                confidence=1.0
            )

        # 3. escribe en <app/chat> <texto>
        m3 = re.search(rf"^(?:escribe|pon|envia|redacta|manda)\s+en\s+({apps})[:,\s\.]+(?:escribe\s+)?(.+)$", clean, flags=re.IGNORECASE)
        if m3:
            target_app = _resolve_target(m3.group(1))
            prompt_content = m3.group(2).strip().rstrip(".")
            return ParsedPipeline(
                raw_text=text,
                steps=[
                    ActionStep(intent="WRITE_TEXT", target=target_app, parameters=StepParameters(content=prompt_content))
                ],
                confidence=1.0
            )

        # 4. dile / dilo / pide / pidele / preguntale a <app/agente> [que] <mensaje> (ej: 'dile a Antigravity hola. Esto es una prueba.')
        m4 = re.search(rf"^{verbs}\s+(?:(?:a|al|en)\s+)?({apps})[:,\s\.]+(?:que\s+)?(.+)$", clean, flags=re.IGNORECASE)
        if m4:
            target_app = _resolve_target(m4.group(1))
            prompt_content = m4.group(2).strip().rstrip(".")
            return ParsedPipeline(
                raw_text=text,
                steps=[
                    ActionStep(intent="OPEN_APP", target=target_app, parameters=StepParameters()),
                    ActionStep(intent="WRITE_TEXT", target=target_app, parameters=StepParameters(content=prompt_content))
                ],
                confidence=1.0
            )

        # 5. [en] <app> dile/pon/escribe/manda <texto> (ej: 'antigravity escribe hola mundo')
        m5 = re.search(rf"^(?:en\s+)?({apps})\s+(?:dile|dilo|pon|escribe|envia|manda)[:,\s\.]+(?:que\s+)?(.+)$", clean, flags=re.IGNORECASE)
        if m5:
            target_app = _resolve_target(m5.group(1))
            prompt_content = m5.group(2).strip().rstrip(".")
            return ParsedPipeline(
                raw_text=text,
                steps=[
                    ActionStep(intent="OPEN_APP", target=target_app, parameters=StepParameters()),
                    ActionStep(intent="WRITE_TEXT", target=target_app, parameters=StepParameters(content=prompt_content))
                ],
                confidence=1.0
            )

        return None

    def _fast_editor_status_check(self, text: str) -> ActionStep | None:
        """Detección ultra-rápida de consultas de conexión y estado de editores de código."""
        clean = text.strip().lower()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye banshee)[,\s]*", "", clean).strip().rstrip("?.!")

        editor_terms = r"(?:editor(?:es)?(?:\s+de\s+c[oó]digo)?|ide|vscode|antigravity)"
        prep = r"(?:\s+(?:a|al|con|de|del)(?:\s+(?:el|la|los|las))?)?"
        patterns = [
            rf"^(?:con[eé]ctate|conectar|conecta){prep}\s+{editor_terms}$",
            rf"^(?:revisa|ver|comprueba|chequea|consultar?)\s+(?:la\s+)?(?:conexi[oó]n|estado){prep}\s+{editor_terms}$",
            rf"^(?:estado\s+del?\s+{editor_terms}|{editor_terms}\s+conectados?)$",
            rf"^(?:hay\s+alg[uú]n\s+{editor_terms}\s+conectado)$"
        ]
        for p in patterns:
            if re.search(p, clean):
                return ActionStep(intent="EDITOR_STATUS", target="editor", parameters=StepParameters())
        return None

    def _fast_media_check(self, text: str) -> ActionStep | None:
        """Detección ultra-rápida y determinista de comandos multimedia (play, pause, next, volume, mute)."""
        clean = text.strip()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye vanshee)[,\s]*", "", clean, flags=re.IGNORECASE).strip()
        clean_lower = clean.lower().rstrip(".")

        # Normalización simple de caracteres acentuados
        norm = (
            clean_lower
            .replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        )

        # 1. Pausa / Detener
        if re.search(r"^(?:pon\s+)?(?:pausa|pausar|pausala|deten|detener|para|parar|stop)(?:\s+(?:la|el)\s+(?:musica|cancion|reproduccion|video|reproductor|spotify|youtube))?(?:\s+(?:en|de)\s+(?:spotify|youtube))?$", norm):
            return ActionStep(intent="MEDIA_CONTROL", target="pause", parameters=StepParameters())

        # 2. Reanudar / Play / Continuar
        if re.search(r"^(?:reanuda|reanudar|reproduce|reproducir|continua|continuar|play|dale\s+play)(?:\s+(?:la|el)\s+(?:musica|cancion|reproduccion|video|reproductor|spotify|youtube))?(?:\s+(?:en|de)\s+(?:spotify|youtube))?$", norm):
            return ActionStep(intent="MEDIA_CONTROL", target="play", parameters=StepParameters())

        # 3. Siguiente canción / pista
        if re.search(r"^(?:siguiente|pasa|pasar|salta|saltar|avanza|avanzar|next)(?:\s+(?:de\s+)?(?:(?:la|el)\s+)?(?:cancion|pista|tema|video|musica))?(?:\s+(?:en|de)\s+(?:spotify|youtube))?$", norm) or norm in ["cancion siguiente", "tema siguiente", "pista siguiente", "siguiente cancion"]:
            return ActionStep(intent="MEDIA_CONTROL", target="next", parameters=StepParameters())

        # 4. Canción anterior / retroceder
        if re.search(r"^(?:anterior|vuelve|volver|retrocede|retroceder|prev|previous)(?:\s+(?:a\s+)?(?:(?:la|el)\s+)?(?:cancion|pista|tema|video|musica))?(?:\s+(?:en|de)\s+(?:spotify|youtube))?$", norm) or norm in ["cancion anterior", "tema anterior", "pista anterior", "anterior cancion"]:
            return ActionStep(intent="MEDIA_CONTROL", target="previous", parameters=StepParameters())

        # 5. Silenciar / Mute
        if re.search(r"^(?:silencia|silenciar|mute|mutear|desmutear|quita\s+el\s+sonido|sin\s+sonido)(?:\s+(?:el\s+audio|el\s+volumen|el\s+sistema|la\s+musica))?$", norm):
            return ActionStep(intent="MEDIA_CONTROL", target="mute", parameters=StepParameters())

        # 6. Subir volumen
        if re.search(r"^(?:sube|subir|aumenta|aumentar|mas)\s+(?:el\s+)?volumen$", norm) or norm in ["subir volumen", "sube volumen", "mas volumen"]:
            return ActionStep(intent="MEDIA_CONTROL", target="volume_up", parameters=StepParameters())

        # 7. Bajar volumen
        if re.search(r"^(?:baja|bajar|disminuye|disminuir|menos)\s+(?:el\s+)?volumen$", norm) or norm in ["bajar volumen", "baja volumen", "menos volumen"]:
            return ActionStep(intent="MEDIA_CONTROL", target="volume_down", parameters=StepParameters())

        return None

    def _fast_search_check(self, text: str) -> ActionStep | None:
        """Detección ultra-rápida y determinista de comandos de búsqueda comunes."""
        clean = text.strip()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye vanshee)[,\s]*", "", clean, flags=re.IGNORECASE).strip()

        ignored_search_terms = {"pausa", "pausar", "silencio", "mute", "reproduce", "reproducir", "siguiente", "anterior", "volumen", "musica", "música", "cancion", "canción", "video"}

        # -1. pon/por/reproduce [cancion/musica de] <artista/cancion> (en spotify/youtube)
        m_music = re.search(r"^(?:por\s+favor\s+)?(?:pon|por|coloca|reproduce|reproducir|toca|tocar|escuchar)\s+(?:una\s+|un\s+|la\s+|el\s+)?(?:cancion|canción|musica|música|video|tema|pista)?\s*(?:de\s+)?(.+?)(?:\s+en\s+(spotify|youtube))?\.?$", clean, flags=re.IGNORECASE)
        if m_music:
            raw_target = m_music.group(1).strip()
            dest_srv = m_music.group(2) or "spotify"
            qry = clean_search_term(raw_target)
            if qry and qry.lower() not in ignored_search_terms:
                return ActionStep(intent="SEARCH_CONTENT", target=dest_srv.lower(), parameters=StepParameters(content=qry))

        # 0. busca <query> y reproduce (el primer video)
        m0 = re.search(r"^(?:busca|buscar|encuentra|pon|reproduce)\s+(.+?)\s+y\s+(?:reproduce|reproducir|pon|ponlo|dale\s+play)(?:\s+(?:el\s+)?(?:primer\s+)?(?:video|cancion|tema))?\.?$", clean, flags=re.IGNORECASE)
        if m0:
            raw_target = m0.group(1).strip()
            target_srv = "youtube"
            for srv in ["youtube", "spotify", "google", "brave", "chrome"]:
                if srv in raw_target.lower():
                    target_srv = srv
                    break
            qry = clean_search_term(raw_target)
            if qry and qry.lower() not in ignored_search_terms:
                return ActionStep(intent="SEARCH_CONTENT", target=target_srv, parameters=StepParameters(content=qry))

        # 1. abre <servicio> y busca <query>
        m1 = re.search(r"^(?:abre|abrir|inicia|ejecuta)\s+(youtube|google|spotify|brave|chrome|el\s+navegador|el\s+buscador)\s+y\s+(?:busca|buscar|encuentra|pon)\s+(.+)$", clean, flags=re.IGNORECASE)
        if m1:
            raw_action = m1.group(2).strip()
            # Si lo que sigue es ajuste de volumen, pausa, prompt o ventana, no es búsqueda en el servicio
            if not re.search(r"^(?:el\s+)?volumen|pausa|el\s+prompt|la\s+ventana|a\s+la\s+izquierda|a\s+la\s+derecha", raw_action, flags=re.IGNORECASE):
                srv = m1.group(1).strip().lower().replace("el navegador", "google").replace("el buscador", "google")
                qry = clean_search_term(raw_action) or raw_action
                if qry:
                    return ActionStep(intent="SEARCH_CONTENT", target=srv, parameters=StepParameters(content=qry))

        # 2. busca <query> en <servicio> [y abre el primer link/resultado]
        m2 = re.search(r"^(?:busca|buscar|encuentra|pon|reproduce)\s+(.+?)\s+en\s+(youtube|google|spotify|brave|chrome|el\s+navegador|el\s+buscador|la\s+web|internet)(?:\s+(?:y\s+)?(?:abre|entra|ingresa|ve)(?:\s+(?:a|al|en))?\s+(?:el\s+)?(?:primer\s+|1er\s+)?(?:link|enlace|resultado|pagina|página|sitio))?\.?$", clean, flags=re.IGNORECASE)
        if m2:
            srv = m2.group(2).strip().lower().replace("el navegador", "google").replace("el buscador", "google").replace("la web", "google").replace("internet", "google")
            qry = clean_search_term(m2.group(1).strip())
            if qry and qry.lower() not in ignored_search_terms:
                return ActionStep(intent="SEARCH_CONTENT", target=srv, parameters=StepParameters(content=qry))

        # 3. busca en <servicio> <query>
        m3 = re.search(r"^(?:busca|buscar|encuentra|pon|reproduce)\s+en\s+(youtube|google|spotify|brave|chrome|el\s+navegador|el\s+buscador|la\s+web|internet)\s+(.+)$", clean, flags=re.IGNORECASE)
        if m3:
            srv = m3.group(1).strip().lower().replace("el navegador", "google").replace("el buscador", "google").replace("la web", "google").replace("internet", "google")
            qry = clean_search_term(m3.group(2).strip())
            if qry and qry.lower() not in ignored_search_terms:
                return ActionStep(intent="SEARCH_CONTENT", target=srv, parameters=StepParameters(content=qry))

        # 4. busca <query> [general] (ej: 'busca solo todo', 'busca precios de computadores')
        m4 = re.search(r"^(?:busca|buscar|encuentra)\s+(.+)$", clean, flags=re.IGNORECASE)
        if m4:
            qry = clean_search_term(m4.group(1).strip())
            if qry and qry.lower() not in ignored_search_terms:
                return ActionStep(intent="SEARCH_CONTENT", target="google", parameters=StepParameters(content=qry))

        return None

    def _fast_relative_action_check(self, text: str) -> ActionStep | None:
        """Detección ultra-rápida y determinista de comandos relativos de pantalla (reproduce la primera canción, abre el primer link)."""
        clean = text.strip()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye banshee)[,\s]*", "", clean, flags=re.IGNORECASE).strip()
        norm = clean.lower().rstrip(".").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")

        # 1. Reproducir primer video o canción
        if re.search(r"^(?:(?:reproduce|reproducir|pon|ponle|dale\s+play\s+a|escuchar|toca|tocar)\s+)?(?:el\s+|la\s+|al\s+)?(?:primer|primera|1er|1ra)\s+(?:video|cancion|tema|pista|resultado)(?:\s+(?:de\s+)?(?:la\s+lista|pantalla|youtube|spotify))?$", norm):
            return ActionStep(intent="INTERACT_SCREEN", target="play_first", parameters=StepParameters(content="play_first"))

        # 2. Abrir primer link o resultado de búsqueda
        if re.search(r"^(?:(?:abre|abrir|entra|entrar|ingresa|ingresar|navega|navegar|ve|ir|haz\s+clic\s+en|clic\s+en)\s+)?(?:el\s+|la\s+|al\s+|a\s+la\s+)?(?:primer|primera|1er|1ra)\s+(?:link|enlace|resultado|pagina|sitio|opcion)(?:\s+(?:de\s+)?(?:la\s+lista|pantalla|google|busqueda|navegador))?$", norm):
            return ActionStep(intent="INTERACT_SCREEN", target="open_first_link", parameters=StepParameters(content="open_first_link"))

        return None

    def _fast_integration_check(self, text: str) -> ActionStep | None:
        """Detección ultra-rápida y determinista de comandos para integraciones directas (Spotify, Valorant, OBS, Mixer, Hardware, Obsidian)."""
        clean = text.strip()
        clean = re.sub(r"^[¿¡\s]+", "", clean).strip()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye banshee)[,\s]*", "", clean, flags=re.IGNORECASE).strip()
        norm = clean.lower().strip("¿?¡!.,;: \t").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")

        # 1. Spotify Now Playing / ¿Qué canción suena?
        if any(w in norm for w in ["que cancion esta sonando", "que cancion suena", "que tema suena", "que cancion es esta", "cancion actual", "que suena en spotify", "que suena"]):
            return ActionStep(intent="SPOTIFY_NOW_PLAYING", target="spotify", parameters=StepParameters())

        # 2. Spotify Like / Favoritos
        if re.search(r"^(?:guarda|guardar|agrega|agregar|añade|añadir)\s+(?:esta\s+)?cancion\s+(?:en|a)\s+(?:favoritos|mis\s+me\s+gusta|canciones\s+que\s+te\s+gustan)$", norm) or norm in ["me gusta esta cancion", "dale like", "like a la cancion"]:
            return ActionStep(intent="SPOTIFY_LIKE", target="spotify", parameters=StepParameters())

        # 3. Spotify Cola
        m_queue = re.search(r"^(?:agrega|agregar|añade|añadir|pon|poner)\s+(.+?)\s+a\s+la\s+cola(?:\s+de\s+spotify)?$", norm)
        if m_queue:
            q = m_queue.group(1).strip()
            return ActionStep(intent="SPOTIFY_QUEUE", target="spotify", parameters=StepParameters(content=q))

        # 3.5. Spotify Playback directo
        m_play_spotify = re.search(r"^(?:pon|reproduce|toca|escuchar|reproducir)\s+(?:una\s+cancion\s+de\s+|la\s+cancion\s+de\s+|musica\s+de\s+|canciones\s+de\s+|un\s+tema\s+de\s+|a\s+)?(.+?)(?:\s+en\s+spotify)?$", norm)
        if m_play_spotify and not any(w in norm for w in ["youtube", "video", "obs", "obsidian", "valorant", "lol", "league", "volumen", "pantalla", "ventana", "completa", "pestana", "pestaña"]):
            query_music = m_play_spotify.group(1).strip()
            query_music = re.sub(r"^(?:de|el|la|los|las|un|una)\s+", "", query_music).strip()
            if query_music and query_music not in ["musica", "cancion", "play"]:
                return ActionStep(intent="SEARCH_CONTENT", target="spotify", parameters=StepParameters(content=query_music))

        # 4. Mezclador de Audio de Windows: Volumen porcentual por app o maestro
        m_vol_app = re.search(r"^(?:pon|ajusta|cambia|coloca|setea)\s+(?:el\s+)?volumen\s+(?:de\s+)?([a-zA-Z0-9_\-\s]+?)\s+al\s+(\d{1,3})\s*%?$", norm)
        if m_vol_app:
            target_app = m_vol_app.group(1).strip()
            vol_pct = int(m_vol_app.group(2).strip())
            return ActionStep(intent="SET_APP_VOLUME", target=target_app, parameters=StepParameters(content=str(vol_pct)))

        m_vol_gen = re.search(r"^(?:pon|ajusta|cambia|coloca|setea)\s+(?:el\s+)?volumen(?:\s+general|\s+maestro|\s+de\s+windows)?\s+al\s+(\d{1,3})\s*%?$", norm)
        if m_vol_gen:
            vol_pct = int(m_vol_gen.group(1).strip())
            return ActionStep(intent="SET_APP_VOLUME", target="master", parameters=StepParameters(content=str(vol_pct)))

        # 5. Silenciar / Desmutear app
        m_mute = re.search(r"^(?:silencia|silenciar|mutea|mutear)\s+(?:el\s+audio\s+de\s+|a\s+|la\s+app\s+de\s+)?([a-zA-Z0-9_\-\s]+)$", norm)
        if m_mute and m_mute.group(1).strip() not in ["el audio", "el volumen", "el sistema", "la musica"]:
            return ActionStep(intent="MUTE_APP", target=m_mute.group(1).strip(), parameters=StepParameters())

        m_unmute = re.search(r"^(?:desmutea|desmutear|reactiva\s+el\s+audio\s+de)\s+([a-zA-Z0-9_\-\s]+)$", norm)
        if m_unmute:
            return ActionStep(intent="UNMUTE_APP", target=m_unmute.group(1).strip(), parameters=StepParameters())

        # 5.5. Discord: Canales de Voz
        if "discord" in norm or any(w in norm for w in ["canal de voz", "servidor de voz", "sala de voz", "la llamada", "el canal"]):
            # Desconectar / Salir del canal de voz
            if any(w in norm for w in ["desconecta", "desconectar", "desconectate", "desconectame", "sal", "salir", "salte", "corta", "cortar", "cuelga", "colgar", "deja", "dejar", "abandona", "abandonar"]):
                return ActionStep(intent="DISCORD_DISCONNECT_VOICE", target="discord", parameters=StepParameters())

            # Conectar / Unirse a canal de voz
            m_disc = re.search(r"^(?:conectame|conectar|conectate|entra|entrar|metete|meter|unete|unirme|ir)(?:\s+(?:al|a\s+la|a|en))?(?:\s+(?:un|el|la|los|las))?(?:\s+(?:canal\s+de\s+voz|canal|servidor\s+de\s+voz|servidor|sala\s+de\s+voz|sala))?(?:\s+(?:llamado|llamada|de))?\s*(.*?)(?:\s+en\s+discord|\s+de\s+discord)?$", norm)
            if m_disc:
                ch = m_disc.group(1).strip()
                ch = re.sub(r"^(?:de|el|la|los|las|un|una|canal|canal de voz|sala|servidor)\s+", "", ch).strip()
                ch = re.sub(r"\s+(?:en|de)\s+discord$", "", ch).strip()
                if not ch or ch in ["discord", "voz", "un canal", "el canal", "canal de voz", "un canal de voz", "el canal de voz", "la llamada", "en discord"]:
                    ch = "general"
                return ActionStep(intent="DISCORD_CONNECT_VOICE", target="discord", parameters=StepParameters(content=ch))
            elif any(w in norm for w in ["canal de voz", "conectame", "conectar", "conectate", "entra", "unete"]):
                return ActionStep(intent="DISCORD_CONNECT_VOICE", target="discord", parameters=StepParameters(content="general"))

        # 6. Valorant: Tienda Diaria
        if re.search(r"^(?:que\s+hay\s+en\s+mi\s+tienda\s+de\s+valorant|tienda\s+de\s+valorant|mira\s+mi\s+tienda\s+de\s+valorant|ofertas\s+de\s+valorant)$", norm):
            return ActionStep(intent="VALORANT_STORE", target="valorant", parameters=StepParameters())

        # 7. Selección / Auto-Lock de Agentes (Valorant) y Campeones (League of Legends)
        VALORANT_AGENTS = {
            "jett", "reyna", "raze", "omen", "sova", "sage", "phoenix", "viper", "cypher",
            "brimstone", "killjoy", "skye", "yoru", "astra", "kayo", "kay/o", "chamber",
            "neon", "fade", "harbor", "gekko", "deadlock", "iso", "clove", "vyse", "tejo"
        }

        # Baneo en League of Legends
        m_ban = re.search(r"^(?:banea|banear|baneame|bloquea\s+el\s+ban\s+de)\s+(?:a\s+|al\s+campeon\s+|a\s+la\s+campeona\s+)?([a-zA-Z0-9_\'\s]+?)(?:\s+en\s+(?:el\s+)?(?:lol|league\s+of\s+legends))?$", norm)
        if m_ban:
            champ_ban = m_ban.group(1).strip()
            champ_ban = re.sub(r"^(?:al\s+campeon|a\s+la\s+campeona|al\s+personaje|a|el|la)\s+", "", champ_ban).strip()
            return ActionStep(intent="LOL_BAN", target="lol", parameters=StepParameters(content=champ_ban))

        # Pick / Lock de personajes
        m_pick = re.search(r"^(?:selecciona|seleccionar|bloquea|bloquear|auto\s*lock|lockea|lockear|escoge|escoger|elige|elegir|pickea|pickear)\s+(?:a\s+|al\s+campeon\s+|a\s+la\s+campeona\s+|al\s+personaje\s+|al\s+agente\s+)?([a-zA-Z0-9_\'\s]+?)(?:\s+en\s+(?:el\s+)?(?:lol|league\s+of\s+legends|valorant))?$", norm)
        if m_pick:
            character = m_pick.group(1).strip()
            character = re.sub(r"^(?:al\s+campeon|a\s+la\s+campeona|al\s+personaje|al\s+agente|a|el|la)\s+", "", character).strip()

            if "valorant" in norm or (character in VALORANT_AGENTS and not any(w in norm for w in ["lol", "league", "campeon", "campeona"])):
                return ActionStep(intent="VALORANT_LOCK", target="valorant", parameters=StepParameters(content=character))
            else:
                return ActionStep(intent="LOL_PICK", target="lol", parameters=StepParameters(content=character))

        # 7.5. League of Legends (LCU API): Aceptar, rechazar partidas y gestión de cola
        is_lol_context = any(w in norm for w in ["lol", "league of legends", "league", "de lol", "del lol", "diana", "yasuo", "ahri", "zed"]) or (
            any(w in norm for w in ["partida", "cola", "ready check", "champ select", "campeon", "campeona"]) and not any(w in norm for w in ["musica", "cancion", "video", "youtube", "spotify", "valorant", "obs"])
        )

        if is_lol_context:
            # 1. Cancelar cola / Salir de la cola (prioridad si menciona cola/búsqueda)
            if any(w in norm for w in ["cola", "busqueda", "emparejamiento", "matchmaking", "queue"]):
                if any(w in norm for w in ["cancela", "cancelar", "sal", "salir", "quitar", "quita", "para", "parar", "frena", "frenar", "deja", "dejar", "rechaza", "rechazar"]):
                    return ActionStep(intent="LOL_CANCEL_QUEUE", target="lol", parameters=StepParameters())
                if any(w in norm for w in ["busca", "buscar", "inicia", "iniciar", "entra", "entrar", "pon", "poner", "juega", "jugar"]):
                    return ActionStep(intent="LOL_START_QUEUE", target="lol", parameters=StepParameters())

            # 2. Aceptar partida
            if any(w in norm for w in ["acepta", "aceptar", "dale a aceptar", "confirma", "confirmar", "dale aceptar"]):
                return ActionStep(intent="LOL_ACCEPT", target="lol", parameters=StepParameters())

            # 3. Rechazar partida
            if any(w in norm for w in ["rechaza", "rechazar", "declina", "declinar", "no aceptar", "rechazala", "rechazalas"]):
                return ActionStep(intent="LOL_DECLINE", target="lol", parameters=StepParameters())

            # 4. Iniciar cola general / Buscar partida
            if any(w in norm for w in ["busca", "buscar", "inicia", "iniciar", "entra", "entrar", "pon", "poner", "juega", "jugar"]):
                if any(w in norm for w in ["partida", "match", "juego"]):
                    return ActionStep(intent="LOL_START_QUEUE", target="lol", parameters=StepParameters())

            # 5. Estado del juego
            if any(w in norm for w in ["como va", "fase", "estado", "fase actual", "status"]):
                return ActionStep(intent="LOL_STATUS", target="lol", parameters=StepParameters())

        # 8. OBS Studio: Grabación y Replay Buffer
        if re.search(r"^(?:inicia|empezar|iniciar)\s+(?:la\s+)?grabacion\s+en\s+obs$", norm):
            return ActionStep(intent="OBS_START_RECORD", target="obs", parameters=StepParameters())
        if re.search(r"^(?:deten|detener|para|parar|termina|terminar|finaliza|finalizar)\s+(?:la\s+)?grabacion\s+en\s+obs$", norm):
            return ActionStep(intent="OBS_STOP_RECORD", target="obs", parameters=StepParameters())
        if re.search(r"^(?:graba|grabar|toggle\s+grabacion)\s+en\s+obs$", norm) or norm in ["grabar en obs", "graba en obs"]:
            return ActionStep(intent="OBS_RECORD", target="obs", parameters=StepParameters())
        if re.search(r"^(?:guarda|guardar|salva|salvar)\s+(?:el\s+)?(?:clip|repeticion|replay)(?:\s+en\s+obs)?$", norm):
            return ActionStep(intent="OBS_REPLAY", target="obs", parameters=StepParameters())

        # 9. Hardware y Diagnóstico (Ultra-resiliente a cualquier mención de temperatura, hardware o rendimiento)
        if any(w in norm for w in ["temperatura", "temperaturas", "hardware", "rendimiento", "memoria ram", "uso de ram", "uso de cpu", "uso de procesador", "como esta el pc", "como va el pc", "estado del sistema", "diagnostico del sistema", "recursos del sistema", "diagnostico"]):
            return ActionStep(intent="HARDWARE_STATUS", target="system", parameters=StepParameters())

        # 10. Obsidian: Diario y Tareas
        m_obs_note = re.search(r"^(?:anota|escribe|guarda)\s+en\s+(?:mi\s+diario|obsidian)[:,\s\.]+(.+)$", clean, flags=re.IGNORECASE)
        if m_obs_note:
            note_txt = m_obs_note.group(1).strip()
            return ActionStep(intent="OBSIDIAN_NOTE", target="obsidian", parameters=StepParameters(content=note_txt))

        m_obs_todo = re.search(r"^(?:añade|agrega|crea)\s+(?:una\s+)?tarea(?:\s+en\s+obsidian)?[:,\s\.]+(.+)$", clean, flags=re.IGNORECASE)
        if m_obs_todo:
            todo_txt = m_obs_todo.group(1).strip()
            return ActionStep(intent="OBSIDIAN_TODO", target="obsidian", parameters=StepParameters(content=todo_txt))

        # 11. Git: Estado, Commits automáticos, Push, Pull, Diff, Ramas
        # 11.1. Git Commit con mensaje explícito
        m_git_msg = re.search(
            r"^(?:haz|hacer|crea|crear|genera|generar)\s+(?:un\s+)?commit\s+(?:con\s+el\s+mensaje|diciendo|con\s+mensaje|con\s+texto|que\s+diga|titulado)[:,\s]+['\"]?(.+?)['\"]?$",
            clean,
            flags=re.IGNORECASE
        )
        if not m_git_msg:
            m_git_msg = re.search(
                r"^(?:haz|hacer|crea|crear|genera|generar)\s+(?:un\s+)?commit\s+['\"](.+?)['\"]$",
                clean,
                flags=re.IGNORECASE
            )
        if m_git_msg:
            raw_msg = m_git_msg.group(1).strip().strip("'\"")
            if raw_msg.lower() not in ["automatico", "automático", "los cambios", "de los cambios"]:
                return ActionStep(intent="GIT_COMMIT", target="git", parameters=StepParameters(content=raw_msg))

        # 11.2. Git Commit automático
        if any(norm == w for w in [
            "haz un commit", "haz commit", "crea un commit", "crear commit", 
            "commit automatico", "commit automático", "auto commit", 
            "commitea los cambios", "commitea", "commitear", 
            "guarda los cambios en git", "guardar cambios en git", "hacer commit",
            "haz un commit de los cambios", "haz commit de los cambios"
        ]):
            return ActionStep(intent="GIT_COMMIT", target="git", parameters=StepParameters())

        # 11.3. Git Status
        if re.search(r"^(?:por\s+favor\s+)?(?:estado\s+de\s+git|como\s+esta\s+git|revisa\s+git|revisar\s+git|revisa\s+el\s+estado\s+de\s+git|estado\s+del\s+repositorio|que\s+cambios\s+hay\s+en\s+git|git\s+status|status\s+de\s+git|status\s+del\s+repo)$", norm):
            return ActionStep(intent="GIT_STATUS", target="git", parameters=StepParameters())

        # 11.4. Git Push
        if re.search(r"^(?:por\s+favor\s+)?(?:sube|subir)\s+los\s+cambios(?:\s+a\s+git|\s+al\s+repositorio)?$|^(?:haz\s+)?git\s+push$|^(?:pushea|pushear)(?:\s+los\s+cambios|\s+a\s+git)?$|^(?:sube|subir)\s+al\s+repositorio$", norm):
            return ActionStep(intent="GIT_PUSH", target="git", parameters=StepParameters())

        # 11.5. Git Pull
        if re.search(r"^(?:por\s+favor\s+)?(?:trae|traer)\s+los\s+cambios(?:\s+de\s+git|\s+del\s+repositorio)?$|^(?:haz\s+)?git\s+pull$|^(?:pullea|pullear)(?:\s+los\s+cambios)?$|^(?:actualiza|actualizar)\s+el\s+repositorio$", norm):
            return ActionStep(intent="GIT_PULL", target="git", parameters=StepParameters())

        # 11.6. Git Diff
        if re.search(r"^(?:que\s+cambios\s+hice|muestra\s+el\s+diff|mostrar\s+diff|git\s+diff|diff\s+de\s+git|muestra\s+los\s+cambios(?:\s+de\s+git)?|ver\s+el\s+diff|revisa\s+los\s+cambios)$", norm):
            return ActionStep(intent="GIT_DIFF", target="git", parameters=StepParameters())

        # 11.7. Git Branch (crear, cambiar, consultar)
        m_branch_create = re.search(
            r"^(?:crea|crear|haz)\s+(?:una\s+)?rama(?:\s+(?:llamada|con\s+nombre))?\s+([a-zA-Z0-9_\-\./]+)$",
            clean,
            flags=re.IGNORECASE
        )
        if m_branch_create:
            b_name = m_branch_create.group(1).strip()
            return ActionStep(intent="GIT_BRANCH", target="create", parameters=StepParameters(content=b_name))

        m_branch_switch = re.search(
            r"^(?:cambia|cambiar|cambiate|cámbiate|pasa|pasar)\s+(?:a\s+la\s+|de\s+)?rama\s+([a-zA-Z0-9_\-\./]+)$",
            clean,
            flags=re.IGNORECASE
        )
        if m_branch_switch:
            b_name = m_branch_switch.group(1).strip()
            return ActionStep(intent="GIT_BRANCH", target="switch", parameters=StepParameters(content=b_name))

        if re.search(r"^(?:en\s+que\s+rama\s+(?:de\s+git\s+)?estoy|que\s+rama\s+tengo\s+activa|rama\s+actual\s+de\s+git|rama\s+de\s+git|git\s+branch)$", norm):
            return ActionStep(intent="GIT_BRANCH", target="current", parameters=StepParameters())

        return None

    def _fast_window_check(self, text: str) -> list[ActionStep] | ActionStep | None:
        """Detección ultra-rápida y determinista de comandos de ventanas y pestañas."""
        clean = text.strip()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye banshee)[,\s]*", "", clean, flags=re.IGNORECASE).strip()
        norm = clean.lower().strip("¿?¡!.,;: \t").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")

        def _clean_pos(pos_str: str) -> str:
            p = pos_str.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").strip()
            if any(k in p for k in ["arriba a la izquierda", "superior izquierda", "arriba izquierda"]):
                return "top_left"
            if any(k in p for k in ["arriba a la derecha", "superior derecha", "arriba derecha"]):
                return "top_right"
            if any(k in p for k in ["abajo a la izquierda", "inferior izquierda", "abajo izquierda"]):
                return "bottom_left"
            if any(k in p for k in ["abajo a la derecha", "inferior derecha", "abajo derecha"]):
                return "bottom_right"
            if "izq" in p or "izquierda" in p:
                return "left"
            if "der" in p or "derecha" in p:
                return "right"
            if "arriba" in p or "superior" in p:
                return "top"
            if "abajo" in p or "inferior" in p:
                return "bottom"
            if any(k in p for k in ["maxim", "completa", "fullscreen", "agrand", "toda la pantalla", "pantalla entera"]):
                return "maximize"
            if any(k in p for k in ["minim", "ocult"]):
                return "minimize"
            if any(k in p for k in ["centr", "medio"]):
                return "center"
            return "left"

        pos_pattern = (
            r"izquierda|derecha|mitad\s+izquierda|mitad\s+derecha|arriba|abajo|centro|al\s+centro|"
            r"arriba\s+a\s+la\s+izquierda|arriba\s+a\s+la\s+derecha|abajo\s+a\s+la\s+izquierda|abajo\s+a\s+la\s+derecha|"
            r"esquina\s+superior\s+izquierda|esquina\s+superior\s+derecha|esquina\s+inferior\s+izquierda|esquina\s+inferior\s+derecha|"
            r"superior\s+izquierda|superior\s+derecha|inferior\s+izquierda|inferior\s+derecha|"
            r"pantalla\s+completa|en\s+pantalla\s+completa|a\s+pantalla\s+completa|fullscreen|completa|toda\s+la\s+pantalla|"
            r"maximizado|maximizada|maximizar|minimizado|minimizada|minimizar"
        )

        # 0. Ordenar / Organizar ventanas en la pantalla: 'ordena las ventanas', 'organiza las ventanas en la pantalla'
        m_tile = re.search(
            r"^(?:ordena|ordenar|organiza|organizar|acomoda|acomodar|distribuye|distribuir|reorganiza|reorganizar)\s+(?:todas\s+)?(?:las\s+)?ventanas(?:\s+(?:en\s+la\s+pantalla|en\s+pantalla|abiertas))?$",
            clean,
            flags=re.IGNORECASE
        )
        if m_tile:
            return ActionStep(intent="WINDOW_CONTROL", target="tile", parameters=StepParameters(position="tile"))

        # 1. Split / Dual open: 'abre a la izquierda de mi pantalla YouTube y a la derecha AntiGravity'
        m_dual1 = re.search(
            rf"^(?:abre|abrir|inicia|ejecuta|pon|coloca)\s+(?:a\s+la\s+|en\s+la\s+|al\s+|a\s+|en\s+)?({pos_pattern})(?:\s+de\s+(?:mi\s+|la\s+)?pantalla)?\s+([a-zA-Z0-9_\-\.\s]+?)\s+y\s+(?:a\s+la\s+|en\s+la\s+|al\s+|a\s+|en\s+)?({pos_pattern})(?:\s+de\s+(?:mi\s+|la\s+)?pantalla)?\s+(?:abre\s+|inicia\s+|pon\s+)?([a-zA-Z0-9_\-\.\s]+)$",
            clean,
            flags=re.IGNORECASE
        )
        if m_dual1:
            pos1 = _clean_pos(m_dual1.group(1))
            app1 = m_dual1.group(2).strip().lower()
            pos2 = _clean_pos(m_dual1.group(3))
            app2 = m_dual1.group(4).strip().lower()
            return [
                ActionStep(intent="OPEN_APP", target=app1, parameters=StepParameters(position=pos1)),
                ActionStep(intent="OPEN_APP", target=app2, parameters=StepParameters(position=pos2))
            ]

        # 2. Split / Dual open (Apps first): 'abre YouTube a la izquierda y AntiGravity a la derecha'
        m_dual2 = re.search(
            rf"^(?:abre|abrir|inicia|ejecuta|pon|coloca)\s+([a-zA-Z0-9_\-\.\s]+?)\s+(?:a\s+la\s+|en\s+la\s+|al\s+|a\s+|en\s+)?({pos_pattern})(?:\s+de\s+(?:mi\s+|la\s+)?pantalla)?\s+y\s+(?:abre\s+|inicia\s+|pon\s+)?([a-zA-Z0-9_\-\.\s]+?)\s+(?:a\s+la\s+|en\s+la\s+|al\s+|a\s+|en\s+)?({pos_pattern})(?:\s+de\s+(?:mi\s+|la\s+)?pantalla)?$",
            clean,
            flags=re.IGNORECASE
        )
        if m_dual2:
            app1 = m_dual2.group(1).strip().lower()
            pos1 = _clean_pos(m_dual2.group(2))
            app2 = m_dual2.group(3).strip().lower()
            pos2 = _clean_pos(m_dual2.group(4))
            return [
                ActionStep(intent="OPEN_APP", target=app1, parameters=StepParameters(position=pos1)),
                ActionStep(intent="OPEN_APP", target=app2, parameters=StepParameters(position=pos2))
            ]

        # 3. Divide pantalla: 'divide la pantalla entre YouTube y AntiGravity'
        m_split = re.search(
            r"^(?:divide|dividir|parte|partir)\s+(?:la\s+)?pantalla(?:\s+entre|\s+con|:)?\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+a\s+la\s+izquierda)?\s+y\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+a\s+la\s+derecha)?$",
            clean,
            flags=re.IGNORECASE
        )
        if m_split:
            app1 = m_split.group(1).strip().lower()
            app2 = m_split.group(2).strip().lower()
            return [
                ActionStep(intent="OPEN_APP", target=app1, parameters=StepParameters(position="left")),
                ActionStep(intent="OPEN_APP", target=app2, parameters=StepParameters(position="right"))
            ]

        # 4. Single Open App with position: 'abre YouTube a la izquierda de mi pantalla', 'abre Spotify en pantalla completa'
        m_single1 = re.search(
            rf"^(?:abre|abrir|inicia|iniciar|ejecuta|ejecutar|lanza)\s+([a-zA-Z0-9_\-\.\s]+?)\s+(?:a\s+la\s+|en\s+la\s+|al\s+|a\s+|en\s+)?({pos_pattern})(?:\s+de\s+(?:mi\s+|la\s+)?pantalla)?$",
            clean,
            flags=re.IGNORECASE
        )
        if m_single1:
            app = m_single1.group(1).strip().lower()
            pos = _clean_pos(m_single1.group(2))
            return ActionStep(intent="OPEN_APP", target=app, parameters=StepParameters(position=pos))

        # 5. Position first, app second: 'abre a la izquierda de mi pantalla YouTube', 'abre en pantalla completa Spotify'
        m_single2 = re.search(
            rf"^(?:abre|abrir|inicia|iniciar|ejecuta|ejecutar|lanza)\s+(?:a\s+la\s+|en\s+la\s+|al\s+|a\s+|en\s+)?({pos_pattern})(?:\s+de\s+(?:mi\s+|la\s+)?pantalla)?\s+([a-zA-Z0-9_\-\.\s]+)$",
            clean,
            flags=re.IGNORECASE
        )
        if m_single2:
            pos = _clean_pos(m_single2.group(1))
            app = m_single2.group(2).strip().lower()
            return ActionStep(intent="OPEN_APP", target=app, parameters=StepParameters(position=pos))

        # 6. Mover / Acomodar ventana existente o activa: 'mueve YouTube a la derecha', 'pon Spotify en pantalla completa', 'pon la ventana en pantalla completa'
        m_move = re.search(
            rf"^(?:mueve|mover|pon|poner|coloca|colocar|ajusta|ajustar|acomoda|acomodar)\s+(?:la\s+ventana\s+de\s+|la\s+app\s+de\s+)?([a-zA-Z0-9_\-\.\s]+?)\s+(?:a\s+la\s+|en\s+la\s+|al\s+|a\s+|en\s+)?({pos_pattern})(?:\s+de\s+(?:mi\s+|la\s+)?pantalla)?$",
            clean,
            flags=re.IGNORECASE
        )
        if m_move:
            target_raw = m_move.group(1).strip().lower()
            pos = _clean_pos(m_move.group(2))
            target = "active" if target_raw in ["esta", "esta ventana", "la ventana", "la ventana actual", "ventana actual", "actual", "activa", "pantalla", "app", "a", "en", "al", "el", "la", "de"] else target_raw
            return ActionStep(intent="WINDOW_CONTROL", target=target, parameters=StepParameters(position=pos))

        # 7. Maximizar / Pantalla completa / Minimizar / Centrar
        m_max = re.search(
            r"^(?:maximiza|maximizar|agrandar|fullscreen|(?:pon|poner|coloca|colocar|haz|hacer)(?:la|lo)?\s+(?:a\s+|en\s+)?pantalla\s+completa|(?:en\s+|a\s+)?pantalla\s+completa)(?:\s+(?:de\s+|para\s+|la\s+ventana\s+de\s+|la\s+ventana\s+actual|esta\s+ventana|la\s+ventana|la\s+app\s+de\s+)?([a-zA-Z0-9_\-\.\s]+))?$",
            clean,
            flags=re.IGNORECASE
        )
        if m_max:
            t = (m_max.group(1) or "").strip().lower()
            target = "active" if not t or t in ["esta", "esta ventana", "la ventana", "la ventana actual", "ventana actual", "actual", "activa", "pantalla", "app"] else t
            return ActionStep(intent="WINDOW_CONTROL", target=target, parameters=StepParameters(position="maximize"))

        m_min = re.search(r"^(?:minimiza|minimizar|oculta|ocultar)(?:\s+(?:la\s+ventana\s+de\s+|la\s+ventana\s+actual|esta\s+ventana|la\s+ventana|la\s+app\s+de\s+)?([a-zA-Z0-9_\-\.\s]+))?$", clean, flags=re.IGNORECASE)
        if m_min:
            t = (m_min.group(1) or "").strip().lower()
            target = "active" if not t or t in ["esta", "esta ventana", "la ventana", "la ventana actual", "ventana actual", "actual", "activa", "pantalla", "app"] else t
            return ActionStep(intent="WINDOW_CONTROL", target=target, parameters=StepParameters(position="minimize"))

        m_cen = re.search(r"^(?:centra|centrar|al\s+centro)(?:\s+(?:la\s+ventana\s+de\s+|la\s+ventana\s+actual|esta\s+ventana|la\s+ventana|la\s+app\s+de\s+)?([a-zA-Z0-9_\-\.\s]+))?$", clean, flags=re.IGNORECASE)
        if m_cen:
            t = (m_cen.group(1) or "").strip().lower()
            target = "active" if not t or t in ["esta", "esta ventana", "la ventana", "la ventana actual", "ventana actual", "actual", "activa", "pantalla", "app"] else t
            return ActionStep(intent="WINDOW_CONTROL", target=target, parameters=StepParameters(position="center"))

        # 8. Pestañas de navegador / editores
        if any(w in norm for w in ["siguiente pestaña", "pestana siguiente", "cambia de pestaña", "cambia de pestana", "pasa de pestaña", "pasa de pestana"]):
            return ActionStep(intent="WINDOW_CONTROL", target="next_tab", parameters=StepParameters())
        if any(w in norm for w in ["anterior pestaña", "pestana anterior", "pestaña previa", "pestana previa"]):
            return ActionStep(intent="WINDOW_CONTROL", target="prev_tab", parameters=StepParameters())
        if any(w in norm for w in ["nueva pestaña", "pestana nueva", "abre una pestaña", "abre una pestana", "otra pestaña", "otra pestana"]):
            return ActionStep(intent="WINDOW_CONTROL", target="new_tab", parameters=StepParameters())
        if any(w in norm for w in ["cierra la pestaña", "cerrar pestaña", "cierra pestaña", "cierra esta pestaña", "cierra pestana", "cerrar pestana", "quita la pestaña"]):
            return ActionStep(intent="WINDOW_CONTROL", target="close_tab", parameters=StepParameters())
        if any(w in norm for w in ["reabre la pestaña", "reabrir pestaña", "recupera la pestaña", "restaura la pestaña", "reabrir pestana"]):
            return ActionStep(intent="WINDOW_CONTROL", target="reopen_tab", parameters=StepParameters())

        return None

    def _fast_open_app_check(self, text: str) -> ActionStep | None:
        """Detección ultra-rápida y determinista de comandos simples de apertura de apps."""
        clean = text.strip()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye banshee)[,\s]*", "", clean, flags=re.IGNORECASE).strip()
        m = re.search(r"^(?:abre|abrir|inicia|iniciar|ejecuta|ejecutar|lanza|lanzar)\s+(?:la\s+app\s+de\s+|el\s+programa\s+de\s+|la\s+aplicacion\s+de\s+|el\s+)?([a-zA-Z0-9_\-\.\s]+)$", clean, flags=re.IGNORECASE)
        if m:
            target = m.group(1).strip().lower()
            if target and target not in ["un archivo", "un proyecto", "una carpeta", "un video", "una cancion", "musica", "el prompt", "la consola", "el navegador"]:
                if not any(w in target for w in ["busca", "videos de", "canciones de", " y ", " e "]):
                    return ActionStep(intent="OPEN_APP", target=target, parameters=StepParameters())
        return None

    def _parse_single_clause(self, clause: str) -> list[ActionStep] | None:
        """Intenta parsear una cláusula o sub-comando individual mediante motores deterministas rápidos."""
        c = clause.strip()
        if not c:
            return None
        p_pipe = self._fast_prompt_check(c)
        if p_pipe and p_pipe.steps:
            return p_pipe.steps
        integ = self._fast_integration_check(c)
        if integ:
            return [integ]
        win = self._fast_window_check(c)
        if win:
            return win if isinstance(win, list) else [win]
        rel = self._fast_relative_action_check(c)
        if rel:
            return [rel]
        med = self._fast_media_check(c)
        if med:
            return [med]
        srch = self._fast_search_check(c)
        if srch:
            return [srch]
        opn = self._fast_open_app_check(c)
        if opn:
            return [opn]
        return None

    def _fast_compound_check(self, text: str) -> list[ActionStep] | None:
        """Descompone oraciones complejas con conectores ('y', 'luego', etc.) en múltiples pasos independientes."""
        clean = text.strip()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye banshee)[,\s]*", "", clean, flags=re.IGNORECASE).strip()

        # No dividir búsquedas de marcas compuestas
        if re.search(r"^busca\s+(?:solo\s+todo|solotodo)", clean, flags=re.IGNORECASE):
            return None

        # Si es 'abre X y busca Y', eso es un comando atómico de búsqueda (cubierto por _fast_search_check)
        if re.search(r"^(?:abre|inicia)\s+[a-zA-Z0-9_\-]+\s+y\s+(?:busca|buscar|encuentra)\s+", clean, flags=re.IGNORECASE):
            return None
        if re.search(r"^(?:busca|pon|reproduce)\s+.+\s+y\s+(?:reproduce|pon|dale\s+play)", clean, flags=re.IGNORECASE):
            return None

        delimiters = [r"\s*,\s*y\s+", r"\s+y\s+", r"\s+e\s+", r"\s+luego\s+", r"\s+despues\s+", r"\s+después\s+", r"\s*,\s*"]
        pattern = "|".join(f"(?:{d})" for d in delimiters)

        parts = [p.strip() for p in re.split(pattern, clean, flags=re.IGNORECASE) if p.strip()]
        if len(parts) < 2:
            return None

        all_steps = []
        for part in parts:
            step_list = self._parse_single_clause(part)
            if step_list:
                all_steps.extend(step_list)
            else:
                return None

        return all_steps if all_steps else None

    def _normalize_intent(self, raw_intent: str) -> str:
        raw = str(raw_intent).upper()
        if any(w in raw for w in ["WINDOW", "VENTANA", "SNAP", "TAB", "PESTAÑA", "PESTANA", "SPLIT", "POSITION", "POSICION", "LAYOUT"]):
            return "WINDOW_CONTROL"
        if any(w in raw for w in ["INTERACT", "LINK", "ENLACE", "RESULTADO", "CLICK_FIRST", "PLAY_FIRST"]):
            return "INTERACT_SCREEN"
        if any(w in raw for w in ["MEDIA", "PLAY", "PAUSE", "PAUSA", "VOLUME", "VOLUMEN", "MUTE", "TRACK", "SILENC"]):
            return "MEDIA_CONTROL"
        if any(w in raw for w in ["SEARCH", "BUSCA", "CONSULT"]):
            return "SEARCH_CONTENT"
        if any(w in raw for w in ["FORGET", "OLVID", "BORR", "ELIMIN", "ELMIN"]):
            return "FORGET_COMMAND"
        if "CREATE_FILE" in raw or "FILE" in raw or "ARCHIVO" in raw:
            return "CREATE_FILE"
        if "WRITE_TEXT" in raw or "WRITE" in raw or "ESCRIB" in raw or "TEXTO" in raw:
            return "WRITE_TEXT"
        if "CREATE_PROJECT" in raw or "CREATE" in raw or "PROJECT" in raw:
            return "CREATE_PROJECT"
        if "OPEN_APP" in raw or "OPEN" in raw:
            return "OPEN_APP"
        if "SYSTEM" in raw:
            return "SYSTEM_CONTROL"
        return "UNKNOWN"

    def parse(self, text_command: str) -> ParsedPipeline:
        # 1. Chequeo rápido de dictado de prompt a agentes de código / IDEs (0ms)
        fast_prompt = self._fast_prompt_check(text_command)
        if fast_prompt:
            return fast_prompt

        # 1.1 Chequeo rápido de consulta o conexión de editores de código (0ms)
        fast_editor = self._fast_editor_status_check(text_command)
        if fast_editor:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_editor],
                confidence=1.0
            )

        # 2. Chequeo rápido de comandos de ventanas, posicionamiento y pestañas (0ms)
        fast_window = self._fast_window_check(text_command)
        if fast_window:
            steps = fast_window if isinstance(fast_window, list) else [fast_window]
            return ParsedPipeline(
                raw_text=text_command,
                steps=steps,
                confidence=1.0
            )

        # 3. Chequeo rápido de integraciones directas (Spotify, Valorant, OBS, Audio Mixer, Hardware, Obsidian) (0ms)
        fast_integ = self._fast_integration_check(text_command)
        if fast_integ:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_integ],
                confidence=1.0
            )

        # 4. Chequeo rápido de acciones relativas en pantalla (0ms)
        fast_relative = self._fast_relative_action_check(text_command)
        if fast_relative:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_relative],
                confidence=1.0
            )

        # 5. Chequeo rápido de control multimedia determinista (0ms)
        fast_media = self._fast_media_check(text_command)
        if fast_media:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_media],
                confidence=1.0
            )

        # 6. Chequeo rápido de búsqueda determinista (0ms)
        fast_search = self._fast_search_check(text_command)
        if fast_search:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_search],
                confidence=1.0
            )

        # 7. Chequeo rápido de descomposición de comandos compuestos multi-acción (0ms)
        fast_compound = self._fast_compound_check(text_command)
        if fast_compound:
            return ParsedPipeline(
                raw_text=text_command,
                steps=fast_compound,
                confidence=1.0
            )

        # 8. Chequeo rápido de apertura simple de apps (0ms)
        fast_open = self._fast_open_app_check(text_command)
        if fast_open:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_open],
                confidence=1.0
            )

        # 9. Análisis con Ollama para comandos complejos, variados o multi-acción
        try:
            response = ollama.chat(
                model=settings.OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Comando: '{text_command}'"}
                ],
                format="json"
            )
            data = json.loads(response["message"]["content"])
            raw_steps = data.get("steps", [])

            steps = []
            for s in raw_steps:
                params = StepParameters(**(s.get("parameters") or {}))
                normalized_intent = self._normalize_intent(s.get("intent", "UNKNOWN"))
                if normalized_intent == "SEARCH_CONTENT" and params.content:
                    params.content = clean_search_term(params.content)
                steps.append(ActionStep(
                    intent=normalized_intent,
                    target=str(s.get("target", "")).strip(),
                    parameters=params
                ))

            return ParsedPipeline(
                raw_text=text_command,
                steps=steps,
                confidence=float(data.get("confidence", 1.0))
            )
        except Exception as e:
            print(f"[NLU Error] Fallo al parsear comandos compuestos: {e}")
            return ParsedPipeline(raw_text=text_command, steps=[])

