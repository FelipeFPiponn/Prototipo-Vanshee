import json
import ollama
from pydantic import BaseModel, Field
from config.settings import settings

class StepParameters(BaseModel):
    project_type: str = "none"         # Ej: 'python', 'node', 'cpp', 'none'
    project_name: str = "nuevo_proyecto"
    path: str = ""

class ActionStep(BaseModel):
    intent: str                        # OPEN_APP | CREATE_PROJECT | SYSTEM_CONTROL | FORGET_COMMAND
    target: str                        # Ej: 'vscode', 'chatgpt', 'spotify'
    parameters: StepParameters = Field(default_factory=StepParameters)

class ParsedPipeline(BaseModel):
    raw_text: str
    steps: list[ActionStep]
    confidence: float = 1.0

class IntentParser:
    def __init__(self):
        self.system_prompt = (
            "Eres el motor NLU de V.ANSHEE para automatización en Windows OS.\n"
            "Analiza el texto del usuario y descompón la solicitud en una lista ordenada de pasos (pipeline).\n\n"
            "Formato JSON Estricto Requerido:\n"
            "{\n"
            '  "steps": [\n'
            '    {\n'
            '      "intent": "OPEN_APP | CREATE_PROJECT | SYSTEM_CONTROL | FORGET_COMMAND | UNKNOWN",\n'
            '      "target": "nombre de la app, servicio o comando",\n'
            '      "parameters": {\n'
            '        "project_type": "python | node | web | none",\n'
            '        "project_name": "nombre_del_proyecto_o_default",\n'
            '        "path": ""\n'
            '      }\n'
            '    }\n'
            '  ],\n'
            '  "confidence": 1.0\n'
            "}\n\n"
            "EJEMPLOS:\n"
            "1. 'ejecuta vs code e inicia un nuevo proyecto python llamado mi_api':\n"
            "   Pasos: [OPEN_APP -> 'vscode'], [CREATE_PROJECT -> 'vscode', params: {project_type: 'python', project_name: 'mi_api'}]\n"
            "2. 'abrir chat gpt y spotify':\n"
            "   Pasos: [OPEN_APP -> 'chatgpt'], [OPEN_APP -> 'spotify']\n"
            "Responde ÚNICAMENTE con el objeto JSON."
        )

    def parse(self, text_command: str) -> ParsedPipeline:
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
                steps.append(ActionStep(
                    intent=s.get("intent", "UNKNOWN").upper(),
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