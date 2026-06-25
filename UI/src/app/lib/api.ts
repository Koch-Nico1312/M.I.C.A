import type {
  CockpitPayload,
  DashboardResponse,
  DocumentsPayload,
  MemoryPayload,
  ModelsPayload,
  ActionHistoryPayload,
  ApprovalsPayload,
  DevicesPayload,
  PermissionsPayload,
  ReliabilityPayload,
  ResumePayload,
  SessionPayload,
  SetupPayload,
  UploadDocumentsResponse,
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

function getMockData<T>(path: string): T {
  const mockDashboard: DashboardResponse = {
    state: {
      state: "LISTENING",
      muted: false,
      speaking: false,
      voice_focus: true,
      default_view: "home",
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
        default_view: "home",
        voice_first: true,
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
          default_view: "home",
          voice_first: true,
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
      tools: [],
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
  if (path === "/api/devices") {
    return mockDashboard.devices as T;
  }

  return {} as T;
}

export const jarvisApi = {
  getDashboard: () => requestJson<DashboardResponse>("/api/dashboard"),
  getCockpit: () => requestJson<CockpitPayload>("/api/cockpit"),
  getResume: () => requestJson<ResumePayload>("/api/session/resume"),
  getDocuments: () => requestJson<DocumentsPayload>("/api/documents"),
  getSetup: () => requestJson<SetupPayload>("/api/setup"),
  getModels: () => requestJson<ModelsPayload>("/api/models"),
  getMemory: () => requestJson<MemoryPayload>("/api/memory"),
  exportMemory: () => requestJson<MemoryPayload>("/api/memory/export"),
  getActionHistory: () => requestJson<ActionHistoryPayload>("/api/actions/history"),
  getApprovals: () => requestJson<ApprovalsPayload>("/api/approvals"),
  getPermissions: () => requestJson<PermissionsPayload>("/api/permissions"),
  getReliability: () => requestJson<ReliabilityPayload>("/api/reliability"),
  getDevices: () => requestJson<DevicesPayload>("/api/devices"),
  getSettings: () => requestJson("/api/settings"),
  getCalendarStatus: () => requestJson("/api/calendar/status"),
  getChatSession: (sessionId: string) =>
    requestJson<SessionPayload>(`/api/chats/${encodeURIComponent(sessionId)}`),
  sendCommand: (text: string) =>
    requestJson("/api/command", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  setMute: (muted: boolean) =>
    requestJson("/api/mute", {
      method: "POST",
      body: JSON.stringify({ muted }),
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

