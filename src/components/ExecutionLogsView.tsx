import React from 'react';
import { History, Trash2, Clock, Calendar, CheckCircle2, ChevronRight } from 'lucide-react';
import { ExecutionLog } from '../types';

interface ExecutionLogsViewProps {
  logs: ExecutionLog[];
  onRefresh: () => void;
}

const DAY_NAMES = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];

export const ExecutionLogsView: React.FC<ExecutionLogsViewProps> = ({ logs, onRefresh }) => {
  const handleClear = async () => {
    if (!window.confirm('¿Deseas reiniciar el historial de ejecuciones de V.ANSHEE?')) return;
    try {
      await fetch('/api/logs/clear', { method: 'POST' });
      onRefresh();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
        <div>
          <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
            <History className="w-4 h-4 text-cyan-400" /> Historial de Ejecuciones Registradas ({logs.length})
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Registro cronológico utilizado por el motor para correlacionar hábitos diarios y horarios.
          </p>
        </div>
        {logs.length > 0 && (
          <button
            type="button"
            onClick={handleClear}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 border border-rose-800/60 text-rose-300 text-xs font-mono transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" /> Limpiar Historial
          </button>
        )}
      </div>

      {logs.length === 0 ? (
        <div className="text-center py-10 text-slate-500 text-xs font-mono">
          No hay registros de ejecución todavía. Emite un comando por voz o texto para iniciar el seguimiento.
        </div>
      ) : (
        <div className="space-y-2.5 max-h-[520px] overflow-y-auto pr-1">
          {logs.map((log) => {
            const dateObj = new Date(log.executed_at);
            const timeStr = dateObj.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
            const dayName = DAY_NAMES[log.day_of_week] || 'Día';

            return (
              <div
                key={log.id}
                className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-slate-700 transition-all font-mono"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-white">"{log.full_command}"</span>
                  </div>

                  {log.steps && log.steps.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {log.steps.map((step, idx) => (
                        <span
                          key={idx}
                          className="text-[10px] px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300 flex items-center gap-1"
                        >
                          <ChevronRight className="w-2.5 h-2.5 text-cyan-400" />
                          <strong className="text-cyan-300">{step.intent}</strong>: {step.target}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex sm:flex-col sm:items-end justify-between text-xs text-slate-400 flex-shrink-0">
                  <div className="flex items-center gap-1.5 text-slate-300">
                    <Clock className="w-3 h-3 text-cyan-400" />
                    <span>{timeStr}</span>
                    <span className="text-slate-500">({log.hour_of_day}:00 hrs)</span>
                  </div>
                  <div className="flex items-center gap-1 text-slate-500 text-[11px]">
                    <Calendar className="w-3 h-3" />
                    <span>{dayName}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
