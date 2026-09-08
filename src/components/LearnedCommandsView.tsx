import React, { useState } from 'react';
import { BookOpen, Plus, Trash2, Globe, Laptop, Terminal, ExternalLink, Check, AlertCircle } from 'lucide-react';
import { LearnedCommand } from '../types';

interface LearnedCommandsViewProps {
  commands: LearnedCommand[];
  knownTargets: Record<string, { target: string; type: 'url' | 'protocol' | 'app' }>;
  onRefresh: () => void;
}

export const LearnedCommandsView: React.FC<LearnedCommandsViewProps> = ({
  commands,
  knownTargets,
  onRefresh
}) => {
  const [keyword, setKeyword] = useState('');
  const [target, setTarget] = useState('');
  const [cmdType, setCmdType] = useState<'url' | 'protocol' | 'app'>('url');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword.trim() || !target.trim()) return;

    setIsSubmitting(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/commands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keyword: keyword.trim().toLowerCase(),
          execution_target: target.trim(),
          command_type: cmdType
        })
      });

      if (res.ok) {
        setKeyword('');
        setTarget('');
        setFeedback('Comando aprendido y guardado en memoria exitosamente.');
        onRefresh();
        setTimeout(() => setFeedback(null), 3000);
      }
    } catch {
      setFeedback('Error al guardar el comando aprendido.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (kw: string) => {
    try {
      const res = await fetch(`/api/commands/${encodeURIComponent(kw)}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        onRefresh();
      }
    } catch (err) {
      console.error('Error al olvidar comando:', err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Dynamic Resolver: Teach new command */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
        <div className="pb-3 border-b border-slate-800/80 mb-4">
          <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
            <Plus className="w-4 h-4 text-cyan-400" /> Enseñar Nuevo Comando a V.ANSHEE (Dynamic Resolver)
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Asocia una palabra clave personalizada a una URL web, protocolo o ruta de aplicación.
          </p>
        </div>

        {feedback && (
          <div className="mb-4 text-xs font-mono text-cyan-300 bg-cyan-950/40 border border-cyan-800/60 p-2.5 rounded-lg flex items-center gap-2">
            <Check className="w-3.5 h-3.5 text-cyan-400" /> {feedback}
          </div>
        )}

        <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-12 gap-3">
          <div className="sm:col-span-4">
            <label className="block text-xs font-mono text-slate-400 mb-1">Palabra Clave (Keyword):</label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="ej: correo, intranet, musica"
              className="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-2 text-xs font-mono text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
              required
            />
          </div>

          <div className="sm:col-span-5">
            <label className="block text-xs font-mono text-slate-400 mb-1">Target / Destino:</label>
            <input
              type="text"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="ej: https://mail.google.com o code"
              className="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-2 text-xs font-mono text-white placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
              required
            />
          </div>

          <div className="sm:col-span-3 flex items-end">
            <button
              type="submit"
              disabled={isSubmitting || !keyword.trim() || !target.trim()}
              className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 text-xs font-bold font-mono transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> Memorizar
            </button>
          </div>
        </form>
      </div>

      {/* Learned Commands list */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-cyan-400" /> Memoria Dinámica de Comandos ({commands.length})
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Comandos persistidos en la tabla <code className="text-slate-300">learned_commands</code>. Puedes decir "olvida [keyword]" para eliminarlos.
            </p>
          </div>
        </div>

        {commands.length === 0 ? (
          <div className="text-center py-6 text-slate-500 text-xs font-mono">
            No hay comandos personalizados aprendidos todavía.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {commands.map((cmd) => (
              <div
                key={cmd.id}
                className="rounded-xl border border-slate-800 bg-slate-950/70 p-3.5 flex flex-col justify-between hover:border-slate-700 transition-all"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="text-xs font-bold text-cyan-300 font-mono">
                      "{cmd.keyword}"
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 uppercase">
                      {cmd.command_type}
                    </span>
                  </div>
                  <div className="text-xs font-mono text-slate-300 truncate mb-2">
                    {cmd.execution_target}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-xs font-mono">
                  {cmd.execution_target.startsWith('http') ? (
                    <a
                      href={cmd.execution_target}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-cyan-400 hover:text-cyan-300 inline-flex items-center gap-1"
                    >
                      Abrir <ExternalLink className="w-3 h-3" />
                    </a>
                  ) : (
                    <span className="text-slate-500">Local OS</span>
                  )}

                  <button
                    type="button"
                    onClick={() => handleDelete(cmd.keyword)}
                    title="Olvidar comando"
                    className="text-slate-500 hover:text-rose-400 p-1 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Built-in Known Targets Catalog */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
        <div className="pb-3 border-b border-slate-800/80 mb-4">
          <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-cyan-400" /> Catálogo Nativo de Aplicaciones y Servicios (KNOWN_TARGETS)
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Mapeos predeterminados para Windows OS, servicios web y protocolos.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
          {Object.entries(knownTargets).map(([alias, item]) => {
            const isUrl = item.type === 'url';
            return (
              <div
                key={alias}
                className="rounded-lg border border-slate-800/80 bg-slate-950/60 p-2.5 text-xs font-mono flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between text-slate-300 font-medium">
                    <span className="truncate">{alias}</span>
                    <span className="text-[10px] text-slate-500">{item.type}</span>
                  </div>
                  <div className="text-[11px] text-slate-500 truncate mt-1">
                    {item.target}
                  </div>
                </div>
                {isUrl && (
                  <a
                    href={item.target}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 text-right text-[11px] text-cyan-400 hover:underline flex items-center justify-end gap-1"
                  >
                    Visitar <ExternalLink className="w-2.5 h-2.5" />
                  </a>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
