import React, { useState, useEffect } from 'react';
import { Mic, Sparkles, BookOpen, History, Layers, RefreshCw } from 'lucide-react';
import { Header } from './components/Header';
import { VoiceConsole } from './components/VoiceConsole';
import { HabitEngineView } from './components/HabitEngineView';
import { LearnedCommandsView } from './components/LearnedCommandsView';
import { ExecutionLogsView } from './components/ExecutionLogsView';
import { ArchitectureDiagram } from './components/ArchitectureDiagram';
import { SystemStatus, DetectedRoutine, ExecutionLog, LearnedCommand } from './types';

export default function App() {
  const [activeTab, setActiveTab] = useState<'console' | 'habits' | 'commands' | 'logs' | 'architecture'>('console');
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [routines, setRoutines] = useState<DetectedRoutine[]>([]);
  const [suggestedRoutine, setSuggestedRoutine] = useState<DetectedRoutine | null>(null);
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [commands, setCommands] = useState<LearnedCommand[]>([]);
  const [knownTargets, setKnownTargets] = useState<Record<string, { target: string; type: 'url' | 'protocol' | 'app' }>>({});
  const [currentHour, setCurrentHour] = useState<number>(new Date().getHours());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchAllData = async () => {
    try {
      const [statusRes, routinesRes, logsRes, commandsRes] = await Promise.all([
        fetch('/api/status'),
        fetch('/api/routines'),
        fetch('/api/logs'),
        fetch('/api/commands')
      ]);

      if (statusRes.ok) {
        const sData = await statusRes.json();
        setStatus(sData);
        setCurrentHour(sData.current_hour);
      }

      if (routinesRes.ok) {
        const rData = await routinesRes.json();
        setRoutines(rData.routines || []);
        setSuggestedRoutine(rData.suggested || null);
      }

      if (logsRes.ok) {
        const lData = await logsRes.json();
        setLogs(lData.logs || []);
      }

      if (commandsRes.ok) {
        const cData = await commandsRes.json();
        setCommands(cData.commands || []);
        setKnownTargets(cData.knownTargets || {});
      }
    } catch (err) {
      console.error('Error al sincronizar datos de V.ANSHEE:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleExecuteFromOutside = async (commandText: string) => {
    try {
      const parseRes = await fetch('/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: commandText })
      });
      const parsed = await parseRes.json();
      await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pipeline: parsed })
      });
      fetchAllData();
      setActiveTab('console');
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-cyan-500/30 selection:text-cyan-200">
      <Header status={status} isListening={false} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Navigation Tabs Bar */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3 gap-2 overflow-x-auto">
          <nav className="flex items-center gap-2">
            <button
              id="tab-console"
              type="button"
              onClick={() => setActiveTab('console')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-mono font-medium transition-all ${
                activeTab === 'console'
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
              }`}
            >
              <Mic className="w-3.5 h-3.5" /> Consola & Voz
            </button>

            <button
              id="tab-habits"
              type="button"
              onClick={() => setActiveTab('habits')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-mono font-medium transition-all ${
                activeTab === 'habits'
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" /> Motor de Hábitos
              {routines.length > 0 && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full bg-cyan-950 text-cyan-400 text-[10px] border border-cyan-800">
                  {routines.length}
                </span>
              )}
            </button>

            <button
              id="tab-commands"
              type="button"
              onClick={() => setActiveTab('commands')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-mono font-medium transition-all ${
                activeTab === 'commands'
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" /> Resolver Dinámico
              {commands.length > 0 && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300 text-[10px]">
                  {commands.length}
                </span>
              )}
            </button>

            <button
              id="tab-logs"
              type="button"
              onClick={() => setActiveTab('logs')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-mono font-medium transition-all ${
                activeTab === 'logs'
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
              }`}
            >
              <History className="w-3.5 h-3.5" /> Historial
              {logs.length > 0 && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300 text-[10px]">
                  {logs.length}
                </span>
              )}
            </button>

            <button
              id="tab-architecture"
              type="button"
              onClick={() => setActiveTab('architecture')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-mono font-medium transition-all ${
                activeTab === 'architecture'
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
              }`}
            >
              <Layers className="w-3.5 h-3.5" /> Arquitectura
            </button>
          </nav>

          <button
            id="btn-refresh-data"
            type="button"
            onClick={fetchAllData}
            title="Sincronizar telemetría"
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-900 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Tab content view */}
        <div>
          {activeTab === 'console' && (
            <VoiceConsole onCommandExecuted={fetchAllData} />
          )}

          {activeTab === 'habits' && (
            <HabitEngineView
              routines={routines}
              suggestedRoutine={suggestedRoutine}
              logs={logs}
              currentHour={currentHour}
              onExecuteCommand={handleExecuteFromOutside}
              onRefresh={fetchAllData}
            />
          )}

          {activeTab === 'commands' && (
            <LearnedCommandsView
              commands={commands}
              knownTargets={knownTargets}
              onRefresh={fetchAllData}
            />
          )}

          {activeTab === 'logs' && (
            <ExecutionLogsView logs={logs} onRefresh={fetchAllData} />
          )}

          {activeTab === 'architecture' && (
            <ArchitectureDiagram />
          )}
        </div>
      </main>

      <footer className="border-t border-slate-900 py-4 mt-auto text-center text-xs font-mono text-slate-500">
        V.ANSHEE — Sistema de Control por Voz e Interpretación en Tiempo Real &bull; Duoc UC APT122
      </footer>
    </div>
  );
}
