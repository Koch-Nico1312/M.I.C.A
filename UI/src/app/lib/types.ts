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
  model_router?: {
    preferred_profile: string;
    model_scope: "linked" | "all" | string;
    cost_mode: string;
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
  setup?: SetupPayload;
  models?: ModelsPayload;
  memory?: MemoryPayload;
  devices?: DevicesPayload;
  action_history?: ActionHistoryPayload;
  approvals?: ApprovalsPayload;
  permissions?: PermissionsPayload;
  reliability?: ReliabilityPayload;
  quick_actions?: QuickActionsPayload;
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

export interface SetupPayload {
  configured: boolean;
  api_keys_path: string;
  example_path: string;
  has_gemini_key: boolean;
  has_openai_key: boolean;
  ollama_base_url: string;
  settings: DashboardSettings;
}

export interface ModelProfilePayload {
  name: string;
  model_id: string;
  provider: string;
  capabilities: string[];
  context_window: number;
  cost_tier: string;
  latency_tier: string;
  enabled: boolean;
  linked: boolean;
}

export interface ModelsPayload {
  scope: "linked" | "all" | string;
  preferred_profile: string;
  models: ModelProfilePayload[];
  all_models: ModelProfilePayload[];
  linked_models: ModelProfilePayload[];
}

export interface MemoryEntry {
  id: string;
  category: string;
  key: string;
  value: string;
  metadata: Record<string, unknown>;
  updated?: string | null;
  created?: string | null;
  tags?: string[];
}

export interface MemoryPayload {
  categories: string[];
  entries: MemoryEntry[];
  raw: Record<string, unknown>;
  path?: string;
  error?: string;
}

export interface DeviceRecord {
  id: string;
  name: string;
  status: string;
  kind?: string;
  os?: string;
  python?: string;
  pid?: number;
  process?: string;
  last_seen?: string;
  started_at?: string;
}

export interface DevicesPayload {
  current: DeviceRecord;
  items: DeviceRecord[];
}

export interface ActionRecordPayload {
  id: string;
  action_type: string;
  tool_name: string;
  action: string;
  parameters: Record<string, unknown>;
  result: string;
  status: string;
  timestamp: string;
  can_undo: boolean;
  undo_plan?: Record<string, unknown> | null;
}

export interface ActionHistoryPayload {
  records: ActionRecordPayload[];
  undoable: ActionRecordPayload[];
  stats: Record<string, unknown>;
  error?: string;
}

export interface ApprovalPayload {
  tool_name: string;
  action: string;
  permission_level: string;
  reason: string;
  risk_level: string;
  status: string;
  timestamp: string;
  summary: string;
  context?: Record<string, unknown>;
}

export interface ApprovalsPayload {
  permission_level: string;
  pending: ApprovalPayload[];
  error?: string;
}

export interface PermissionToolPayload {
  name: string;
  description: string;
  risk_level: string;
  requires_confirmation: boolean;
  requires_permission: boolean;
  reversible: boolean;
  tags: string[];
  enabled: boolean;
}

export interface PermissionsPayload {
  tools: PermissionToolPayload[];
  disabled_actions: string[];
  error?: string;
}

export interface QuickActionPayload {
  id: string;
  label: string;
  command: string;
}

export interface QuickActionsPayload {
  items: QuickActionPayload[];
}

export interface ReliabilityCheckPayload {
  name: string;
  status: "ok" | "degraded" | "blocked" | string;
  message: string;
  detail: Record<string, unknown>;
}

export interface ReliabilityPayload {
  status: "ok" | "degraded" | "blocked" | string;
  generated_at?: string;
  counts: Record<string, number>;
  checks: ReliabilityCheckPayload[];
  recommendations: string[];
  error?: string;
}
