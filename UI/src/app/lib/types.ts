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

export interface VoiceTurn {
  role: "user" | "assistant" | "system";
  text: string;
  timestamp: string;
  source: string;
}

export interface VoiceConversationState {
  enabled: boolean;
  input_mode: "open_mic" | "push_to_talk" | "wakeword" | string;
  push_to_talk_active: boolean;
  wakeword_enabled: boolean;
  wakeword: string;
  last_transcript: string;
  last_response: string;
  last_interrupt_at?: string | null;
  turns: VoiceTurn[];
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
    background_id?: string;
    background_url?: string;
    voice_volume?: number;
    theme?: "dark" | "light" | string;
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

export interface ArtifactPanelItem {
  id: string;
  kind:
    | "menu"
    | "web"
    | "chart"
    | "note"
    | "table"
    | "code"
    | "progress"
    | string;
  title: string;
  content?: string;
  language?: string;
  columns?: string[];
  rows?: Array<Record<string, unknown>>;
  progress?: number;
  url?: string;
  path?: string;
  mime_type?: string;
  created_at: string;
}

export interface PersonalModePayload {
  enabled: boolean;
  owner_name: string;
  profile_id: string;
  local_first: boolean;
  glass_design: boolean;
  hidden_surfaces: string[];
  preferred_apps: string[];
  routines: string[];
  preferences: Record<string, unknown>;
}

export interface ActiveModePayload {
  id: "focus" | "coding" | "research" | "private" | "gaming" | "admin" | string;
  label: string;
  description: string;
  privacy_mode: string;
  trust_level: number;
  proactive_mode: string;
  status: string;
}

export interface TrustLevelPayload {
  level: number;
  label: string;
  description: string;
  permission_profile: string;
  rules: Array<{ action: string; policy: string }>;
}

export interface SilentBrainPayload {
  generated_at: string;
  critical_count: number;
  hint_count: number;
  summary: string;
  hints: CockpitItem[];
  critical: CockpitItem[];
  checks: Array<{ id: string; label: string; status: string; detail?: string }>;
}

export interface CommandPalettePayload {
  placeholder: string;
  examples: QuickActionPayload[];
  suggestions: QuickActionPayload[];
  modes: ActiveModePayload[];
}

export interface ArtifactPanelPayload {
  open: boolean;
  reason: string;
  items: ArtifactPanelItem[];
  tabs: Array<{ id: string; label: string; count: number }>;
}

export interface ProjectAwarenessPayload {
  active_project: ProjectWorkspacesPayload["active"] | null;
  relevant: CockpitItem[];
  todos: CockpitItem[];
  health: Array<{ id: string; label: string; status: string; detail?: string }>;
  next_three: CockpitItem[];
}

export interface LiveEventPayload {
  id: number;
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface TeachModePayload {
  recording: boolean;
  active: {
    id: string;
    name: string;
    started_at: string;
    steps: Array<{ id: string; tool: string; args: Record<string, unknown>; label: string }>;
  } | null;
  items: Array<{
    id: string;
    name: string;
    status: string;
    created_at: string;
    steps: Array<{ id: string; tool: string; args: Record<string, unknown>; label: string }>;
  }>;
}

export interface TaskGraphPayload {
  id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
  steps: Array<{
    id: string;
    tool: string;
    args: Record<string, unknown>;
    depends_on: string[];
    status: string;
    attempts: number;
    error?: string | null;
  }>;
}

export interface AIGovernorPayload {
  daily_budget_usd: number;
  daily_cost_usd_estimate: number;
  daily_tokens_estimate: number;
  budget_used_percent: number;
  budget_exceeded: boolean;
  local_first: boolean;
  recent_calls: Array<Record<string, unknown>>;
}

export interface FeatureHubPayload {
  teach_mode: TeachModePayload;
  task_graphs: { items: TaskGraphPayload[] };
  governor: AIGovernorPayload;
  live_events: { sequence: number; events: LiveEventPayload[] };
  evidence_mode: { enabled: boolean; endpoint: string };
}

export interface EvidencePayload {
  query: string;
  generated_at: string;
  citation_count: number;
  context: string;
  citations: Array<{
    id: string;
    title: string;
    content: string;
    excerpt: string;
    source: string;
    uri: string;
    score?: number | null;
  }>;
}

export interface DashboardResponse {
  revision?: string;
  state: {
    state: LiveMode;
    muted: boolean;
    speaking: boolean;
    current_file?: string | null;
    voice?: VoiceConversationState;
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
  command_center?: CommandCenterPayload;
  artifacts?: ArtifactPanelItem[];
  privacy?: PrivacyPayload;
  automations?: AutomationsPayload;
  project_workspaces?: ProjectWorkspacesPayload;
  learning_feedback?: LearningFeedbackPayload;
  plugins?: PluginsPayload;
  os_integrations?: OSIntegrationsPayload;
  personal_mode?: PersonalModePayload;
  active_mode?: ActiveModePayload;
  trust_level?: TrustLevelPayload;
  silent_brain?: SilentBrainPayload;
  command_palette?: CommandPalettePayload;
  artifact_panel?: ArtifactPanelPayload;
  project_awareness?: ProjectAwarenessPayload;
  features?: FeatureHubPayload;
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
  ingestion?: {
    queued: number;
    chunked: number;
    duplicates: number;
    errors: Array<{ id?: string; name?: string; error?: string }>;
  };
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

export interface CommandCenterStatusCard {
  id: string;
  label: string;
  value: string;
  status: "ok" | "degraded" | "blocked" | string;
  detail?: string;
}

export interface DailyBriefingItem {
  category: string;
  content: string;
  priority: string;
  source: string;
  time_cost_minutes: number;
  metadata: Record<string, unknown>;
}

export interface DailyBriefingPayload {
  status: "ready" | "degraded" | string;
  generated_at: string;
  date: string;
  kind: string;
  time_budget_minutes: number;
  focus: DailyBriefingItem[];
  items: DailyBriefingItem[];
  summary: string;
  error?: string;
}

export interface MemoryCurationSuggestion {
  id: string;
  kind: "duplicate" | "low_confidence" | string;
  title: string;
  confidence: number;
  entries: string[];
  recommendation: string;
}

export interface MemoryCurationPayload {
  entries: Array<{
    id: string;
    category: string;
    key: string;
    value: string;
    confidence: number;
    tags: string[];
    updated?: string | null;
  }>;
  suggestions: MemoryCurationSuggestion[];
  counts: Record<string, number>;
  error?: string;
}

export interface TaskPipelineStep {
  id: string;
  title: string;
  status: string;
  depends_on: string[];
  verification: Array<{ timestamp: string; status: string; note: string }>;
}

export interface TaskPipeline {
  id: string;
  goal: string;
  status: string;
  created_at: string;
  updated_at: string;
  steps: TaskPipelineStep[];
  requires_approval: boolean;
}

export interface TaskPipelinesPayload {
  pipelines: TaskPipeline[];
  active: TaskPipeline[];
  error?: string;
}

export interface KnowledgeGraphPayload {
  nodes: Array<{
    id: string;
    label: string;
    source: string;
    tags: string[];
    uri?: string;
    metadata?: Record<string, unknown>;
  }>;
  edges: Array<{ source: string; target: string; relation: string; evidence?: string }>;
  filters: { sources: string[]; tags: string[] };
  counts: { nodes: number; edges: number };
}

export interface NoteDraftPayload {
  id: string;
  title: string;
  markdown: string;
  tags: string[];
  sources: string[];
  links: string[];
  target_folder: string;
  status: string;
  duplicate_warning?: string;
  created_at: string;
}

export interface AutomationsPayload {
  items: Array<{
    id: string;
    name: string;
    action: string;
    schedule: string;
    enabled: boolean;
    last_run?: string | null;
    last_error?: string | null;
  }>;
  allowed_actions: string[];
}

export interface PrivacyPayload {
  mode: string;
  temporary_until?: string | null;
  updated_at: string;
  rules: Record<string, unknown>;
  modes: Record<string, Record<string, unknown>>;
}

export interface ProjectWorkspacesPayload {
  items: Array<{
    id: string;
    name: string;
    paths: string[];
    notes: string[];
    tags: string[];
    active: boolean;
    archived: boolean;
    created_at: string;
  }>;
  active?: ProjectWorkspacesPayload["items"][number] | null;
}

export interface LearningFeedbackPayload {
  records: Array<{
    id: string;
    rating: string;
    target: string;
    comment: string;
    correction: string;
    category: string;
    status: string;
    created_at: string;
  }>;
  counts: Record<string, number>;
}

export interface PluginsPayload {
  plugins_dir: string;
  loaded: string[];
  tools: Array<{ name: string; category: string; enabled: boolean; permissions: string[] }>;
  manifests: Array<{ id: string; name: string; enabled: boolean; permissions: string[]; entrypoint: string }>;
}

export interface OSIntegrationsPayload {
  os: string;
  actions: Record<string, { risk: string; requires_confirmation: boolean }>;
  records: Array<{ id: string; action: string; status: string; message: string; timestamp: string }>;
}

export interface CommandCenterPayload {
  generated_at: string;
  status_cards: CommandCenterStatusCard[];
  active_tasks: CockpitItem[];
  open_questions: CockpitItem[];
  recent_actions: ActionRecordPayload[];
  recent_files: CockpitItem[];
  warnings: CockpitItem[];
  day_overview: {
    calendar: CockpitItem[];
    reminders: CockpitItem[];
    tasks: CockpitItem[];
    next_best_step: CockpitPayload["next_best_step"];
    briefing?: DailyBriefingPayload;
  };
  quick_actions: QuickActionPayload[];
  task_pipelines?: TaskPipelinesPayload;
  privacy?: PrivacyPayload;
  automations?: AutomationsPayload;
  project_workspaces?: ProjectWorkspacesPayload;
  plugins?: PluginsPayload;
  os_integrations?: OSIntegrationsPayload;
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

export interface PlatformAgent {
  id: string;
  name: string;
  model: string;
  prompt: string;
  tools: string[];
  knowledge: string[];
  parameters: Record<string, number | string | boolean>;
  permissions?: string[];
  version?: string;
  visibility: string;
  owner: string;
  updated_at?: string;
}

export interface PlatformAgentPackage {
  id: string;
  agent_id: string;
  name: string;
  format: string;
  version: string;
  artifact_path: string;
  exported_at: string;
  tool_count: number;
  knowledge_count: number;
}

export interface PlatformUser {
  id: string;
  name: string;
  email: string;
  roles: string[];
  groups: string[];
}

export interface PlatformMarketplaceItem {
  id: string;
  name: string;
  kind: string;
  installed: boolean;
  version: string;
  latest_version?: string;
  trust: string;
  review_status?: string;
  enabled?: boolean;
  publisher?: string;
  permissions?: string[];
  risk?: { level: string; score: number; reasons?: string[]; permissions?: string[] };
  checksum?: string;
  signature?: string;
  source_url?: string;
  manifest?: Record<string, unknown>;
  verification?: { status: string; checks?: Array<{ name: string; status: string; detail?: string }> };
  description: string;
  entrypoint?: string;
  artifact_path?: string;
  manifest_path?: string;
  installed_at?: string;
  updated_at?: string;
  reviewed_at?: string;
  review_notes?: string;
}

export interface PlatformTool {
  id: string;
  name: string;
  kind: string;
  status: string;
  description?: string;
  code?: string;
  method?: string;
  path?: string;
  schema?: Record<string, unknown>;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  test_parameters?: Record<string, unknown>;
  test_result?: string;
  last_test?: Record<string, unknown>;
  server_url?: string;
  server_id?: string;
  loaded?: boolean;
  last_request_plan?: PlatformOpenApiRequestPlan;
}

export interface PlatformOpenApiRequestPlan {
  method: string;
  url: string;
  path: string;
  query: Record<string, unknown>;
  headers: Record<string, unknown>;
  body?: unknown;
}

export interface PlatformToolExecution {
  id: string;
  tool_id: string;
  status: string;
  request: PlatformOpenApiRequestPlan;
  response_preview: Record<string, unknown>;
  created_at: string;
}

export interface PlatformWorkflowNode {
  id: string;
  type: string;
  label: string;
  x?: number;
  y?: number;
  config?: Record<string, unknown>;
}

export interface PlatformWorkflow {
  id: string;
  name: string;
  nodes: PlatformWorkflowNode[];
  edges: string[][];
  canvas?: { zoom?: number; supports?: string[] };
  version?: number;
  versions?: Array<{ version: number; created_at: string; reason?: string; nodes: PlatformWorkflowNode[]; edges: string[][]; canvas?: Record<string, unknown> }>;
  status: string;
  trigger?: { type: string; enabled: boolean; webhook_path?: string; event?: string };
  schedule?: string;
  next_run?: string;
  last_scheduled_run?: string;
  updated_at?: string;
}

export interface PlatformRunStep {
  node: string;
  node_type?: string;
  status: string;
  input: string;
  input_snapshot?: Record<string, unknown>;
  output: string;
  output_snapshot?: Record<string, unknown>;
  latency_ms: number;
  retries: number;
  tool_calls?: Array<string | Record<string, unknown>>;
  incoming?: string[];
  outgoing?: string[];
  route_labels?: string[];
  branch_taken?: string | null;
  selected_route?: string;
  loop_iteration?: number;
  human_required?: boolean;
  retry_log?: string[];
  error?: string | null;
}

export interface PlatformRunEvent {
  id: string;
  run_id?: string;
  index: number;
  step_index?: number;
  type: string;
  node?: string;
  status: string;
  message: string;
  timestamp: string;
  payload?: Record<string, unknown>;
}

export interface PlatformRun {
  id: string;
  workflow_id: string;
  status: string;
  started_at: string;
  completed_at?: string;
  debug?: { edges?: string[][]; canvas?: Record<string, unknown>; supports?: string[]; timeline_events?: number; branch_attempts?: Record<string, number>; loop_counts?: Record<string, number>; human_decision?: string };
  steps: PlatformRunStep[];
  timeline?: PlatformRunEvent[];
}

export interface PlatformEvaluation {
  id: string;
  name: string;
  agents: string[];
  dataset: string;
  status: string;
  elo: Record<string, number>;
  regressions: number;
  last_score?: number;
  last_run?: string;
  baseline?: string;
  challenger?: string;
  regression_gate?: { min_score: number; max_regressions: number };
}

export interface PlatformEvaluationRun {
  id: string;
  evaluation_id: string;
  dataset: string;
  status: string;
  score: number;
  regressions: number;
  winner?: string;
  baseline?: string;
  challenger?: string;
  elo_delta?: Record<string, number>;
  gate?: { status: string; min_score: number; max_regressions: number };
  pairs?: Array<{ case_id: string; baseline: string; challenger: string; winner: string; loser?: string; margin: number }>;
  created_at: string;
  cases: Array<{ case_id: string; agent: string; score: number; winner: boolean; regression: boolean }>;
}

export interface PlatformEvaluationDataset {
  id: string;
  name: string;
  cases: Array<{ id: string; input: string; expected: string; rubric?: string }>;
}

export interface PlatformMetric {
  scope: string;
  model: string;
  tool?: string;
  user: string;
  agent?: string;
  workflow: string;
  tokens: number;
  cost: number;
  latency_ms: number;
  tool_calls: number;
}

export interface PlatformMetricAggregate {
  dimension: string;
  key: string;
  tokens: number;
  cost: number;
  latency_ms: number;
  avg_latency_ms: number;
  tool_calls: number;
  count: number;
}

export interface PlatformKnowledgeSource {
  id: string;
  source: string;
  target: string;
  uri?: string;
  status: string;
  last_sync: string;
  rag: string;
  vector_db: string;
  schedule?: string;
  next_sync?: string;
  watch_mode?: boolean;
  connector_status?: string;
  last_run_id?: string;
}

export interface PlatformKnowledgeRun {
  id: string;
  source_id: string;
  source: string;
  target: string;
  status: string;
  started_at: string;
  completed_at: string;
  rag: string;
  vector_db: string;
  phases: Array<{ name: string; status: string; items: number; latency_ms: number }>;
  documents?: number;
  chunks?: number;
  index?: { bm25_terms: number; vectors: number; reranker: string };
}

export interface PlatformKnowledgeSchedulerRun {
  id: string;
  status: string;
  started_at: string;
  completed_at: string;
  checked_sources: number;
  synced_sources: number;
  runs: string[];
}

export interface PlatformKnowledgeSearch {
  id: string;
  query: string;
  source_ids: string[];
  status: string;
  retrieval: string;
  created_at: string;
  results: Array<{
    source_id: string;
    chunk_id: string;
    document_id: string;
    text: string;
    bm25_score: number;
    vector_score: number;
    rerank_score: number;
    metadata?: Record<string, unknown>;
  }>;
}

export interface PlatformIdentityProvider {
  id: string;
  name: string;
  type: string;
  status: string;
  issuer?: string;
  client_id?: string;
  audience?: string;
  jwks_uri?: string;
  authorization_endpoint?: string;
  token_endpoint?: string;
  allowed_algs?: string[];
  jwks?: { keys?: Array<Record<string, unknown>> };
  ldap_url?: string;
  scim_enabled: boolean;
  last_test?: string | null;
}

export interface PlatformScimEvent {
  id: string;
  action: string;
  user_id: string;
  email: string;
  status: string;
  timestamp: string;
}

export interface PlatformSubagent {
  id: string;
  name: string;
  parent: string;
  role: string;
  status: string;
}

export interface PlatformAgentChainRun {
  id: string;
  agent_id: string;
  goal: string;
  status: string;
  compact_result: string;
  created_at: string;
  budget?: { max_tokens: number; max_cost: number; used_tokens: number; used_cost: number; reason?: string };
  steps: Array<{
    subagent_id: string;
    name: string;
    role: string;
    status: string;
    input: string;
    output: string;
    tokens_in: number;
    tokens_out: number;
  }>;
}

export interface PlatformSoloQuickstart {
  id: string;
  status: string;
  agent_id: string;
  artifact_id: string;
  created_at: string;
  links: Record<string, string>;
  summary?: {
    title?: string;
    agent_output?: string;
    knowledge_results?: number;
    ingested_documents?: number;
    sandbox_stdout?: string;
    workflow_status?: string;
    artifact_id?: string;
  };
  next_actions?: Array<{ label: string; href?: string; target?: string; kind: string }>;
}

export interface PlatformSoloAudit {
  id: string;
  status: string;
  workspace_name: string;
  ready_count: number;
  optional_count: number;
  blocking_count: number;
  total_count: number;
  created_at: string;
  items: Array<{
    id: string;
    label: string;
    status: string;
    evidence: string[];
    recommendation: string;
    verified: boolean;
  }>;
}

export interface PlatformArtifact {
  id: string;
  title: string;
  kind: string;
  content: string;
  version?: number;
  versions?: Array<{ version: number; created_at: string; content: string }>;
  render_status?: string;
  dependencies?: string[];
  created_by?: string;
  last_render?: { artifact_id: string; kind: string; version: number; status: string; mime: string; preview: string; updated_at: string };
  updated_at: string;
}

export interface PlatformExtractionRun {
  id: string;
  engine: string;
  status: string;
  started_at: string;
  completed_at: string;
  artifact_dir: string;
  artifact_id?: string;
  engine_config?: Record<string, unknown>;
  batch_size: number;
  diagnostics?: {
    documents_total: number;
    documents_review: number;
    tables_total: number;
    layout_blocks_total: number;
    ocr_spans_total: number;
    rag_ready: boolean;
    warnings: string[];
  };
  documents: Array<{
    id: string;
    name: string;
    status: string;
    pages: number;
    tables: number;
    ocr: boolean;
    ocr_confidence?: number;
    ocr_spans?: number;
    layout_blocks?: number;
    quality?: string;
    warnings?: string[];
    quality_gates?: Array<{ name: string; status: string; value?: unknown; threshold?: number }>;
    rag_ready?: boolean;
    rerank_features?: Record<string, unknown>;
    text_path: string;
    tables_path: string;
    layout_path: string;
    searchable_path?: string;
    report_path?: string;
  }>;
}

export interface PlatformSandboxArtifact {
  kind: string;
  path: string;
  title: string;
}

export interface PlatformSandboxRun {
  id: string;
  language: string;
  code: string;
  started_at: string;
  completed_at?: string;
  status: string;
  stdout: string;
  stderr: string;
  uploaded_files?: Array<{ name: string; size?: number; original_size?: number; truncated?: boolean; rejected?: boolean }>;
  policy?: Record<string, unknown>;
  limits?: Record<string, unknown>;
  artifacts: PlatformSandboxArtifact[];
}

export interface PlatformAuditEvent {
  id: string;
  action: string;
  user: string;
  permission: string;
  resource: string;
  status: string;
  timestamp: string;
  error?: string;
}

export interface PlatformPayload {
  solo?: {
    enabled: boolean;
    owner_user: string;
    workspace_name: string;
    local_only: boolean;
    status: string;
    updated_at?: string;
  };
  solo_status?: {
    enabled: boolean;
    owner_user: string;
    workspace_name: string;
    local_only: boolean;
    status: string;
    ready_count: number;
    total_count: number;
    optional_count?: number;
    blocking_count?: number;
    updated_at?: string;
    checklist: Array<{ id: string; label: string; status: string }>;
  };
  users: PlatformUser[];
  groups: Array<{ id: string; name: string; members: string[] }>;
  roles: Array<{ id: string; permissions: string[] }>;
  acls: Array<Record<string, unknown>>;
  secret_references?: Array<{ id: string; name: string; env_var: string; scope: string; status: string; updated_at: string }>;
  integration_checks?: Array<{ id: string; category: string; integration_id: string; status: string; detail: string; checked_at: string }>;
  audit_events?: PlatformAuditEvent[];
  agents: PlatformAgent[];
  agent_runs?: PlatformAgentRun[];
  invocations?: PlatformAgentInvocation[];
  agent_packages?: PlatformAgentPackage[];
  marketplace: PlatformMarketplaceItem[];
  marketplace_policy?: {
    require_review?: boolean;
    require_signature?: boolean;
    allowed_trust?: string[];
    max_risk?: string;
    permission_denylist?: string[];
    trusted_publishers?: string[];
  };
  marketplace_audit?: Array<{ id: string; action: string; item_id?: string; status: string; timestamp: string; details?: Record<string, unknown> }>;
  tools: PlatformTool[];
  mcp: { deferred: boolean; last_query: string; tools: PlatformTool[]; loaded_tools: PlatformTool[]; servers: Array<Record<string, unknown>> };
  tool_executions?: PlatformToolExecution[];
  workflows: PlatformWorkflow[];
  runs: PlatformRun[];
  evaluations: PlatformEvaluation[];
  evaluation_datasets: PlatformEvaluationDataset[];
  evaluation_runs: PlatformEvaluationRun[];
  metrics: PlatformMetric[];
  metric_events?: PlatformMetric[];
  metrics_aggregate?: Record<string, PlatformMetricAggregate[]>;
  knowledge: PlatformKnowledgeSource[];
  knowledge_runs: PlatformKnowledgeRun[];
  knowledge_scheduler_runs?: PlatformKnowledgeSchedulerRun[];
  knowledge_searches?: PlatformKnowledgeSearch[];
  extraction: {
    engines?: string[];
    engine_config?: Record<string, Record<string, unknown>>;
    batch_queue?: Array<{ id: string; name: string; engine: string; status: string; queued_at: string; started_at?: string; completed_at?: string }>;
    runs?: PlatformExtractionRun[];
    tables?: boolean;
    layouts?: boolean;
    scans?: boolean;
    artifact_dir?: string;
    last_run_id?: string;
  };
  artifacts: PlatformArtifact[];
  sandbox: {
    enabled: boolean;
    languages: string[];
    runs: PlatformSandboxRun[];
    artifact_dir?: string;
    policy?: Record<string, unknown>;
    audit?: Array<{ id: string; run_id?: string; language: string; status: string; blocked: boolean; uploaded_files: number; artifact_count: number; timestamp: string }>;
  };
  publishing: Array<{
    id: string;
    agent_id: string;
    kind: string;
    status: string;
    url: string;
    policy?: {
      auth?: string;
      cors?: string[];
      rate_limit_per_minute?: number;
      allowed_groups?: string[];
      secret_refs?: string[];
      api_key_count?: number;
      api_keys?: Array<{ id: string; name?: string; status: string; created_at?: string; last_used_at?: string }>;
      audit_invocations?: boolean;
    };
    artifact_path?: string;
    updated_at?: string;
  }>;
  deployment: Record<string, unknown>;
  sso: Record<string, unknown>;
  identity_providers: PlatformIdentityProvider[];
  scim_events: PlatformScimEvent[];
  subagents: PlatformSubagent[];
  agent_chain_runs: PlatformAgentChainRun[];
  solo_quickstarts?: PlatformSoloQuickstart[];
  solo_audits?: PlatformSoloAudit[];
  companion: Record<string, unknown>;
  counts: Record<string, number>;
  updated_at: string;
}

export interface PlatformAgentRunLog {
  timestamp: string;
  level: string;
  message: string;
}

export interface PlatformAgentRun {
  id: string;
  agent_id: string;
  agent_name: string;
  assignment: string;
  status: string;
  model: string;
  started_at: string;
  updated_at: string;
  completed_at?: string;
  logs: PlatformAgentRunLog[];
  result: string;
}

export interface PlatformAgentInvocation {
  id: string;
  agent_id: string;
  status: string;
  input: string;
  output: string;
  tool_plan: string[];
  created_at: string;
}
