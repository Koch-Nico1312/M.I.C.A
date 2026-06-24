export type LiveMode = "LISTENING" | "SPEAKING" | "THINKING" | "API KEY ERROR" | string;

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  timestamp: string;
  tool?: string;
  args_summary?: string;
  result_summary?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  started_at: string;
  updated_at: string;
  ended_at?: string | null;
  summary?: string;
  status?: "active" | "completed" | string;
  preview?: string;
  message_count?: number;
  messages?: ChatMessage[];
}

export interface ResourceSummary {
  cpu_percent: number;
  memory_percent: number;
  memory_mb: number;
  disk_percent: number;
  threads: number;
  processes: number;
  uptime_seconds: number;
  performance: {
    active_tasks?: number;
    recent_alerts?: number;
    history_size?: number;
    waiting_for_input?: boolean;
    tool_active?: boolean;
    model_active?: boolean;
    current_activity?: string;
    activity_type?: string | null;
  };
  resource_trend?: Record<string, unknown> | { error?: string };
}

export interface DashboardSettings {
  ui: {
    default_view: string;
    voice_first: boolean;
  };
  calendar: {
    enabled: boolean;
    credentials_path: string;
    token_path: string;
  };
}

export interface CalendarStatus {
  enabled: boolean;
  configured: boolean;
  authenticated: boolean;
  credentials_path: string;
  token_path: string;
}

export interface DashboardResponse {
  state: {
    state: LiveMode;
    muted: boolean;
    speaking: boolean;
    current_file?: string | null;
    voice_focus: boolean;
    default_view: string;
    logs: Array<{ timestamp: number; text: string }>;
    session: ChatSession | null;
    recent_sessions: ChatSession[];
  };
  resources: ResourceSummary;
  settings: DashboardSettings;
  calendar: CalendarStatus;
  current_session: ChatSession | null;
  recent_sessions: ChatSession[];
  cockpit?: CockpitPayload;
  resume?: ResumePayload;
  documents?: DocumentsPayload;
}

export interface SessionPayload {
  session: ChatSession;
}

export interface CockpitItem {
  id: string;
  title: string;
  subtitle?: string;
  time?: string;
  status?: string;
  source?: string;
}

export interface CockpitPayload {
  calendar: {
    items: CockpitItem[];
    status: CalendarStatus;
  };
  weather: {
    summary: string;
    temperature?: string | null;
    condition?: string | null;
    location?: string | null;
  };
  mail: {
    open_count: number;
    items: CockpitItem[];
  };
  reminders: CockpitItem[];
  tasks: CockpitItem[];
  recent_activities: CockpitItem[];
  next_best_step: {
    title: string;
    reason?: string;
    action?: string;
  } | null;
}

export interface ResumePayload {
  last_activity: CockpitItem | null;
  open_ends: CockpitItem[];
  recent_files: CockpitItem[];
  summary: string;
  session: ChatSession | null;
}

export interface DocumentRecord {
  id: string;
  name: string;
  type: string;
  size: number;
  size_label: string;
  uploaded_at: string;
  path?: string;
  analysis?: string | null;
  indexed?: boolean;
  status?: string;
  error?: string | null;
}

export interface DocumentsPayload {
  files: DocumentRecord[];
  upload_dir?: string;
}

export interface UploadDocumentsResponse {
  status: string;
  files: DocumentRecord[];
  errors: Array<{ name: string; error: string }>;
  indexed: boolean;
}
