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

class ActionStep(BaseModel):
    intent: str                        # OPEN_APP | SEARCH_CONTENT | CREATE_PROJECT | CREATE_FILE | WRITE_TEXT | SYSTEM_CONTROL | FORGET_COMMAND
    target: str                        # Ej: 'vscode', 'youtube', 'chatgpt', 'spotify'
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
            "REGLA CRÍTICA DE COMANDOS COMPUESTOS:\n"
            "Si la frase contiene conectores como 'y', 'e', 'luego', 'además' o múltiples acciones independientes:\n"
            "Genera un objeto paso separado para cada acción DISTINTA.\n"
            "PERO ATENCIÓN: Si el usuario pide abrir un servicio y buscar algo en él (ej: 'abre youtube y busca videos de monster hunter'),\n"
            "NO abras la página principal vacía: genera UN SOLO PASO con intent 'SEARCH_CONTENT'.\n\n"
            "REGLA CRÍTICA DE BÚSQUEDA Y REPRODUCCIÓN EN YOUTUBE / SPOTIFY / WEB:\n"
            "Si el usuario pide buscar y reproducir un video o música (ej: 'busca videos de warframe y reproduce el primer video', 'reproduce musica de queen en youtube', 'pon el primer video de minecraft'):\n"
            "Genera UN SOLO PASO con intent 'SEARCH_CONTENT' hacia el servicio correspondiente ('youtube' o 'spotify') y NO agregues un paso separado 'MEDIA_CONTROL'.\n\n"
            "REGLA CRÍTICA DE PRESERVACIÓN DE MARCAS Y NOMBRES COMPUESTOS:\n"
            "NUNCA elimines ni acortes palabras que forman parte del nombre de una marca, sitio web o término propio/compuesto (ejemplos: 'solo todo', 'solotodo', 'solo leveling', 'han solo', 'pc factory', 'mercado libre').\n"
            "'solo todo' NO significa 'solamente todo', es el nombre de la plataforma 'SoloTodo'.\n"
            "El parámetro 'content' DEBE conservar el nombre completo de la búsqueda ('solo todo').\n\n"
            "REGLAS STRICTAS DE INTENT:\n"
            "- 'HARDWARE_STATUS' (para consultar temperaturas de CPU/GPU, uso de RAM, disco o estado del sistema)\n"
            "- 'SPOTIFY_NOW_PLAYING' (para preguntar qué canción está sonando o qué música suena)\n"
            "- 'SPOTIFY_LIKE' (para guardar la canción actual en favoritos o darle like)\n"
            "- 'SPOTIFY_QUEUE' (para añadir canciones a la cola de Spotify)\n"
            "- 'SET_APP_VOLUME' (para ajustar volumen porcentual de una app como Spotify, Discord o volumen general)\n"
            "- 'MUTE_APP' (para silenciar o mutear una app específica como Discord, juego o navegador)\n"
            "- 'DISCORD_CONNECT_VOICE' (para conectarse o entrar a un canal de voz de Discord como General o Gaming)\n"
            "- 'DISCORD_DISCONNECT_VOICE' (para desconectarse o salir del canal de voz de Discord)\n"
            "- 'VALORANT_STORE' (para consultar las skins u ofertas de la tienda de Valorant)\n"
            "- 'VALORANT_LOCK' (para seleccionar o bloquear agentes en Valorant)\n"
            "- 'LOL_ACCEPT' (para aceptar la partida encontrada en League of Legends)\n"
            "- 'LOL_DECLINE' (para rechazar la partida encontrada en League of Legends)\n"
            "- 'LOL_START_QUEUE' (para iniciar la búsqueda de partida / entrar en cola en League of Legends)\n"
            "- 'LOL_CANCEL_QUEUE' (para cancelar la cola / salir del matchmaking en League of Legends)\n"
            "- 'LOL_STATUS' (para consultar la fase o estado actual en League of Legends)\n"
            "- 'LOL_PICK' (para seleccionar o bloquear campeones en League of Legends)\n"
            "- 'LOL_BAN' (para banear campeones en League of Legends)\n"
            "- 'OBS_START_RECORD' / 'OBS_STOP_RECORD' / 'OBS_RECORD' / 'OBS_REPLAY' (para control de OBS Studio)\n"
            "- 'OBSIDIAN_NOTE' / 'OBSIDIAN_TODO' (para anotar en el diario o agregar tareas en Obsidian)\n"
            "- 'INTERACT_SCREEN' (para abrir el primer enlace, reproducir la primera canción o interactuar con el primer resultado en pantalla)\n"
            "- 'MEDIA_CONTROL' (para pausar, reanudar/play, siguiente pista, pista anterior, silenciar, subir/bajar volumen)\n"
            "- 'SEARCH_CONTENT' (para buscar videos, música o información en YouTube, Google, Spotify o internet)\n"
            "- 'OPEN_APP' (para abrir programas locales, páginas web o accesos directos)\n"
            "- 'CREATE_PROJECT' (para crear o iniciar nuevos proyectos de código)\n"
            "- 'CREATE_FILE' (para crear archivos en una ruta o proyecto activo)\n"
            "- 'WRITE_TEXT' (para redactar notas o dictados en archivos de texto .txt)\n"
            "- 'SYSTEM_CONTROL' (para apagar, reiniciar o comandos del SO)\n"
            "- 'FORGET_COMMAND' (para olvidar o borrar un comando aprendido)\n"
            "- 'UNKNOWN' (si la instrucción no es clara o no coincide con nada)\n\n"
            "REGLAS DE TARGET PARA 'INTERACT_SCREEN':\n"
            "- 'play_first' (para reproducir el primer video o canción de la pantalla o búsqueda previa)\n"
            "- 'open_first_link' (para abrir el primer enlace o resultado en el navegador)\n\n"
            "REGLAS DE TARGET PARA 'MEDIA_CONTROL':\n"
            "- 'pause' o 'play_pause' (para pausar o alternar reproducción)\n"
            "- 'play' (para reanudar o reproducir)\n"
            "- 'next' (para siguiente canción o pista)\n"
            "- 'previous' (para canción anterior)\n"
            "- 'mute' (para silenciar o mutear)\n"
            "- 'volume_up' (para subir volumen)\n"
            "- 'volume_down' (para bajar volumen)\n\n"
            "REGLAS DE PARÁMETROS PARA 'SEARCH_CONTENT':\n"
            "- target: 'youtube', 'google', 'spotify' o el servicio solicitado.\n"
            "- parameters.content: el término de búsqueda limpio, SIN palabras de relleno como 'videos de', 'canciones de', 'musica de', 'temas de'.\n\n"
            "REGLAS DE PARÁMETROS PARA 'CREATE_PROJECT':\n"
            "- project_type: 'python', 'node', 'web' o 'none'.\n"
            "- project_name: nombre del proyecto.\n\n"
            "REGLA DE PALABRA DE ACTIVACIÓN:\n"
            "Ignora palabras de saludo o activación como 'Banchi', 'Vanshee', 'V.ANSHEE', 'Oye Vanshee' al inicio.\n\n"
            "Formato JSON Estricto Requerido:\n"
            "{\n"
            '  "steps": [\n'
            '    {\n'
            '      "intent": "SEARCH_CONTENT",\n'
            '      "target": "youtube",\n'
            '      "parameters": {\n'
            '        "content": "warframe"\n'
            '      }\n'
            '    }\n'
            '  ],\n'
            '  "confidence": 1.0\n'
            "}\n\n"
            "EJEMPLOS OBLIGATORIOS:\n"
            "1. 'busca videos de warframe y reproduce el primer video':\n"
            '   {"steps": [{"intent": "SEARCH_CONTENT", "target": "youtube", "parameters": {"content": "warframe"}}], "confidence": 1.0}\n'
            "2. 'busca canciones de lana del rey en spotify':\n"
            '   {"steps": [{"intent": "SEARCH_CONTENT", "target": "spotify", "parameters": {"content": "lana del rey"}}], "confidence": 1.0}\n'
            "3. 'busca solo todo en el navegador y abre el primer link':\n"
            '   {"steps": [{"intent": "SEARCH_CONTENT", "target": "google", "parameters": {"content": "solo todo"}}], "confidence": 1.0}\n'
            "4. 'pausa la musica de spotify':\n"
            '   {"steps": [{"intent": "MEDIA_CONTROL", "target": "pause", "parameters": {}}], "confidence": 1.0}\n'
            "5. 'siguiente cancion':\n"
            '   {"steps": [{"intent": "MEDIA_CONTROL", "target": "next", "parameters": {}}], "confidence": 1.0}\n'
            "6. 'sube el volumen':\n"
            '   {"steps": [{"intent": "MEDIA_CONTROL", "target": "volume_up", "parameters": {}}], "confidence": 1.0}\n'
            "7. 'ejecuta vs code e inicia un nuevo proyecto python llamado mi_app':\n"
            '   {"steps": [{"intent": "OPEN_APP", "target": "vscode", "parameters": {}}, {"intent": "CREATE_PROJECT", "target": "vscode", "parameters": {"project_type": "python", "project_name": "mi_app"}}], "confidence": 1.0}\n'
            "8. 'abre antigravity y pon el siguiente prompt escribe hola mundo':\n"
            '   {"steps": [{"intent": "OPEN_APP", "target": "antigravity", "parameters": {}}, {"intent": "WRITE_TEXT", "target": "antigravity", "parameters": {"content": "hola mundo"}}], "confidence": 1.0}\n'
            "9. 'escribe el siguiente prompt crea una calculadora en python':\n"
            '   {"steps": [{"intent": "WRITE_TEXT", "target": "prompt", "parameters": {"content": "crea una calculadora en python"}}], "confidence": 1.0}\n'
            "10. 'olvida el ultimo comando':\n"
            '   {"steps": [{"intent": "FORGET_COMMAND", "target": "last", "parameters": {}}], "confidence": 1.0}\n'
            "Responde ÚNICAMENTE con el objeto JSON."
        )

    def _fast_prompt_check(self, text: str) -> ParsedPipeline | None:
        """Detección ultra-rápida y determinista de comandos para escribir prompts en agentes/IDEs."""
        clean = text.strip()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye banshee)[,\s]*", "", clean, flags=re.IGNORECASE).strip()

        # 1. abre <app> y pon/escribe el prompt <texto> (ej: 'abre Antigravity y pon el siguiente prompt. Escribe hola mundo')
        m1 = re.search(r"^(?:abre|abrir|inicia|ejecuta)\s+(antigravity|cursor|claude|codex|opencode|windsurf|vscode|vs code)\s+y\s+(?:pon|escribe|envia|enviar|redacta)\s+(?:el\s+)?(?:siguiente\s+)?(?:prompt|mensaje|texto)?[:,\s\.]+(?:escribe\s+)?(.+)$", clean, flags=re.IGNORECASE)
        if m1:
            app_target = m1.group(1).lower().strip()
            prompt_content = m1.group(2).strip().rstrip(".")
            return ParsedPipeline(
                raw_text=text,
                steps=[
                    ActionStep(intent="OPEN_APP", target=app_target, parameters=StepParameters()),
                    ActionStep(intent="WRITE_TEXT", target=app_target, parameters=StepParameters(content=prompt_content))
                ],
                confidence=1.0
            )

        # 2. pon/escribe el siguiente prompt <texto>
        m2 = re.search(r"^(?:pon|escribe|envia|enviar|dicta|redacta)\s+(?:el\s+)?(?:siguiente\s+)?(?:prompt|mensaje)[:,\s\.]+(?:escribe\s+)?(.+)$", clean, flags=re.IGNORECASE)
        if m2:
            prompt_content = m2.group(1).strip().rstrip(".")
            return ParsedPipeline(
                raw_text=text,
                steps=[
                    ActionStep(intent="WRITE_TEXT", target="prompt", parameters=StepParameters(content=prompt_content))
                ],
                confidence=1.0
            )

        # 3. escribe en <app/chat> <texto>
        m3 = re.search(r"^(?:escribe|pon|envia|redacta)\s+en\s+(antigravity|cursor|claude|codex|opencode|windsurf|vscode|vs code|el\s+chat|el\s+agente)[:,\s\.]+(?:escribe\s+)?(.+)$", clean, flags=re.IGNORECASE)
        if m3:
            target_app = m3.group(1).lower().strip().replace("el chat", "chat").replace("el agente", "agent")
            prompt_content = m3.group(2).strip().rstrip(".")
            return ParsedPipeline(
                raw_text=text,
                steps=[
                    ActionStep(intent="WRITE_TEXT", target=target_app, parameters=StepParameters(content=prompt_content))
                ],
                confidence=1.0
            )

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
            srv = m1.group(1).strip().lower().replace("el navegador", "google").replace("el buscador", "google")
            qry = clean_search_term(m1.group(2).strip())
            if qry and qry.lower() not in ignored_search_terms:
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
        if m_play_spotify and not any(w in norm for w in ["youtube", "video", "obs", "obsidian", "valorant", "lol", "league", "volumen"]):
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

        return None

    def _normalize_intent(self, raw_intent: str) -> str:
        raw = str(raw_intent).upper()
        if any(w in raw for w in ["INTERACT", "SCREEN", "LINK", "PANTALLA", "RESULTADO"]):
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

        # 2. Chequeo rápido de integraciones directas (Spotify, Valorant, OBS, Audio Mixer, Hardware, Obsidian) (0ms)
        fast_integ = self._fast_integration_check(text_command)
        if fast_integ:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_integ],
                confidence=1.0
            )

        # 3. Chequeo rápido de acciones relativas en pantalla (0ms)
        fast_relative = self._fast_relative_action_check(text_command)
        if fast_relative:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_relative],
                confidence=1.0
            )

        # 4. Chequeo rápido de control multimedia determinista (0ms)
        fast_media = self._fast_media_check(text_command)
        if fast_media:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_media],
                confidence=1.0
            )

        # 4. Chequeo rápido de búsqueda determinista (0ms)
        fast_search = self._fast_search_check(text_command)
        if fast_search:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_search],
                confidence=1.0
            )

        # 5. Análisis con Ollama para comandos complejos o multi-acción
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
