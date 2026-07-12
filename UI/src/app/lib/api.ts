import type {
  CockpitPayload,
  CommandCenterPayload,
  DashboardResponse,
  DocumentsPayload,
  KnowledgeGraphPayload,
  LearningFeedbackPayload,
  MemoryCurationPayload,
  MemoryPayload,
  ModelsPayload,
  ActionHistoryPayload,
  ActiveModePayload,
  AutomationsPayload,
  ApprovalsPayload,
  ArtifactPanelPayload,
  CommandPalettePayload,
  DevicesPayload,
  NoteDraftPayload,
  OSIntegrationsPayload,
  PermissionsPayload,
  PersonalModePayload,
  PluginsPayload,
  PrivacyPayload,
  ProjectAwarenessPayload,
  ProjectStatePayload,
  ProjectSnapshotsPayload,
  ProjectWorkspacesPayload,
  SupervisorAutomationPayload,
  ReliabilityPayload,
  PlatformPayload,
  ResumePayload,
  SessionPayload,
  SilentBrainPayload,
  SetupPayload,
  TaskPipelinesPayload,
  TrustLevelPayload,
  UploadDocumentsResponse,
  VoiceConversationState,
  AIGovernorPayload,
  EvidencePayload,
  FeatureHubPayload,
  LiveEventPayload,
  TeachModePayload,
} from "./types";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const response = await fetch(path, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      ...init,
    });

    const text = await response.text();
    let body: any = {};
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = { raw: text };
      }
    }

    if (!response.ok) {
      const message = body?.error || body?.message || `Request failed: ${response.status}`;
      throw new Error(message);
    }

    return body as T;
  } catch (error) {
    // Return mock data if backend is not available
    console.warn("Backend not available, using mock data:", error);
    return getMockData<T>(path);
  }
}

async function uploadRequest<T>(path: string, formData: FormData): Promise<T> {
  try {
    const response = await fetch(path, {
      method: "POST",
      body: formData,
    });

    const text = await response.text();
    let body: any = {};
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = { raw: text };
      }
    }

    if (!response.ok) {
      const message = body?.error || body?.message || `Request failed: ${response.status}`;
      throw new Error(message);
    }

    return body as T;
  } catch (error) {
    console.warn("Upload failed:", error);
    throw error;
  }
}

async function strictRequestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  const text = await response.text();
  let body: any = {};
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { raw: text };
    }
  }

  if (!response.ok) {
    const message = body?.error || body?.message || `Request failed: ${response.status}`;
    throw new Error(message);
  }

  return body as T;
}

function getMockData<T>(path: string): T {
  const mockDashboard: DashboardResponse = {
    state: {
      state: "LISTENING",
      muted: false,
      speaking: false,
      voice_focus: true,
      voice: {
        enabled: true,
        input_mode: "open_mic",
        push_to_talk_active: true,
        wakeword_enabled: false,
        wakeword: "mica",
        last_transcript: "",
        last_response: "",
        last_interrupt_at: null,
        turns: [],
      },
      default_view: "voice-chat",
      current_file: null,
      logs: [],
      session: null,
      recent_sessions: [],
    },
    resources: {
      cpu_percent: 25.5,
      memory_percent: 45.2,
      disk_percent: 62.8,
      memory_mb: 16384,
      threads: 8,
      processes: 150,
      uptime_seconds: 3600,
      performance: {
        active_tasks: 2,
        recent_alerts: 0,
        history_size: 100,
        waiting_for_input: false,
        tool_active: false,
        model_active: false,
        current_activity: "idle",
        activity_type: null,
      },
    },
    settings: {
      ui: {
        default_view: "voice-chat",
        voice_first: true,
        background_id: "lake",
        background_url: "/backgrounds/mica-lake.jpg",
        voice_volume: 82,
        theme: "dark",
      },
      calendar: {
        enabled: false,
        credentials_path: "",
        token_path: "",
      },
    },
    calendar: {
      enabled: false,
      configured: false,
      authenticated: false,
      credentials_path: "",
      token_path: "",
    },
    current_session: null,
    recent_sessions: [],
    cockpit: {
      calendar: {
        items: [],
        status: {
          enabled: false,
          configured: false,
          authenticated: false,
          credentials_path: "",
          token_path: "",
        },
      },
      weather: {
        summary: "Keine Wetterdaten",
        temperature: null,
        condition: null,
        location: null,
      },
      mail: {
        open_count: 0,
        items: [],
      },
      reminders: [],
      tasks: [],
      recent_activities: [],
      next_best_step: null,
    },
    resume: {
      last_activity: null,
      open_ends: [],
      recent_files: [],
      summary: "",
      session: null,
    },
    documents: {
      files: [],
    },
    setup: {
      configured: false,
      api_keys_path: "config/api_keys.json",
      example_path: "config/api_keys.example.json",
      has_gemini_key: false,
      has_openai_key: false,
      ollama_base_url: "http://localhost:11434",
      settings: {
        ui: {
          default_view: "voice-chat",
          voice_first: true,
          background_id: "lake",
          background_url: "/backgrounds/mica-lake.jpg",
          voice_volume: 82,
          theme: "dark",
        },
        calendar: {
          enabled: false,
          credentials_path: "",
          token_path: "",
        },
        model_router: {
          preferred_profile: "fast",
          model_scope: "linked",
          cost_mode: "balanced",
        },
      },
    },
    models: {
      scope: "linked",
      preferred_profile: "fast",
      models: [],
      all_models: [],
      linked_models: [],
    },
    memory: {
      categories: [],
      entries: [],
      raw: {},
    },
    devices: {
      current: {
        id: "local",
        name: "Local device",
        status: "online",
      },
      items: [],
    },
    action_history: {
      records: [],
      undoable: [],
      stats: {},
    },
    approvals: {
      permission_level: "normal",
      pending: [],
    },
    permissions: {
      tools: [
        { name: "summarize_text", description: "Text lokal zusammenfassen", risk_level: "low", requires_confirmation: false, requires_permission: false, reversible: true, tags: ["text"], enabled: true },
        { name: "nonempty_text", description: "Leere Eingaben abweisen", risk_level: "low", requires_confirmation: false, requires_permission: false, reversible: true, tags: ["filter"], enabled: true },
        { name: "normalize_text", description: "Text für die Verarbeitung normalisieren", risk_level: "low", requires_confirmation: false, requires_permission: false, reversible: true, tags: ["text"], enabled: true },
        { name: "create_note_action", description: "Eine lokale Notiz erzeugen", risk_level: "medium", requires_confirmation: true, requires_permission: true, reversible: true, tags: ["notes"], enabled: true },
      ],
      disabled_actions: [],
    },
    reliability: {
      status: "degraded",
      counts: { ok: 0, degraded: 1, blocked: 0 },
      checks: [],
      recommendations: ["Backend not available."],
    },
    quick_actions: {
      items: [],
    },
    command_center: {
      generated_at: new Date().toISOString(),
      status_cards: [
        { id: "backend", label: "Backend", value: "Mock", status: "degraded", detail: "Backend nicht erreichbar" },
        { id: "ui", label: "UI", value: "Ready", status: "ok", detail: "Fallback-Daten aktiv" },
        { id: "knowledge", label: "Knowledge", value: "0 Quellen", status: "degraded", detail: "Keine lokalen Treffer geladen" },
        { id: "tools", label: "Tools", value: "4 aktiv", status: "ok", detail: "Mock-Tools verfügbar" },
      ],
      active_tasks: [],
      open_questions: [],
      recent_actions: [],
      recent_files: [],
      warnings: [{ id: "backend", title: "Backend nicht erreichbar", source: "ui", status: "degraded" }],
      day_overview: {
        calendar: [],
        reminders: [],
        tasks: [],
        next_best_step: null,
        briefing: {
          status: "ready",
          generated_at: new Date().toISOString(),
          date: new Date().toISOString().slice(0, 10),
          kind: "morning",
          time_budget_minutes: 15,
          focus: [],
          items: [],
          summary: "Daily briefing bereit.",
        },
      },
      quick_actions: [],
      task_pipelines: {
        pipelines: [],
        active: [],
      },
    },
    artifacts: [],
    personal_mode: {
      enabled: true,
      owner_name: "You",
      profile_id: "local-owner",
      local_first: true,
      glass_design: true,
      hidden_surfaces: ["teams", "marketplace", "publishing", "multi_user"],
      preferred_apps: ["VS Code", "Browser", "Obsidian"],
      routines: ["Morning brief", "Focus", "Evening review"],
      preferences: { surface: "minimal", language: "de" },
    },
    active_mode: {
      id: "focus",
      label: "Focus",
      description: "Leise arbeiten, nur wichtige Hinweise.",
      privacy_mode: "local_only",
      trust_level: 2,
      proactive_mode: "subtle",
      status: "active",
    },
    trust_level: {
      level: 2,
      label: "Stufe 2",
      description: "Lesen, suchen, Apps öffnen und sortieren automatisch.",
      permission_profile: "normal",
      rules: [
        { action: "Lesen und zusammenfassen", policy: "automatisch" },
        { action: "Apps öffnen und sortieren", policy: "automatisch" },
        { action: "Dateien ändern", policy: "bestätigen" },
        { action: "Senden, löschen, kaufen, posten", policy: "immer bestätigen" },
      ],
    },
    silent_brain: {
      generated_at: new Date().toISOString(),
      critical_count: 0,
      hint_count: 3,
      summary: "3 Hinweise gesammelt",
      hints: [
        { id: "mock-project", title: "Projektstatus prüfen", subtitle: "Keine Backend-Daten geladen", status: "hint", source: "project" },
        { id: "mock-memory", title: "Memory bereit", subtitle: "Lokale Erinnerungen können gepflegt werden", status: "hint", source: "memory" },
        { id: "mock-health", title: "Systemcheck offen", subtitle: "Backend verbinden für echte Checks", status: "hint", source: "health" },
      ],
      critical: [],
      checks: [
        { id: "backend", label: "Backend", status: "degraded", detail: "Mockdaten aktiv" },
        { id: "privacy", label: "Privacy", status: "ok", detail: "Local-first" },
      ],
    },
    command_palette: {
      placeholder: "Frag M.I.C.A oder starte einen Modus...",
      examples: [
        { id: "focus", label: "Fokus starten", command: "fokus starten" },
        { id: "today", label: "Heute", command: "was steht heute an" },
        { id: "coding", label: "Coding Setup", command: "öffne mein coding setup" },
        { id: "health", label: "Systemcheck", command: "was ist kaputt im system" },
      ],
      suggestions: [],
      modes: [],
    },
    artifact_panel: {
      open: false,
      reason: "manual",
      items: [],
      tabs: [
        { id: "text", label: "Text", count: 0 },
        { id: "code", label: "Code", count: 0 },
        { id: "image", label: "Bild", count: 0 },
      ],
    },
    project_awareness: {
      active_project: null,
      relevant: [],
      todos: [],
      health: [],
      next_three: [],
    },
  };

  if (path === "/api/dashboard") {
    return mockDashboard as T;
  }
  if (path === "/api/cockpit") {
    return mockDashboard.cockpit as T;
  }
  if (path === "/api/session/resume") {
    return mockDashboard.resume as T;
  }
  if (path === "/api/documents") {
    return mockDashboard.documents as T;
  }
  if (path === "/api/setup") {
    return mockDashboard.setup as T;
  }
  if (path === "/api/models") {
    return mockDashboard.models as T;
  }
  if (path === "/api/memory" || path === "/api/memory/export") {
    return mockDashboard.memory as T;
  }
  if (path === "/api/memory/curation") {
    return { entries: [], suggestions: [], counts: { entries: 0, suggestions: 0 } } as T;
  }
  if (path === "/api/actions/history") {
    return mockDashboard.action_history as T;
  }
  if (path === "/api/approvals") {
    return mockDashboard.approvals as T;
  }
  if (path === "/api/permissions") {
    return mockDashboard.permissions as T;
  }
  if (path === "/api/reliability") {
    return mockDashboard.reliability as T;
  }
  if (path === "/api/command-center") {
    return mockDashboard.command_center as T;
  }
  if (path === "/api/personal-mode") {
    return mockDashboard.personal_mode as T;
  }
  if (path === "/api/silent-brain") {
    return mockDashboard.silent_brain as T;
  }
  if (path === "/api/devices") {
    return mockDashboard.devices as T;
  }
  if (path === "/api/platform") {
    return {
      solo: {
        enabled: true,
        owner_user: "u-admin",
        workspace_name: "Personal M.I.C.A",
        local_only: true,
        status: "ready",
        updated_at: new Date().toISOString(),
      },
      solo_status: {
        enabled: true,
        owner_user: "u-admin",
        workspace_name: "Personal M.I.C.A",
        local_only: true,
        status: "ready",
        ready_count: 18,
        total_count: 20,
        optional_count: 2,
        blocking_count: 0,
        updated_at: new Date().toISOString(),
        checklist: [
          { id: "agent_builder", label: "Agent/Persona Builder", status: "ready" },
          { id: "solo_access", label: "Single-User Rollen/RBAC", status: "ready" },
          { id: "marketplace", label: "Lokale Erweiterungen", status: "optional" },
          { id: "openapi_import", label: "OpenAPI Tool Import", status: "ready" },
          { id: "mcp_deferred", label: "MCP Deferred Discovery", status: "ready" },
          { id: "tool_editor", label: "Tool/Function Editor", status: "ready" },
          { id: "workflow_builder", label: "Canvas Workflow Builder", status: "ready" },
          { id: "workflow_debugger", label: "Workflow Replay/Debugger", status: "ready" },
          { id: "evaluations", label: "Evaluations/Model Arena", status: "ready" },
          { id: "metrics", label: "Token/Kosten/Latenz", status: "ready" },
          { id: "knowledge_sync", label: "Knowledge Sync", status: "ready" },
          { id: "hybrid_rag", label: "Hybrid RAG + Reranking", status: "ready" },
          { id: "document_extraction", label: "Dokument-Extraktion", status: "ready" },
          { id: "artifacts", label: "Notes/Artifacts Workspace", status: "ready" },
          { id: "sandbox", label: "Code Interpreter Sandbox", status: "ready" },
          { id: "publishing", label: "Web/App/API/MCP Publishing", status: "ready" },
          { id: "deployment", label: "Lokales Deployment", status: "ready" },
          { id: "identity", label: "SSO/OIDC/LDAP/SCIM optional", status: "optional" },
          { id: "agent_chains", label: "Agent Chains/Subagents", status: "ready" },
          { id: "companion", label: "Mobile/Browser Companion", status: "ready" },
        ],
      },
      users: [
        { id: "u-admin", name: "You", email: "you@mica.local", roles: ["owner"], groups: ["personal"] },
      ],
      groups: [{ id: "personal", name: "Personal Workspace", members: ["u-admin"] }],
      roles: [{ id: "owner", permissions: ["*"] }],
      acls: [],
      audit_events: [],
      agents: [
        {
          id: "research-copilot",
          name: "Research Copilot",
          model: "fast",
          prompt: "You research, cite sources, and summarize compactly.",
          tools: ["web_search", "documents_search"],
          knowledge: ["local-documents"],
          parameters: { temperature: 0.3, max_tokens: 1800 },
          version: "1.0.0",
          visibility: "private",
          owner: "u-admin",
        },
      ],
      agent_packages: [],
      marketplace: [
        {
          id: "github-sync",
          name: "GitHub Knowledge Sync",
          kind: "connector",
          installed: false,
          enabled: false,
          version: "1.0.0",
          latest_version: "1.1.0",
          trust: "community",
          review_status: "pending",
          checksum: "sha256:community-github-sync",
          signature: "unsigned",
          verification: {
            status: "failed",
            checks: [
              { name: "checksum", status: "passed", detail: "sha256:community-github-sync" },
              { name: "signature", status: "failed", detail: "unsigned" },
              { name: "review", status: "failed", detail: "pending" },
            ],
          },
          source_url: "https://plugins.mica.local/github-sync",
          description: "Keeps repositories indexed for RAG.",
          entrypoint: "github_sync",
        },
      ],
      tools: [
        { id: "tool-custom-summarize", name: "summarize_text", kind: "function", status: "draft", code: "return parameters.get('text', '')[:500]", test_parameters: { text: "M.I.C.A Studio" }, test_result: "Not run" },
        { id: "filter-nonempty-text", name: "nonempty_text", kind: "filter", status: "ready", code: "return bool(parameters.get('text', '').strip())", test_parameters: { text: "M.I.C.A" }, test_result: "Filter ready" },
        { id: "pipe-normalize-text", name: "normalize_text", kind: "pipe", status: "ready", code: "return parameters.get('text', '').strip().lower()", test_parameters: { text: "  M.I.C.A Studio  " }, test_result: "Pipe ready" },
        { id: "action-create-note", name: "create_note_action", kind: "action", status: "ready", code: "return {'artifact_title': parameters.get('title', 'Tool Note')}", test_parameters: { title: "Tool Note" }, test_result: "Action ready" },
      ],
      mcp: { deferred: true, last_query: "", tools: [], loaded_tools: [], servers: [] },
      tool_executions: [],
      workflows: [
        {
          id: "wf-triage",
          name: "Document Triage",
          nodes: [
            { id: "input", type: "input", label: "Upload", x: 6, y: 42 },
            { id: "extract", type: "extract", label: "Extract", x: 26, y: 42 },
            { id: "route", type: "branch", label: "Needs Review?", x: 46, y: 42 },
            { id: "human", type: "human", label: "Approval", x: 66, y: 20 },
            { id: "loop", type: "loop", label: "Retry Extract", x: 66, y: 64 },
            { id: "publish", type: "publish", label: "Report", x: 84, y: 42 },
          ],
          edges: [["input", "extract"], ["extract", "route"], ["route", "human", "low confidence"], ["route", "publish", "ready"], ["route", "loop", "retry"], ["loop", "extract"], ["human", "publish"]],
          canvas: { zoom: 1, supports: ["branching", "human-in-the-loop", "loops", "routing"] },
          version: 2,
          versions: [
            {
              version: 2,
              created_at: new Date().toISOString(),
              reason: "mock-edit",
              nodes: [],
              edges: [["input", "extract"]],
              canvas: { zoom: 1 },
            },
          ],
          status: "draft",
          updated_at: new Date().toISOString(),
        },
      ],
      runs: [
        {
          id: "run-demo",
          workflow_id: "wf-triage",
          status: "waiting_for_human",
          started_at: new Date().toISOString(),
          steps: [
            { node: "input", node_type: "input", status: "completed", input: "state[0]", output: "Upload ok", latency_ms: 18, retries: 0, tool_calls: [] },
            { node: "route", node_type: "branch", status: "completed", input: "state[2]", output: "Needs Review? ok", latency_ms: 21, retries: 0, tool_calls: ["branch"], route_labels: ["low confidence", "ready", "retry"], branch_taken: "human" },
            { node: "human", node_type: "human", status: "waiting_for_human", input: "state[3]", output: "Approval ok", latency_ms: 12, retries: 0, tool_calls: [], human_required: true },
            { node: "loop", node_type: "loop", status: "completed", input: "state[4]", output: "Retry Extract ok", latency_ms: 16, retries: 1, tool_calls: ["loop"], loop_iteration: 1, retry_log: ["retry 1 succeeded"] },
          ],
        },
      ],
      evaluations: [
        {
          id: "eval-support",
          name: "Support Prompt Arena",
          agents: ["research-copilot", "research-copilot-v2"],
          dataset: "golden-support-20",
          status: "passing",
          elo: { "research-copilot": 1240, "research-copilot-v2": 1216 },
          regressions: 0,
          last_score: 0.92,
          baseline: "research-copilot",
          challenger: "research-copilot-v2",
          regression_gate: { min_score: 0.8, max_regressions: 0 },
        },
      ],
      evaluation_datasets: [
        { id: "golden-support-20", name: "Golden Support 20", cases: [{ id: "case-1", input: "Summarize refund policy", expected: "Clear refund summary", rubric: "groundedness" }] },
      ],
      evaluation_runs: [
        {
          id: "eval-run-demo",
          evaluation_id: "eval-support",
          dataset: "golden-support-20",
          status: "passing",
          score: 0.92,
          regressions: 0,
          winner: "research-copilot",
          baseline: "research-copilot",
          challenger: "research-copilot-v2",
          elo_delta: { "research-copilot": 8, "research-copilot-v2": -3 },
          gate: { status: "passed", min_score: 0.8, max_regressions: 0 },
          pairs: [{ case_id: "case-1", baseline: "research-copilot", challenger: "research-copilot-v2", winner: "research-copilot", loser: "research-copilot-v2", margin: 0.02 }],
          created_at: new Date().toISOString(),
          cases: [{ case_id: "case-1", agent: "research-copilot", score: 0.94, winner: true, regression: false }],
        },
      ],
      metrics: [
        { scope: "research-copilot", model: "fast", tool: "documents_search", user: "u-admin", agent: "research-copilot", workflow: "wf-triage", tokens: 42100, cost: 0.84, latency_ms: 1180, tool_calls: 36 },
      ],
      knowledge: [],
      knowledge_runs: [],
      knowledge_scheduler_runs: [],
      knowledge_searches: [],
      extraction: {
        engines: ["Docling", "Tika", "OCR"],
        engine_config: { Docling: { tables: true, layout: true, ocr: true, batch_size: 50 } },
        batch_queue: [{ id: "queue-demo", name: "contract.pdf", engine: "Docling", status: "completed", queued_at: new Date().toISOString() }],
        runs: [
          {
            id: "ingest-demo",
            engine: "Docling",
            status: "completed",
            started_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
            artifact_dir: "data/ingestion/ingest-demo",
            artifact_id: "artifact-extraction-report",
            batch_size: 1,
            documents: [
              {
                id: "doc-1",
                name: "contract.pdf",
                status: "extracted",
                pages: 3,
                tables: 2,
                ocr: true,
                ocr_confidence: 0.94,
                layout_blocks: 8,
                quality: "good",
                text_path: "data/ingestion/ingest-demo/doc-1.txt",
                tables_path: "data/ingestion/ingest-demo/doc-1-tables.json",
                layout_path: "data/ingestion/ingest-demo/doc-1-layout.json",
              },
            ],
          },
        ],
        tables: true,
        layouts: true,
        scans: true,
        artifact_dir: "data/ingestion",
      },
      artifacts: [
        {
          id: "artifact-dashboard",
          title: "Operations Snapshot",
          kind: "dashboard",
          content: "<section>Live metrics</section>",
          version: 1,
          versions: [{ version: 1, created_at: new Date().toISOString(), content: "<section>Live metrics</section>" }],
          render_status: "ready",
          updated_at: new Date().toISOString(),
        },
      ],
      sandbox: { enabled: true, languages: ["python"], runs: [] },
      publishing: [
        {
          id: "pub-chat",
          agent_id: "research-copilot",
          kind: "embeddable-chat",
          status: "draft",
          url: "/embed/research-copilot",
          policy: { auth: "workspace", cors: ["http://localhost:5173"], rate_limit_per_minute: 60, allowed_groups: ["core"], secret_refs: [] },
        },
      ],
      deployment: {
        docker_compose: "docker-compose.yml",
        dockerfile: "Dockerfile",
        kubernetes: "helm-ready",
        helm_chart: "deploy/helm/mica",
        postgres: "compose+helm-ready",
        postgres_schema: "deploy/postgres/migrations/001_platform_hub.sql",
        persistence: {
          backend: "json",
          status: "ready",
          path: "data/platform_hub.json",
        },
        migrations: {
          directory: "deploy/postgres/migrations",
          status: "pending",
          applied: [],
          pending: ["001_platform_hub"],
          catalog: [
            {
              id: "001_platform_hub",
              file: "deploy/postgres/migrations/001_platform_hub.sql",
              checksum: "mock",
              size_bytes: 1,
              tables: ["platform_agents", "platform_workflows", "platform_metric_events"],
              indexes: ["idx_platform_metric_events"],
              status: "pending",
            },
          ],
          missing_files: [],
          last_check: new Date().toISOString(),
        },
        redis: "compose+helm-ready",
        storage: "persistent-volume+s3/minio-ready",
        scaling: "horizontal-ready",
        env_mapping: {
          postgres: "MICA_POSTGRES_URL",
          redis: "MICA_REDIS_URL",
          s3_endpoint: "MICA_S3_ENDPOINT",
        },
        readiness: {
          status: "ready",
          checks: [
            { name: "Dockerfile", status: "ready", detail: "Container image build file" },
            { name: "docker-compose.yml", status: "ready", detail: "Compose stack for Postgres/Redis/MinIO" },
          ],
        },
      },
      sso: {
        oidc: "configured",
        ldap: "configurable",
        scim: "enabled",
        providers: ["local", "oidc"],
        default_provider: "local",
        provisioning: "scim-ready",
        login_flows: [],
        sessions: [],
        events: [],
      },
      identity_providers: [
        {
          id: "oidc-main",
          name: "Primary OIDC",
          type: "oidc",
          status: "configured",
          issuer: "https://login.example.com",
          client_id: "mica",
          scim_enabled: true,
          last_test: null,
        },
      ],
      scim_events: [],
      subagents: [],
      agent_chain_runs: [],
      solo_quickstarts: [
        {
          id: "solo-quickstart-demo",
          status: "ready",
          agent_id: "research-copilot",
          artifact_id: "artifact-solo-quickstart",
          created_at: new Date().toISOString(),
          links: {
            agent_app: "/apps/research-copilot",
            embed: "/embed/research-copilot",
            rest: "/api/agents/research-copilot/invoke",
            mcp: "/mcp/research-copilot",
          },
          summary: {
            title: "Personal M.I.C.A ist lokal bereit",
            agent_output: "Research Copilot is ready with local tools, knowledge, sandbox, and publishing.",
            knowledge_results: 2,
            ingested_documents: 2,
            sandbox_stdout: "Solo M.I.C.A quickstart ready",
            workflow_status: "waiting_for_human",
            artifact_id: "artifact-solo-quickstart",
          },
          next_actions: [
            { label: "Agent im lokalen Web-App-Fenster öffnen", href: "/apps/research-copilot", kind: "link" },
            { label: "Knowledge-Treffer prüfen", target: "knowledge", kind: "tab" },
          ],
        },
      ],
      solo_audits: [
        {
          id: "solo-audit-demo",
          status: "ready",
          workspace_name: "Personal M.I.C.A",
          ready_count: 19,
          optional_count: 1,
          blocking_count: 0,
          total_count: 20,
          created_at: new Date().toISOString(),
          items: [
            { id: "agent_builder", label: "Agent/Persona Builder", status: "ready", evidence: ["research-copilot:private"], recommendation: "Bereit für lokale Nutzung.", verified: true },
            { id: "knowledge_sync", label: "Knowledge Sync", status: "ready", evidence: ["local-documents:watching"], recommendation: "Bereit für lokale Nutzung.", verified: true },
            { id: "identity", label: "SSO/OIDC/LDAP/SCIM optional", status: "optional", evidence: ["solo_mode=true"], recommendation: "Optional für deinen Einzelplatzbetrieb.", verified: true },
          ],
        },
      ],
      companion: {
        browser_extension: "manifest-ready",
        mobile_ui: "responsive",
        remote_access: "guarded",
        workspace_endpoint: "/api/companion/workspace",
        file_endpoint: "/api/companion/file",
        terminal_endpoint: "/api/companion/terminal",
        pairing_endpoint: "/api/companion/pair",
        session_endpoint: "/api/companion/session",
        workspace_snapshot_endpoint: "/api/companion/mobile-workspace",
        allowed_terminal_commands: ["git status", "python version", "list files"],
        pairing_required: true,
        pairing_codes: [{ id: "pair-demo", device_name: "Mobile Companion", code: "***42", status: "pending", expires_at: new Date().toISOString() }],
        sessions: [{ id: "companion-demo", device_name: "Mobile Companion", status: "active", scopes: ["workspace:read", "terminal:limited"], last_seen: new Date().toISOString() }],
      },
      counts: {},
      updated_at: new Date().toISOString(),
    } as T;
  }

  return {} as T;
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function normalizePlatformPayload(payload: PlatformPayload): PlatformPayload {
  const source = asRecord(payload) as Partial<PlatformPayload>;
  const extraction = asRecord(source.extraction);
  const sandbox = asRecord(source.sandbox);

  return {
    ...(source as PlatformPayload),
    solo: source.solo,
    solo_status: source.solo_status,
    users: asArray(source.users),
    groups: asArray(source.groups),
    roles: asArray(source.roles),
    acls: asArray(source.acls),
    audit_events: asArray(source.audit_events),
    agents: asArray(source.agents),
    agent_runs: asArray(source.agent_runs),
    invocations: asArray(source.invocations),
    agent_packages: asArray(source.agent_packages),
    marketplace: asArray(source.marketplace),
    marketplace_policy: source.marketplace_policy,
    marketplace_audit: asArray(source.marketplace_audit),
    tools: asArray(source.tools),
    mcp: {
      deferred: Boolean(source.mcp?.deferred),
      last_query: String(source.mcp?.last_query ?? ""),
      tools: asArray(source.mcp?.tools),
      loaded_tools: asArray(source.mcp?.loaded_tools),
      servers: asArray(source.mcp?.servers),
    },
    tool_executions: asArray(source.tool_executions),
    workflows: asArray(source.workflows),
    runs: asArray(source.runs),
    evaluations: asArray(source.evaluations),
    evaluation_datasets: asArray(source.evaluation_datasets),
    evaluation_runs: asArray(source.evaluation_runs),
    metrics: asArray(source.metrics),
    metric_events: asArray(source.metric_events),
    metrics_aggregate: source.metrics_aggregate ?? {},
    knowledge: asArray(source.knowledge),
    knowledge_runs: asArray(source.knowledge_runs),
    knowledge_scheduler_runs: asArray(source.knowledge_scheduler_runs),
    knowledge_searches: asArray(source.knowledge_searches),
    extraction: {
      ...extraction,
      engines: asArray(extraction.engines),
      engine_config: asRecord(extraction.engine_config),
      batch_queue: asArray(extraction.batch_queue),
      runs: asArray(extraction.runs),
    } as PlatformPayload["extraction"],
    artifacts: asArray(source.artifacts),
    sandbox: {
      ...sandbox,
      enabled: Boolean(sandbox.enabled),
      languages: asArray(sandbox.languages),
      runs: asArray(sandbox.runs),
      policy: asRecord(sandbox.policy),
      audit: asArray(sandbox.audit),
    } as PlatformPayload["sandbox"],
    publishing: asArray(source.publishing),
    deployment: asRecord(source.deployment),
    sso: asRecord(source.sso),
    identity_providers: asArray(source.identity_providers),
    scim_events: asArray(source.scim_events),
    subagents: asArray(source.subagents),
    agent_chain_runs: asArray(source.agent_chain_runs),
    solo_quickstarts: asArray(source.solo_quickstarts),
    solo_audits: asArray(source.solo_audits),
    companion: asRecord(source.companion),
    counts: asRecord(source.counts) as Record<string, number>,
    updated_at: source.updated_at ?? new Date().toISOString(),
  };
}

export interface TerminalActionResponse {
  status?: string;
  error?: string;
  result?: {
    id: string;
    command: string;
    argv?: string[];
    status: string;
    returncode: number;
    stdout: string;
    stderr: string;
    latency_ms: number;
    cwd: string;
    allowed_commands?: string[];
  };
  platform?: PlatformPayload;
}

export interface DashboardPollResult {
  dashboard: DashboardResponse | null;
  etag: string | null;
  notModified: boolean;
}

async function getDashboardIfChanged(etag?: string | null): Promise<DashboardPollResult> {
  try {
    const response = await fetch("/api/dashboard", {
      headers: {
        "Content-Type": "application/json",
        ...(etag ? { "If-None-Match": etag } : {}),
      },
    });

    if (response.status === 304) {
      return {
        dashboard: null,
        etag: response.headers.get("ETag") ?? etag ?? null,
        notModified: true,
      };
    }

    const text = await response.text();
    let body: any = {};
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = { raw: text };
      }
    }

    if (!response.ok) {
      const message = body?.error || body?.message || `Request failed: ${response.status}`;
      throw new Error(message);
    }

    return {
      dashboard: body as DashboardResponse,
      etag: response.headers.get("ETag") ?? (body?.revision ? `"${body.revision}"` : null),
      notModified: false,
    };
  } catch (error) {
    console.warn("Backend not available, using mock data:", error);
    return {
      dashboard: getMockData<DashboardResponse>("/api/dashboard"),
      etag: null,
      notModified: false,
    };
  }
}

function subscribeToLiveEvents(
  onEvent: (event: LiveEventPayload) => void,
  onError?: () => void,
): () => void {
  if (typeof window === "undefined" || !("EventSource" in window)) return () => undefined;
  const source = new EventSource("/api/events");
  const handle = (message: MessageEvent<string>) => {
    try {
      onEvent(JSON.parse(message.data) as LiveEventPayload);
    } catch {
      // Ignore malformed third-party/proxy event frames; EventSource reconnects automatically.
    }
  };
  for (const eventName of ["state", "voice", "file", "artifact", "log", "task_graph", "teach", "governor", "evidence", "mutation"]) {
    source.addEventListener(eventName, handle as EventListener);
  }
  source.onerror = () => onError?.();
  return () => source.close();
}

export const micaApi = {
  getDashboard: () => requestJson<DashboardResponse>("/api/dashboard"),
  getDashboardIfChanged,
  subscribeToLiveEvents,
  getFeatures: () => requestJson<FeatureHubPayload>("/api/features"),
  teachAction: (payload: Record<string, unknown>) =>
    requestJson<TeachModePayload>("/api/teach", { method: "POST", body: JSON.stringify(payload) }),
  taskGraphAction: (payload: Record<string, unknown>) =>
    requestJson<{ graph?: import("./types").TaskGraphPayload; items: import("./types").TaskGraphPayload[] }>("/api/task-graphs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  buildEvidence: (query: string, limit = 5) =>
    requestJson<EvidencePayload>("/api/evidence", {
      method: "POST",
      body: JSON.stringify({ query, limit }),
    }),
  saveGovernor: (dailyBudgetUsd: number) =>
    requestJson<AIGovernorPayload>("/api/governor", {
      method: "POST",
      body: JSON.stringify({ daily_budget_usd: dailyBudgetUsd }),
    }),
  getPersonalMode: () => requestJson<PersonalModePayload>("/api/personal-mode"),
  getSilentBrain: () => requestJson<SilentBrainPayload>("/api/silent-brain"),
  getCommandCenter: () => requestJson<CommandCenterPayload>("/api/command-center"),
  getTaskPipelines: () => requestJson<TaskPipelinesPayload>("/api/task-pipelines"),
  getKnowledgeGraph: () => requestJson<KnowledgeGraphPayload>("/api/knowledge/graph"),
  getCockpit: () => requestJson<CockpitPayload>("/api/cockpit"),
  getResume: () => requestJson<ResumePayload>("/api/session/resume"),
  getDocuments: () => requestJson<DocumentsPayload>("/api/documents"),
  getSetup: () => requestJson<SetupPayload>("/api/setup"),
  getModels: () => requestJson<ModelsPayload>("/api/models"),
  getMemory: () => requestJson<MemoryPayload>("/api/memory"),
  getMemoryCuration: () => requestJson<MemoryCurationPayload>("/api/memory/curation"),
  exportMemory: () => requestJson<MemoryPayload>("/api/memory/export"),
  getActionHistory: () => requestJson<ActionHistoryPayload>("/api/actions/history"),
  getApprovals: () => requestJson<ApprovalsPayload>("/api/approvals"),
  getPermissions: () => requestJson<PermissionsPayload>("/api/permissions"),
  getReliability: () => requestJson<ReliabilityPayload>("/api/reliability"),
  getDevices: () => requestJson<DevicesPayload>("/api/devices"),
  getAutomations: () => requestJson<AutomationsPayload>("/api/automations"),
  getPrivacy: () => requestJson<PrivacyPayload>("/api/privacy"),
  getProjectWorkspaces: () => requestJson<ProjectWorkspacesPayload>("/api/project-workspaces"),
  getProjectState: () => requestJson<ProjectStatePayload>("/api/project-state"),
  getSupervisorAutomation: () => requestJson<SupervisorAutomationPayload>("/api/supervisor-automation"),
  getProjectSnapshots: () => requestJson<ProjectSnapshotsPayload>("/api/project-snapshots"),
  getLearningFeedback: () => requestJson<LearningFeedbackPayload>("/api/learning-feedback"),
  getPlugins: () => requestJson<PluginsPayload>("/api/plugins"),
  getOSIntegrations: () => requestJson<OSIntegrationsPayload>("/api/os-integrations"),
  getNoteDrafts: () => requestJson<{ drafts: NoteDraftPayload[] }>("/api/notes/compose"),
  getPlatform: () => requestJson<PlatformPayload>("/api/platform").then(normalizePlatformPayload),
  getSettings: () => requestJson("/api/settings"),
  getCalendarStatus: () => requestJson("/api/calendar/status"),
  getChatSession: (sessionId: string) =>
    requestJson<SessionPayload>(`/api/chats/${encodeURIComponent(sessionId)}`),
  sendCommand: (text: string) =>
    requestJson("/api/command", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  runCommandPalette: (text: string) =>
    requestJson<{ status: string; command_palette?: CommandPalettePayload; artifact_panel?: ArtifactPanelPayload }>("/api/command-palette", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  savePersonalMode: (payload: Partial<PersonalModePayload>) =>
    requestJson<PersonalModePayload>("/api/personal-mode", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  setMode: (mode: string) =>
    requestJson<ActiveModePayload>("/api/mode", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
  setTrustLevel: (level: number) =>
    requestJson<TrustLevelPayload>("/api/trust-level", {
      method: "POST",
      body: JSON.stringify({ level }),
    }),
  clearArtifacts: () =>
    requestJson<ArtifactPanelPayload>("/api/artifacts/clear", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  setMute: (muted: boolean) =>
    requestJson("/api/mute", {
      method: "POST",
      body: JSON.stringify({ muted }),
    }),
  setVoiceMode: (settings: Partial<VoiceConversationState>) =>
    requestJson<{ voice: VoiceConversationState; muted: boolean }>("/api/voice/mode", {
      method: "POST",
      body: JSON.stringify(settings),
    }),
  interruptVoice: () =>
    requestJson<{ voice: VoiceConversationState }>("/api/voice/interrupt", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  taskPipelineAction: (payload: Record<string, unknown>) =>
    requestJson<{ status: string; pipeline?: unknown; task_pipelines: TaskPipelinesPayload }>("/api/task-pipelines", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  noteComposerAction: (payload: Record<string, unknown>) =>
    requestJson<{ status: string; draft?: NoteDraftPayload; drafts: NoteDraftPayload[] }>("/api/notes/compose", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  automationAction: (payload: Record<string, unknown>) =>
    requestJson<{ status: string; automation?: AutomationsPayload["items"][number]; automations: AutomationsPayload; task_pipelines?: TaskPipelinesPayload }>("/api/automations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  setPrivacyMode: (payload: { mode: string; minutes?: number }) =>
    requestJson<PrivacyPayload>("/api/privacy", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  projectWorkspaceAction: (payload: Record<string, unknown>) =>
    requestJson<Record<string, unknown>>("/api/project-workspaces", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  projectStateAction: (payload: Record<string, unknown>) =>
    requestJson<{ status: string; project_state: ProjectStatePayload }>("/api/project-state", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  supervisorAutomationAction: (payload: Record<string, unknown>) =>
    requestJson<{ status: string; settings: SupervisorAutomationPayload }>("/api/supervisor-automation", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  projectSnapshotAction: (payload: Record<string, unknown>) =>
    requestJson<{ status: string; snapshots?: ProjectSnapshotsPayload; package?: Record<string, unknown>; project_state?: ProjectStatePayload; settings?: SupervisorAutomationPayload }>("/api/project-snapshots", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  submitFeedback: (payload: Record<string, unknown>) =>
    requestJson<{ status: string; feedback: unknown; learning_feedback: LearningFeedbackPayload }>("/api/learning-feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  saveSettings: (settings: Record<string, unknown>) =>
    requestJson("/api/settings", {
      method: "POST",
      body: JSON.stringify(settings),
    }),
  saveSetup: (settings: Record<string, unknown>) =>
    requestJson("/api/setup", {
      method: "POST",
      body: JSON.stringify(settings),
    }),
  upsertMemory: (entry: Record<string, unknown>) =>
    requestJson<{ status: string; memory: MemoryPayload }>("/api/memory/upsert", {
      method: "POST",
      body: JSON.stringify(entry),
    }),
  forgetMemory: (entry: { category: string; key: string }) =>
    requestJson<{ status: string; memory: MemoryPayload }>("/api/memory/forget", {
      method: "POST",
      body: JSON.stringify(entry),
    }),
  applyMemoryCuration: (payload: Record<string, unknown>) =>
    requestJson<{ status: string; curation: MemoryCurationPayload }>("/api/memory/curation", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  approveAction: (request: { tool_name: string; action: string }) =>
    requestJson<ApprovalsPayload>("/api/approvals/approve", {
      method: "POST",
      body: JSON.stringify(request),
    }),
  denyAction: (request: { tool_name: string; action: string }) =>
    requestJson<ApprovalsPayload>("/api/approvals/deny", {
      method: "POST",
      body: JSON.stringify(request),
    }),
  setPermissionLevel: (level: string) =>
    requestJson<ApprovalsPayload>("/api/permissions/level", {
      method: "POST",
      body: JSON.stringify({ level }),
    }),
  connectCalendar: (settings: Record<string, unknown>) =>
    requestJson("/api/calendar/connect", {
      method: "POST",
      body: JSON.stringify(settings),
    }),
  platformAction: (action: string, payload: Record<string, unknown>) =>
    strictRequestJson<{ status?: string; error?: string; result: unknown; platform: PlatformPayload }>("/api/platform/action", {
      method: "POST",
      body: JSON.stringify({ action, payload }),
    }).then((response) => ({
      ...response,
      platform: normalizePlatformPayload(response.platform),
    })),
  runLocalTerminal: (command: string) =>
    strictRequestJson<TerminalActionResponse>("/api/platform/action", {
      method: "POST",
      body: JSON.stringify({ action: "run_local_terminal", payload: { command } }),
    }).then((response) => ({
      ...response,
      platform: response.platform ? normalizePlatformPayload(response.platform) : undefined,
    })),
  knowledgeAction: (payload: Record<string, unknown>) =>
    strictRequestJson<Record<string, unknown>>("/api/knowledge", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startNewSession: () =>
    requestJson("/api/session/new", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  endSession: (summary?: string) =>
    requestJson("/api/session/end", {
      method: "POST",
      body: JSON.stringify({ summary }),
    }),
  uploadDocuments: (files: File[], options: { analyze: boolean; index: boolean }) => {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    formData.append("analyze", String(options.analyze));
    formData.append("index", String(options.index));
    return uploadRequest<UploadDocumentsResponse>("/api/documents/upload", formData);
  },
};

