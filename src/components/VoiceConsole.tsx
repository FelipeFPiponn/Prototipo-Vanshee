import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Send, Play, CheckCircle2, AlertCircle, ExternalLink, Sparkles, FolderGit2, Terminal, RefreshCw } from 'lucide-react';
import { ActionStep, ParsedPipeline } from '../types';

interface VoiceConsoleProps {
  onCommandExecuted: () => void;
}

export const VoiceConsole: React.FC<VoiceConsoleProps> = ({ onCommandExecuted }) => {
  const [commandInput, setCommandInput] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [pipeline, setPipeline] = useState<ParsedPipeline | null>(null);
  const [executionResult, setExecutionResult] = useState<any | null>(null);
  const [consoleLogs, setConsoleLogs] = useState<string[]>([
    "=== V.ANSHEE Core [Sistema de Control por Voz] ===",
    "[V.ANSHEE] Sistema iniciado y listo para recibir intenciones.",
    "[NLU] Parser cargado. Mapeos de apps y resolver dinámico listos."
  ]);

  const recognitionRef = useRef<any>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const addLog = (text: string) => {
    setConsoleLogs((prev) => [...prev, text]);
  };

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [consoleLogs]);

  // Setup Web Speech API for voice recognition
  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'es-ES';

      recognition.onstart = () => {
        setIsListening(true);
        addLog("[AudioRecorder] Micrófono activado. Escuchando instrucción...");
      };

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        setCommandInput(transcript);
      };

      recognition.onerror = (event: any) => {
        setIsListening(false);
        addLog(`[STT Whisper/WebSpeech] Error de captura: ${event.error}`);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    } else {
      addLog("[STT Engine] Navegador sin SpeechRecognition nativo. Puedes usar entrada directa por teclado.");
    }
  }, []);

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      setCommandInput('');
      try {
        recognitionRef.current?.start();
      } catch {
        // restart if already active
        recognitionRef.current?.stop();
        setTimeout(() => recognitionRef.current?.start(), 150);
      }
    }
  };

  const handleProcessCommand = async (customText?: string) => {
    const textToProcess = (customText || commandInput).trim();
    if (!textToProcess) return;

    setIsProcessing(true);
    setExecutionResult(null);
    addLog(`\n[V.ANSHEE] Procesando comando: "${textToProcess}"`);

    try {
      // 1. NLU Parsing
      addLog("[NLP / NLU Parser] Analizando intención y descomponiendo sub-comandos...");
      const parseRes = await fetch('/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: textToProcess })
      });

      if (!parseRes.ok) {
        throw new Error(`Error en parser NLU: ${parseRes.statusText}`);
      }

      const parsed: ParsedPipeline = await parseRes.json();
      setPipeline(parsed);
      addLog(`[NLP Parser] Identificados ${parsed.steps.length} paso(s) con confianza ${(parsed.confidence * 100).toFixed(0)}%`);

      // 2. OS Dispatcher / Dynamic Resolver execution
      addLog("[OSExecutor] Enviando pipeline al despachador de ejecución...");
      const execRes = await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pipeline: parsed })
      });

      if (!execRes.ok) {
        throw new Error(`Error en ejecución OS: ${execRes.statusText}`);
      }

      const execData = await execRes.json();
      setExecutionResult(execData);

      execData.executedSteps?.forEach((step: ActionStep, idx: number) => {
        addLog(` -> Paso ${idx + 1}: [${step.intent}] ${step.target} -> ${step.message || 'Completado'}`);
      });

      addLog(`[HabitEngine] Registro de hábito actualizado. Frecuencia y hora analizadas.`);
      onCommandExecuted();
    } catch (err: any) {
      addLog(`[Error] Fallo en la canalización: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const sampleCommands = [
    "ejecuta vs code e inicia un nuevo proyecto python llamado mi_api",
    "abrir chat gpt y spotify",
    "ejecutar terminal y abrir github",
    "olvida spotify",
    "iniciar proyecto node llamado auth_service"
  ];

  return (
    <div className="space-y-6">
      {/* Voice & Text Input Box */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/40 backdrop-blur-md">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-cyan-400"></span>
            <span className="text-sm font-semibold text-slate-200">Entrada de Voz y Comandos</span>
          </div>
          {isListening && (
            <span className="text-xs font-mono font-medium text-rose-400 animate-pulse flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              Escuchando en vivo...
            </span>
          )}
        </div>

        {/* Input Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleProcessCommand();
          }}
          className="relative flex items-center"
        >
          <input
            id="voice-command-input"
            type="text"
            value={commandInput}
            onChange={(e) => setCommandInput(e.target.value)}
            placeholder="Presiona el micrófono o escribe (ej: 'ejecuta vs code e inicia un nuevo proyecto python llamado mi_api')..."
            disabled={isProcessing}
            className="w-full rounded-xl bg-slate-950 border border-slate-800 py-3.5 pl-4 pr-28 text-sm text-slate-100 placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 transition-all font-mono"
          />

          <div className="absolute right-2 flex items-center gap-1.5">
            <button
              id="btn-voice-mic"
              type="button"
              onClick={toggleListening}
              title={isListening ? "Detener micrófono" : "Activar micrófono para dictar"}
              className={`p-2.5 rounded-lg transition-all ${
                isListening
                  ? 'bg-rose-500 text-white shadow-lg shadow-rose-500/30 animate-bounce'
                  : 'bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700'
              }`}
            >
              {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>

            <button
              id="btn-send-command"
              type="submit"
              disabled={isProcessing || !commandInput.trim()}
              className="p-2.5 rounded-lg bg-cyan-500 text-slate-950 font-medium hover:bg-cyan-400 disabled:opacity-50 disabled:pointer-events-none transition-all"
              title="Ejecutar instrucción"
            >
              {isProcessing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </form>

        {/* Preset quick test chips */}
        <div className="mt-3 flex items-center gap-2 overflow-x-auto pb-1 text-xs">
          <span className="text-slate-400 font-mono flex-shrink-0 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" /> Pruebas rápidas:
          </span>
          {sampleCommands.map((cmd, i) => (
            <button
              key={i}
              type="button"
              onClick={() => {
                setCommandInput(cmd);
                handleProcessCommand(cmd);
              }}
              className="whitespace-nowrap px-2.5 py-1 rounded-md bg-slate-800/80 hover:bg-cyan-950/60 hover:text-cyan-300 hover:border-cyan-700/60 border border-slate-700/60 text-slate-300 font-mono transition-colors"
            >
              "{cmd}"
            </button>
          ))}
        </div>
      </div>

      {/* Pipeline Decomposed Steps Viewer */}
      {pipeline && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                <Play className="w-4 h-4 text-cyan-400" /> Pipeline de Acciones Descompuesto (NLU)
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Comando original: <code className="text-cyan-300">"{pipeline.raw_text}"</code> &bull; Confianza: {(pipeline.confidence * 100).toFixed(0)}%
              </p>
            </div>
            {executionResult && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 text-xs font-medium font-mono">
                <CheckCircle2 className="w-3.5 h-3.5" /> Despacho Exitoso
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {pipeline.steps.map((step, idx) => {
              const execStep = executionResult?.executedSteps?.[idx];
              const isUrl = execStep?.targetType === 'url' || (execStep?.resolvedTarget && execStep.resolvedTarget.startsWith('http'));

              return (
                <div
                  key={idx}
                  className="rounded-xl border border-slate-800/90 bg-slate-950/70 p-3.5 hover:border-slate-700 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-xs font-mono text-slate-400">Paso #{idx + 1}</span>
                      <span className={`text-[11px] font-mono uppercase px-2 py-0.5 rounded border ${
                        step.intent === 'OPEN_APP'
                          ? 'bg-blue-950/60 text-blue-300 border-blue-800/60'
                          : step.intent === 'CREATE_PROJECT'
                          ? 'bg-purple-950/60 text-purple-300 border-purple-800/60'
                          : step.intent === 'FORGET_COMMAND'
                          ? 'bg-amber-950/60 text-amber-300 border-amber-800/60'
                          : 'bg-slate-800 text-slate-300 border-slate-700'
                      }`}>
                        {step.intent}
                      </span>
                    </div>

                    <div className="flex items-baseline gap-2 mb-1.5">
                      <span className="text-xs text-slate-400">Target:</span>
                      <span className="text-sm font-semibold text-white font-mono">{step.target}</span>
                    </div>

                    {step.parameters && (step.parameters.project_type !== 'none' || step.parameters.project_name) && (
                      <div className="mt-2 text-xs font-mono rounded bg-slate-900/90 p-2 border border-slate-800/60 text-slate-300 space-y-1">
                        <div className="flex items-center gap-1.5 text-purple-300 font-medium">
                          <FolderGit2 className="w-3.5 h-3.5" /> Parámetros de Proyecto:
                        </div>
                        <div className="pl-4">
                          <div>Tipo: <strong className="text-slate-100">{step.parameters.project_type}</strong></div>
                          <div>Nombre: <strong className="text-slate-100">{step.parameters.project_name}</strong></div>
                        </div>
                      </div>
                    )}
                  </div>

                  {execStep && (
                    <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center justify-between gap-2 text-xs">
                      <div className="text-slate-400 truncate font-mono">
                        <span className="text-slate-500">Resuelto:</span> <span className="text-cyan-300">{execStep.resolvedTarget}</span>
                      </div>
                      {isUrl && (
                        <a
                          href={execStep.resolvedTarget}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex-shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-300 text-xs font-mono transition-colors"
                        >
                          Abrir <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Terminal stdout logs box */}
      <div className="rounded-2xl border border-slate-800 bg-slate-950 p-4 shadow-lg">
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800 text-xs font-mono text-slate-400">
          <div className="flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            <span>Terminal de Ejecución V.ANSHEE (stdout / logs)</span>
          </div>
          <button
            onClick={() => setConsoleLogs(["=== V.ANSHEE Core [Consola Limpia] ==="])}
            className="hover:text-slate-200 transition-colors"
          >
            Limpiar consola
          </button>
        </div>

        <div className="max-h-48 overflow-y-auto space-y-1 font-mono text-xs text-slate-300">
          {consoleLogs.map((log, index) => {
            const isError = log.includes("[Error]") || log.includes("Falla");
            const isHabit = log.includes("[HabitEngine]");
            const isNlu = log.includes("[NLP") || log.includes("[NLU");
            const isExec = log.includes("[OSExecutor]");

            let color = "text-slate-300";
            if (isError) color = "text-rose-400";
            else if (isHabit) color = "text-emerald-400";
            else if (isNlu) color = "text-indigo-300";
            else if (isExec) color = "text-cyan-300";

            return (
              <div key={index} className={`${color} whitespace-pre-wrap leading-relaxed`}>
                {log}
              </div>
            );
          })}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  );
};
