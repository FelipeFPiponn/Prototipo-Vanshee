import React from 'react';
import { Mic, Cpu, Terminal, Sparkles, ArrowRight, Layers, Bot, Database } from 'lucide-react';

export const ArchitectureDiagram: React.FC = () => {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
      <div className="flex items-center gap-2 pb-3 border-b border-slate-800/80 mb-4">
        <Layers className="w-4 h-4 text-cyan-400" />
        <h2 className="text-sm font-semibold text-slate-100">Arquitectura V.ANSHEE (Flujo de 4 Capas)</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        {/* Layer 1: STT */}
        <div className="rounded-xl border border-slate-800/90 bg-slate-950/80 p-3.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-cyan-400 uppercase font-semibold">Capa 1</span>
              <Mic className="w-4 h-4 text-cyan-400" />
            </div>
            <h3 className="text-xs font-bold text-white mb-1">Captura & STT</h3>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Módulo de audio en tiempo real. Conversión de voz a texto estructurado (Whisper STT / WebSpeech).
            </p>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-800/60 text-[10px] font-mono text-slate-500">
            audio_recorder.py &bull; stt_whisper.py
          </div>
        </div>

        {/* Layer 2: NLP Parser */}
        <div className="rounded-xl border border-slate-800/90 bg-slate-950/80 p-3.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-indigo-400 uppercase font-semibold">Capa 2</span>
              <Cpu className="w-4 h-4 text-indigo-400" />
            </div>
            <h3 className="text-xs font-bold text-white mb-1">Motor NLU / Parser</h3>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Descompone la intención en secuencias JSON ordenadas (OPEN_APP, CREATE_PROJECT, FORGET_COMMAND).
            </p>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-800/60 text-[10px] font-mono text-slate-500">
            intent_parser.py &bull; intents_schema.json
          </div>
        </div>

        {/* Layer 3: OS Dispatcher */}
        <div className="rounded-xl border border-slate-800/90 bg-slate-950/80 p-3.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-emerald-400 uppercase font-semibold">Capa 3</span>
              <Terminal className="w-4 h-4 text-emerald-400" />
            </div>
            <h3 className="text-xs font-bold text-white mb-1">Dispatcher OS / Resolver</h3>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Dynamic Resolver con auto-aprendizaje, indexación de accesos directos y llamada a procesos o protocolos.
            </p>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-800/60 text-[10px] font-mono text-slate-500">
            os_executor.py &bull; dynamic_resolver.py
          </div>
        </div>

        {/* Layer 4: Habit Engine */}
        <div className="rounded-xl border border-slate-800/90 bg-slate-950/80 p-3.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-amber-400 uppercase font-semibold">Capa 4</span>
              <Sparkles className="w-4 h-4 text-amber-400" />
            </div>
            <h3 className="text-xs font-bold text-white mb-1">Engine de Rutinas (ML)</h3>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Análisis estadístico de logs. Identifica patrones recurrentes (frecuencia ≥ 3) y predice sugerencias horarias.
            </p>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-800/60 text-[10px] font-mono text-slate-500">
            habit_engine.py &bull; routine_logger.py
          </div>
        </div>
      </div>
    </div>
  );
};
