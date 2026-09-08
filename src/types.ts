export type ActionIntent =
  | 'OPEN_APP'
  | 'CREATE_PROJECT'
  | 'SYSTEM_CONTROL'
  | 'FORGET_COMMAND'
  | 'UNKNOWN';

export interface StepParameters {
  project_type: 'python' | 'node' | 'react' | 'csharp' | 'none';
  project_name: string;
  path?: string;
  flags?: string[];
}

export interface ActionStep {
  intent: ActionIntent;
  target: string;
  parameters: StepParameters;
  resolvedTarget?: string;
  targetType?: 'url' | 'protocol' | 'app' | 'script' | 'unknown';
  status?: 'pending' | 'executing' | 'completed' | 'failed';
  message?: string;
}

export interface ParsedPipeline {
  raw_text: string;
  steps: ActionStep[];
  confidence: number;
}

export interface ExecutionLog {
  id: number;
  full_command: string;
  day_of_week: number;
  hour_of_day: number;
  executed_at: string;
  steps?: ActionStep[];
}

export interface DetectedRoutine {
  id: number;
  routine_name: string;
  sequence_json: string;
  trigger_hour: number;
  frequency: number;
}

export interface LearnedCommand {
  id: number;
  keyword: string;
  execution_target: string;
  command_type: 'url' | 'protocol' | 'app' | 'script';
  created_at: string;
}

export interface SystemStatus {
  wake_word: string;
  stt_model: string;
  llm_provider: string;
  active_listeners: boolean;
  total_commands: number;
  detected_routines_count: number;
  learned_commands_count: number;
}
