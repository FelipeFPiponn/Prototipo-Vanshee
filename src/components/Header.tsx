import React from 'react';
import { Mic, Activity, Cpu, Clock, Terminal } from 'lucide-react';
import { SystemStatus } from '../types';

interface HeaderProps {
  status: SystemStatus | null;
  isListening: boolean;
}

export const Header: React.FC<HeaderProps> = ({ status, isListening }) => {
  const [timeString, setTimeString] = React.useState<string>('');

  React.useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeString(now.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        {/* Brand identity */}
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shadow-sm shadow-cyan-500/10">
            <Terminal className="w-5 h-5" />
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
                V.ANSHEE <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">Core v1.0</span>
              </h1>
            </div>
            <p className="text-xs text-slate-400">
              Control por Voz &bull; Procesamiento NLU &bull; Motor de Rutinas
            </p>
          </div>
        </div>

        {/* Real-time telemetry indicators */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-xs font-mono">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span>{timeString || '--:--:--'}</span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300">
            <Cpu className="w-3.5 h-3.5 text-indigo-400" />
            <span className="hidden sm:inline">NLU:</span>
            <span className="text-slate-200 font-semibold">{status?.llm_provider || 'Local NLU'}</span>
          </div>

          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all ${
            isListening
              ? 'bg-rose-950/40 border-rose-500/50 text-rose-300'
              : 'bg-slate-800/60 border-slate-700/60 text-slate-300'
          }`}>
            <Mic className={`w-3.5 h-3.5 ${isListening ? 'animate-pulse text-rose-400' : 'text-slate-400'}`} />
            <span>Wake: <strong className="text-slate-200">{status?.wake_word || 'v_anshee'}</strong></span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-400">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span>Listo</span>
          </div>
        </div>
      </div>
    </header>
  );
};
