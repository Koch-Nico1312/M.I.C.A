import type { DashboardResponse, SessionPayload } from "./types";

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

function getMockData<T>(path: string): T {
  const mockDashboard: DashboardResponse = {
    state: {
      state: "LISTENING",
      muted: false,
      speaking: false,
      voice_focus: true,
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
  };

  if (path === "/api/dashboard") {
    return mockDashboard as T;
  }

  return {} as T;
}

export const jarvisApi = {
  getDashboard: () => requestJson<DashboardResponse>("/api/dashboard"),
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
};

