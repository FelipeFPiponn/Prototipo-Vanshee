import React from 'react';
import { Sparkles, Clock, Play, BarChart3, Zap, Calendar, ArrowRight } from 'lucide-react';
import { DetectedRoutine, ExecutionLog } from '../types';

interface HabitEngineViewProps {
  routines: DetectedRoutine[];
  suggestedRoutine: DetectedRoutine | null;
  logs: ExecutionLog[];
  currentHour: number;
  onExecuteCommand: (command: string) => void;
  onRefresh: () => void;
}

export const HabitEngineView: React.FC<HabitEngineViewProps> = ({
  routines,
  suggestedRoutine,
  logs,
  currentHour,
  onExecuteCommand,
  onRefresh
}) => {
  // Compute hourly command frequencies for 24h distribution chart
  const hourlyFrequencies = Array.from({ length: 24 }, (_, h) => {
    const count = logs.filter((log) => log.hour_of_day === h).length;
    return { hour: h, count };
  });

  const maxCount = Math.max(1, ...hourlyFrequencies.map((d) => d.count));

  const simulateAddHabit = async () => {
    const sampleCommand = "ejecutar terminal y abrir github";
    // Send 3 requests to trigger count >= 3 in HabitEngine
    for (let i = 0; i < 3; i++) {
      const parseRes = await fetch('/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: sampleCommand })
      });
      const parsed = await parseRes.json();
      await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pipeline: parsed })
      });
    }
    onRefresh();
  };

  return (
    <div className="space-y-6">
      {/* Active Suggested Routine Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/40 via-slate-900 to-indigo-950/30 p-5 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="flex h-2.5 w-2.5 rounded-full bg-cyan-400 animate-ping"></span>
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-cyan-400">
                Predicción de Hábito en Tiempo Real
              </span>
            </div>
            <h2 className="text-base sm:text-lg font-bold text-white">
              {suggestedRoutine ? (
                <span>
                  Rutina Sugerida para las <span className="text-cyan-300 font-mono">~{currentHour}:00 hrs</span>:
                </span>
              ) : (
                <span>Sin rutina dominante en este bloque horario</span>
              )}
            </h2>
            <p className="text-xs text-slate-300">
              {suggestedRoutine ? (
                <>Secuencia detectada: <code className="text-cyan-200 font-mono bg-slate-950/60 px-2 py-0.5 rounded">"{suggestedRoutine.sequence_json}"</code> (frecuencia: {suggestedRoutine.frequency} repeticiones)</>
              ) : (
                <>El motor aprende automáticamente tus hábitos cuando ejecutas un comando 3 o más veces en el mismo bloque horario.</>
              )}
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            {suggestedRoutine ? (
              <button
                type="button"
                onClick={() => onExecuteCommand(suggestedRoutine.sequence_json)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-bold font-mono transition-all shadow-lg shadow-cyan-500/20"
              >
                <Play className="w-3.5 h-3.5 fill-current" /> Ejecutar Rutina Ahora
              </button>
            ) : (
              <button
                type="button"
                onClick={simulateAddHabit}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono transition-all border border-slate-700"
              >
                <Zap className="w-3.5 h-3.5 text-cyan-400" /> Simular Registro de Patrón
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Detected Routines Grid */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-cyan-400" /> Catálogo de Rutinas y Patrones Aprendidos
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Identificación estadística de secuencias recurrentes (HabitEngine ML).
            </p>
          </div>
          <button
            type="button"
            onClick={simulateAddHabit}
            className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
          >
            <Zap className="w-3 h-3" /> Probar patrón x3
          </button>
        </div>

        {routines.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-xs font-mono">
            No se han consolidado rutinas todavía. Realiza comandos compuestos para que el motor detecte tus secuencias.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {routines.map((routine) => (
              <div
                key={routine.id}
                className="rounded-xl border border-slate-800 bg-slate-950/70 p-4 hover:border-slate-700 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-xs font-semibold text-slate-200 font-mono truncate">
                      {routine.routine_name}
                    </span>
                    <span className="flex-shrink-0 text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800/60">
                      {routine.frequency} ejecuciones
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 font-mono bg-slate-900/90 p-2.5 rounded-lg border border-slate-800/80 mb-3">
                    "{routine.sequence_json}"
                  </p>

                  <div className="flex items-center gap-2 text-xs text-slate-400 font-mono mb-3">
                    <Clock className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Disparador habitual: ~{routine.trigger_hour}:00 hrs</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => onExecuteCommand(routine.sequence_json)}
                  className="w-full mt-2 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-cyan-950/80 hover:text-cyan-300 hover:border-cyan-700 border border-slate-700/80 text-slate-200 text-xs font-mono transition-all"
                >
                  <Play className="w-3 h-3" /> Despachar esta rutina
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Hourly Habit Distribution Chart */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-cyan-400" /> Distribución Horaria de Comandos (00:00 - 23:00)
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Muestra las horas del día con mayor concentración de instrucciones.
            </p>
          </div>
          <span className="text-xs font-mono text-slate-400">
            Total registros: <strong className="text-white">{logs.length}</strong>
          </span>
        </div>

        {/* 24-hour bar visualization */}
        <div className="grid grid-cols-12 sm:grid-cols-24 gap-1 items-end h-28 pt-4 pb-2 border-b border-slate-800">
          {hourlyFrequencies.map(({ hour, count }) => {
            const heightPercent = Math.round((count / maxCount) * 100);
            const isCurrent = hour === currentHour;

            return (
              <div key={hour} className="flex flex-col items-center h-full justify-end group relative">
                <div
                  style={{ height: `${Math.max(6, heightPercent)}%` }}
                  className={`w-full rounded-t transition-all ${
                    isCurrent
                      ? 'bg-cyan-400 shadow-lg shadow-cyan-400/30'
                      : count > 0
                      ? 'bg-indigo-500/70 group-hover:bg-indigo-400'
                      : 'bg-slate-800/50'
                  }`}
                  title={`${hour}:00 hrs: ${count} comando(s)`}
                />
              </div>
            );
          })}
        </div>

        <div className="flex justify-between text-[10px] font-mono text-slate-500 pt-1">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>23:00</span>
        </div>
      </div>
    </div>
  );
};
