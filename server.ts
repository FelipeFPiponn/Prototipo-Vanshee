import express, { Request, Response } from "express";
import path from "path";
import fs from "fs";
import { GoogleGenAI } from "@google/genai";
import { createServer as createViteServer } from "vite";

const app = express();
const PORT = 3000;

app.use(express.json());

// In-memory data store replicating vanshee.db tables
interface ExecutionLogItem {
  id: number;
  full_command: string;
  day_of_week: number;
  hour_of_day: number;
  executed_at: string;
  steps: any[];
}

interface DetectedRoutineItem {
  id: number;
  routine_name: string;
  sequence_json: string;
  trigger_hour: number;
  frequency: number;
}

interface LearnedCommandItem {
  id: number;
  keyword: string;
  execution_target: string;
  command_type: 'url' | 'protocol' | 'app' | 'script';
  created_at: string;
}

const KNOWN_TARGETS: Record<string, { target: string; type: 'url' | 'protocol' | 'app' }> = {
  chatgpt: { target: "https://chatgpt.com", type: "url" },
  "chat gpt": { target: "https://chatgpt.com", type: "url" },
  claude: { target: "https://claude.ai", type: "url" },
  youtube: { target: "https://youtube.com", type: "url" },
  github: { target: "https://github.com", type: "url" },
  gmail: { target: "https://mail.google.com", type: "url" },
  steam: { target: "steam://open/main", type: "protocol" },
  discord: { target: "discord://", type: "protocol" },
  spotify: { target: "spotify://", type: "protocol" },
  calculadora: { target: "calc.exe", type: "app" },
  calc: { target: "calc.exe", type: "app" },
  cmd: { target: "cmd.exe", type: "app" },
  terminal: { target: "wt.exe", type: "app" },
  vscode: { target: "code", type: "app" },
  "vs code": { target: "code", type: "app" },
  "visual studio code": { target: "code", type: "app" },
  chrome: { target: "https://google.com", type: "url" },
  navegador: { target: "https://google.com", type: "url" },
  notion: { target: "https://notion.so", type: "url" },
  slack: { target: "slack://", type: "protocol" }
};

let nextLogId = 1;
let nextRoutineId = 1;
let nextCommandId = 1;

const executionLogs: ExecutionLogItem[] = [];
const detectedRoutines: DetectedRoutineItem[] = [];
const learnedCommands: LearnedCommandItem[] = [
  {
    id: nextCommandId++,
    keyword: "docs",
    execution_target: "https://docs.python.org/3/",
    command_type: "url",
    created_at: new Date(Date.now() - 3600000 * 24).toISOString()
  },
  {
    id: nextCommandId++,
    keyword: "duoc",
    execution_target: "https://www.duoc.cl",
    command_type: "url",
    created_at: new Date(Date.now() - 3600000 * 48).toISOString()
  }
];

// Seed initial execution logs for habit engine demo
function seedInitialData() {
  const now = new Date();
  const currentHour = now.getHours();

  // Seed sample morning habit
  const morningHour = 9;
  for (let i = 0; i < 4; i++) {
    executionLogs.push({
      id: nextLogId++,
      full_command: "ejecuta vs code y abre github",
      day_of_week: (i + 1) % 7,
      hour_of_day: morningHour,
      executed_at: new Date(Date.now() - (4 - i) * 86400000).toISOString(),
      steps: [
        { intent: "OPEN_APP", target: "vscode", parameters: { project_type: "none", project_name: "" } },
        { intent: "OPEN_APP", target: "github", parameters: { project_type: "none", project_name: "" } }
      ]
    });
  }

  detectedRoutines.push({
    id: nextRoutineId++,
    routine_name: "Rutina_ejecuta vs code y a",
    sequence_json: "ejecuta vs code y abre github",
    trigger_hour: morningHour,
    frequency: 4
  });

  // Also seed an active pattern around current hour for immediate detection demonstration
  for (let i = 0; i < 3; i++) {
    executionLogs.push({
      id: nextLogId++,
      full_command: "abrir chat gpt y spotify",
      day_of_week: now.getDay(),
      hour_of_day: currentHour,
      executed_at: new Date(Date.now() - (3 - i) * 3600000 * 2).toISOString(),
      steps: [
        { intent: "OPEN_APP", target: "chatgpt", parameters: { project_type: "none", project_name: "" } },
        { intent: "OPEN_APP", target: "spotify", parameters: { project_type: "none", project_name: "" } }
      ]
    });
  }

  detectedRoutines.push({
    id: nextRoutineId++,
    routine_name: "Rutina_abrir chat gpt y sp",
    sequence_json: "abrir chat gpt y spotify",
    trigger_hour: currentHour,
    frequency: 3
  });
}

seedInitialData();

// Lazy Gemini client helper
let geminiClient: GoogleGenAI | null = null;
function getGeminiClient(): GoogleGenAI | null {
  if (!process.env.GEMINI_API_KEY) return null;
  if (!geminiClient) {
    geminiClient = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
  }
  return geminiClient;
}

// Deterministic NLU fallback rule parser (mimics exact schema from v-anshee/config/intents_schema.json)
function deterministicParse(text: string) {
  const clean = text.trim();
  const lower = clean.toLowerCase();

  // Check forget command
  if (lower.startsWith("olvida") || lower.startsWith("borra") || lower.startsWith("forget")) {
    const target = lower.replace(/^(olvida|borra|forget)\s+(el comando\s+|a\s+)?/i, "").trim();
    return {
      raw_text: clean,
      steps: [
        {
          intent: "FORGET_COMMAND",
          target: target || "last",
          parameters: { project_type: "none", project_name: "" }
        }
      ],
      confidence: 0.95
    };
  }

  // Check compound commands separated by ' y ', ' e ', ' luego ', ' despues ', ','
  const subCommands = lower.split(/\s+(?:y|e|luego|después|despues)\s+|,\s*/);
  const steps: any[] = [];

  for (const part of subCommands) {
    const trimmed = part.trim();
    if (!trimmed) continue;

    // Check project creation
    if (trimmed.includes("proyecto") || trimmed.includes("crea") || trimmed.includes("inicia")) {
      let pType = "python";
      if (trimmed.includes("node") || trimmed.includes("npm") || trimmed.includes("javascript")) pType = "node";
      else if (trimmed.includes("react")) pType = "react";
      else if (trimmed.includes("csharp") || trimmed.includes("c#")) pType = "csharp";

      const nameMatch = trimmed.match(/(?:llamado|nombre|para)\s+([a-zA-Z0-9_\-]+)/);
      const pName = nameMatch ? nameMatch[1] : "nuevo_proyecto";

      steps.push({
        intent: "CREATE_PROJECT",
        target: "vscode",
        parameters: {
          project_type: pType,
          project_name: pName,
          path: ""
        }
      });
      continue;
    }

    // Check system control
    if (trimmed.includes("apagar") || trimmed.includes("reiniciar") || trimmed.includes("suspender") || trimmed.includes("volumen")) {
      steps.push({
        intent: "SYSTEM_CONTROL",
        target: trimmed,
        parameters: { project_type: "none", project_name: "" }
      });
      continue;
    }

    // Default: OPEN_APP / OPEN TARGET
    let target = trimmed
      .replace(/^(ejecuta|abre|abrir|ejecutar|inicia|lanzar|abreme|pon|poner)\s+/i, "")
      .trim();

    // Map common synonyms
    if (target === "vs code" || target === "visual studio code") target = "vscode";
    if (target === "chat gpt") target = "chatgpt";
    if (target === "el navegador" || target === "internet") target = "navegador";

    steps.push({
      intent: "OPEN_APP",
      target: target || trimmed,
      parameters: { project_type: "none", project_name: "" }
    });
  }

  return {
    raw_text: clean,
    steps: steps.length > 0 ? steps : [
      {
        intent: "OPEN_APP",
        target: clean,
        parameters: { project_type: "none", project_name: "" }
      }
    ],
    confidence: 0.9
  };
}

// Analyze routines logic (HabitEngine from habit_engine.py)
function analyzePatterns(command: string, hour: number) {
  const cleanCmd = command.toLowerCase().trim();
  const minHour = Math.max(0, hour - 1);
  const maxHour = Math.min(23, hour + 1);

  const count = executionLogs.filter(
    (l) => l.full_command === cleanCmd && l.hour_of_day >= minHour && l.hour_of_day <= maxHour
  ).length;

  if (count >= 3) {
    const existing = detectedRoutines.find(
      (r) => r.sequence_json === cleanCmd && Math.abs(r.trigger_hour - hour) <= 1
    );
    if (existing) {
      existing.frequency = count;
      existing.trigger_hour = hour;
    } else {
      detectedRoutines.push({
        id: nextRoutineId++,
        routine_name: `Rutina_${cleanCmd.substring(0, 20)}`,
        sequence_json: cleanCmd,
        trigger_hour: hour,
        frequency: count
      });
    }
  }
}

// ---------------- API ROUTES ----------------

// System status
app.get("/api/status", (_req: Request, res: Response) => {
  const now = new Date();
  const currentHour = now.getHours();

  const suggestedRoutine = detectedRoutines.find(
    (r) => Math.abs(r.trigger_hour - currentHour) <= 1
  );

  res.json({
    status: "ok",
    wake_word: "v_anshee",
    stt_model: "Whisper STT (Web / Server)",
    llm_provider: process.env.GEMINI_API_KEY ? "Gemini Pro / Flash" : "V.ANSHEE Local NLU Engine",
    total_commands: executionLogs.length,
    detected_routines_count: detectedRoutines.length,
    learned_commands_count: learnedCommands.length,
    current_hour: currentHour,
    suggested_routine: suggestedRoutine || null
  });
});

// NLU Intent Parser endpoint
app.post("/api/parse", async (req: Request, res: Response) => {
  const { command } = req.body;
  if (!command || typeof command !== "string") {
    return res.status(400).json({ error: "Missing 'command' in request body" });
  }

  const ai = getGeminiClient();
  if (ai) {
    try {
      const systemPrompt = `Eres el motor NLU de V.ANSHEE para automatización e interpretación en Windows OS.
Analiza el texto del usuario y descompón la solicitud en una lista ordenada de pasos (pipeline).

Formato JSON Estricto Requerido:
{
  "steps": [
    {
      "intent": "OPEN_APP | CREATE_PROJECT | SYSTEM_CONTROL | FORGET_COMMAND | UNKNOWN",
      "target": "nombre de la app, servicio o comando",
      "parameters": {
        "project_type": "python | node | react | csharp | none",
        "project_name": "nombre_del_proyecto",
        "path": ""
      }
    }
  ],
  "confidence": 1.0
}
Comando: '${command}'
Responde ÚNICAMENTE con JSON válido, sin bloques markdown de formato ni comentarios.`;

      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: systemPrompt,
      });

      const rawContent = response.text || "";
      const jsonMatch = rawContent.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        return res.json({
          raw_text: command,
          steps: parsed.steps || [],
          confidence: parsed.confidence || 0.98
        });
      }
    } catch (err) {
      console.warn("[Gemini NLU Fallback] Error in Gemini parser, using deterministic NLU:", err);
    }
  }

  // Fallback to deterministic NLU
  const result = deterministicParse(command);
  res.json(result);
});

// Dynamic Resolver & Executor
app.post("/api/execute", (req: Request, res: Response) => {
  const { pipeline } = req.body;
  if (!pipeline || !Array.isArray(pipeline.steps)) {
    return res.status(400).json({ error: "Invalid pipeline structure" });
  }

  const now = new Date();
  const currentHour = now.getHours();
  const dayOfWeek = now.getDay();

  const executedSteps = pipeline.steps.map((step: any) => {
    const intent = (step.intent || "UNKNOWN").toUpperCase();
    const target = (step.target || "").toLowerCase().trim();

    // Check learned commands
    const learned = learnedCommands.find((c) => c.keyword.toLowerCase() === target);
    if (learned) {
      return {
        ...step,
        resolvedTarget: learned.execution_target,
        targetType: learned.command_type,
        status: "completed",
        message: `Comando aprendido resuelto: ${learned.execution_target}`
      };
    }

    // Check known targets
    if (KNOWN_TARGETS[target]) {
      const known = KNOWN_TARGETS[target];
      return {
        ...step,
        resolvedTarget: known.target,
        targetType: known.type,
        status: "completed",
        message: `Servicio o app resuelto (${known.type}): ${known.target}`
      };
    }

    if (intent === "FORGET_COMMAND") {
      const idx = learnedCommands.findIndex((c) => c.keyword.toLowerCase().includes(target));
      if (idx !== -1) {
        learnedCommands.splice(idx, 1);
        return {
          ...step,
          resolvedTarget: target,
          targetType: "script",
          status: "completed",
          message: `Se ha olvidado el comando aprendido para '${target}'`
        };
      }
      return {
        ...step,
        resolvedTarget: target,
        targetType: "script",
        status: "completed",
        message: `No había comando activo registrado para '${target}'`
      };
    }

    if (intent === "CREATE_PROJECT") {
      const pName = step.parameters?.project_name || "nuevo_proyecto";
      const pType = step.parameters?.project_type || "python";
      return {
        ...step,
        resolvedTarget: `C:\\Users\\Desktop\\VANSHEE_Projects\\${pName}`,
        targetType: "app",
        status: "completed",
        message: `Entorno ${pType.toUpperCase()} '${pName}' inicializado y abierto en VS Code.`
      };
    }

    // Fallback URL or generic app launch
    const isUrl = target.startsWith("http://") || target.startsWith("https://") || target.includes(".com") || target.includes(".org");
    return {
      ...step,
      resolvedTarget: isUrl ? (target.startsWith("http") ? target : `https://${target}`) : target,
      targetType: isUrl ? "url" : "app",
      status: "completed",
      message: isUrl ? `Abriendo navegador web en ${target}` : `Lanzando proceso en Windows: ${target}`
    };
  });

  // Log in Habit Engine
  const logItem: ExecutionLogItem = {
    id: nextLogId++,
    full_command: pipeline.raw_text,
    day_of_week: dayOfWeek,
    hour_of_day: currentHour,
    executed_at: now.toISOString(),
    steps: executedSteps
  };
  executionLogs.unshift(logItem);

  // Analyze habits
  analyzePatterns(pipeline.raw_text, currentHour);

  res.json({
    success: true,
    log: logItem,
    executedSteps,
    message: `V.ANSHEE ejecutó exitosamente ${executedSteps.length} paso(s).`
  });
});

// Routines endpoint
app.get("/api/routines", (_req: Request, res: Response) => {
  const currentHour = new Date().getHours();
  const suggested = detectedRoutines.find((r) => Math.abs(r.trigger_hour - currentHour) <= 1);
  res.json({
    routines: detectedRoutines,
    suggested: suggested || null,
    current_hour: currentHour
  });
});

// Execution logs endpoint
app.get("/api/logs", (_req: Request, res: Response) => {
  res.json({
    logs: executionLogs.slice(0, 50)
  });
});

// Learned commands endpoints
app.get("/api/commands", (_req: Request, res: Response) => {
  res.json({
    commands: learnedCommands,
    knownTargets: KNOWN_TARGETS
  });
});

app.post("/api/commands", (req: Request, res: Response) => {
  const { keyword, execution_target, command_type } = req.body;
  if (!keyword || !execution_target) {
    return res.status(400).json({ error: "Missing keyword or execution_target" });
  }
  const existing = learnedCommands.find((c) => c.keyword.toLowerCase() === keyword.toLowerCase());
  if (existing) {
    existing.execution_target = execution_target;
    existing.command_type = command_type || "app";
    return res.json({ command: existing, updated: true });
  }

  const newCmd: LearnedCommandItem = {
    id: nextCommandId++,
    keyword: keyword.toLowerCase().trim(),
    execution_target,
    command_type: command_type || "app",
    created_at: new Date().toISOString()
  };
  learnedCommands.unshift(newCmd);
  res.json({ command: newCmd, created: true });
});

app.delete("/api/commands/:keyword", (req: Request, res: Response) => {
  const kw = String(req.params.keyword).toLowerCase();
  const index = learnedCommands.findIndex((c) => c.keyword.toLowerCase() === kw);
  if (index !== -1) {
    const removed = learnedCommands.splice(index, 1);
    return res.json({ success: true, removed: removed[0] });
  }
  res.status(404).json({ error: "Command keyword not found" });
});

// Clear history
app.post("/api/logs/clear", (_req: Request, res: Response) => {
  executionLogs.length = 0;
  res.json({ success: true, message: "Historial de ejecuciones reiniciado." });
});

// Vite middleware & Production Serving
async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (_req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`[V.ANSHEE Core] Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
