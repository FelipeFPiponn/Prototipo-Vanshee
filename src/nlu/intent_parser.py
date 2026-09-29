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
            "REGLAS STRICTAS DE INTENT:\n"
            "El campo 'intent' DEBE ser ÚNICAMENTE uno de estos valores exactos:\n"
            "- 'SEARCH_CONTENT' (para buscar videos, música o información en YouTube, Google, Spotify o internet)\n"
            "- 'OPEN_APP' (para abrir programas locales, páginas web o accesos directos)\n"
            "- 'CREATE_PROJECT' (para crear o iniciar nuevos proyectos de código)\n"
            "- 'CREATE_FILE' (para crear archivos en una ruta o proyecto activo)\n"
            "- 'WRITE_TEXT' (para redactar notas o dictados en archivos de texto .txt)\n"
            "- 'SYSTEM_CONTROL' (para apagar, reiniciar, volumen o comandos del SO)\n"
            "- 'FORGET_COMMAND' (para olvidar o borrar un comando aprendido)\n"
            "- 'UNKNOWN' (si la instrucción no es clara o no coincide con nada)\n\n"
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
            '        "content": "monster hunter"\n'
            '      }\n'
            '    }\n'
            '  ],\n'
            '  "confidence": 1.0\n'
            "}\n\n"
            "EJEMPLOS OBLIGATORIOS:\n"
            "1. 'abre youtube y busca videos de monster hunter':\n"
            '   {"steps": [{"intent": "SEARCH_CONTENT", "target": "youtube", "parameters": {"content": "monster hunter"}}], "confidence": 1.0}\n'
            "2. 'busca canciones de lana del rey en spotify':\n"
            '   {"steps": [{"intent": "SEARCH_CONTENT", "target": "spotify", "parameters": {"content": "lana del rey"}}], "confidence": 1.0}\n'
            "3. 'busca en google el clima de hoy':\n"
            '   {"steps": [{"intent": "SEARCH_CONTENT", "target": "google", "parameters": {"content": "el clima de hoy"}}], "confidence": 1.0}\n'
            "4. 'ejecuta vs code e inicia un nuevo proyecto python llamado mi_app':\n"
            '   {"steps": [{"intent": "OPEN_APP", "target": "vscode", "parameters": {}}, {"intent": "CREATE_PROJECT", "target": "vscode", "parameters": {"project_type": "python", "project_name": "mi_app"}}], "confidence": 1.0}\n'
            "5. 'olvida el ultimo comando':\n"
            '   {"steps": [{"intent": "FORGET_COMMAND", "target": "last", "parameters": {}}], "confidence": 1.0}\n'
            "Responde ÚNICAMENTE con el objeto JSON."
        )

    def _fast_search_check(self, text: str) -> ActionStep | None:
        """Detección ultra-rápida y determinista de comandos de búsqueda comunes."""
        clean = text.strip()
        clean = re.sub(r"^(?:banshee|vanshee|banchi|oye banshee|oye vanshee)[,\s]*", "", clean, flags=re.IGNORECASE).strip()

        # 1. abre <servicio> y busca <query>
        m1 = re.search(r"^(?:abre|abrir|inicia|ejecuta)\s+(youtube|google|spotify|brave|chrome)\s+y\s+(?:busca|buscar|encuentra|pon)\s+(.+)$", clean, flags=re.IGNORECASE)
        if m1:
            srv = m1.group(1).strip().lower()
            qry = clean_search_term(m1.group(2).strip())
            return ActionStep(intent="SEARCH_CONTENT", target=srv, parameters=StepParameters(content=qry))

        # 2. busca <query> en <servicio>
        m2 = re.search(r"^(?:busca|buscar|encuentra|pon|reproduce)\s+(.+?)\s+en\s+(youtube|google|spotify|brave|chrome)$", clean, flags=re.IGNORECASE)
        if m2:
            srv = m2.group(2).strip().lower()
            qry = clean_search_term(m2.group(1).strip())
            return ActionStep(intent="SEARCH_CONTENT", target=srv, parameters=StepParameters(content=qry))

        # 3. busca en <servicio> <query>
        m3 = re.search(r"^(?:busca|buscar|encuentra|pon|reproduce)\s+en\s+(youtube|google|spotify|brave|chrome)\s+(.+)$", clean, flags=re.IGNORECASE)
        if m3:
            srv = m3.group(1).strip().lower()
            qry = clean_search_term(m3.group(2).strip())
            return ActionStep(intent="SEARCH_CONTENT", target=srv, parameters=StepParameters(content=qry))

        return None

    def _normalize_intent(self, raw_intent: str) -> str:
        raw = str(raw_intent).upper()
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
        # 1. Chequeo rápido de búsqueda determinista (0ms de latencia, 100% de precisión)
        fast_search = self._fast_search_check(text_command)
        if fast_search:
            return ParsedPipeline(
                raw_text=text_command,
                steps=[fast_search],
                confidence=1.0
            )

        # 2. Análisis con Ollama para comandos complejos o multi-acción
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
                params = StepParameters(**s.get("parameters", {}))
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
