import { useEffect, useRef, useState, startTransition } from "react";
import { Sparkles, Activity } from "lucide-react";
import { SidebarProvider, SidebarTrigger, SidebarInset } from "./components/ui/sidebar";
import { AppSidebar } from "./components/AppSidebar";
import { DocumentsView } from "./components/DocumentsView";
import { HomeView } from "./components/HomeView";
import { MemoryView } from "./components/MemoryView";
import { VoiceChatView } from "./components/VoiceChatView";
import { ChatsView } from "./components/ChatsView";
import { ResourcesView } from "./components/ResourcesView";
import { jarvisApi } from "./lib/api";
import type { ChatSession, DashboardResponse } from "./lib/types";

const viewTitles: Record<string, string> = {
  home: "Dashboard",
  "voice-chat": "Sprechen",
  chats: "Chats",
  memory: "Memory",
  documents: "Dokumente",
  resources: "Ressourcen",
};

const DASHBOARD_REFRESH_MS = 12000;

function stableDashboardSignature(dashboard: DashboardResponse) {
  const state = dashboard.state;
  const resources = dashboard.resources;

  return JSON.stringify({
    state: state
      ? {
          value: state.state,
          muted: state.muted,
          speaking: state.speaking,
          current_file: state.current_file,
          voice_focus: state.voice_focus,
          default_view: state.default_view,
          logs: (state.logs ?? []).slice(-12).map((log) => ({
            timestamp: Math.round(Number(log.timestamp ?? 0)),
            text: log.text,
          })),
        }
      : null,
    resources: resources
      ? {
          cpu_percent: Math.round(Number(resources.cpu_percent ?? 0)),
          memory_percent: Math.round(Number(resources.memory_percent ?? 0)),
          disk_percent: Math.round(Number(resources.disk_percent ?? 0)),
          active_tasks: resources.performance?.active_tasks ?? 0,
          current_activity: resources.performance?.current_activity ?? "idle",
          waiting_for_input: Boolean(resources.performance?.waiting_for_input),
          model_active: Boolean(resources.performance?.model_active),
          tool_active: Boolean(resources.performance?.tool_active),
        }
      : null,
    settings: dashboard.settings,
    calendar: dashboard.calendar,
    current_session: dashboard.current_session,
    recent_sessions: dashboard.recent_sessions,
    cockpit: dashboard.cockpit,
    resume: dashboard.resume,
    documents: dashboard.documents,
    setup: dashboard.setup,
    models: dashboard.models,
    memory: dashboard.memory,
    devices: dashboard.devices,
    action_history: dashboard.action_history,
    approvals: dashboard.approvals,
    permissions: dashboard.permissions,
    quick_actions: dashboard.quick_actions,
  });
}

export default function App() {
  const [activeView, setActiveView] = useState("home");
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const appliedDefaultView = useRef(false);
  const lastDashboardSignature = useRef<string | null>(null);

  const refreshDashboard = async (force = false) => {
    try {
      const next = await jarvisApi.getDashboard();
      const signature = stableDashboardSignature(next);
      if (!force && signature === lastDashboardSignature.current) {
        setLoadError(null);
        return;
      }

      lastDashboardSignature.current = signature;
      startTransition(() => {
        setDashboard(next);
        setLoadError(null);
        setLastUpdated(Date.now());
        setSelectedChatId((prev) => {
          const ids = new Set<string>();
          if (next.current_session?.id) ids.add(next.current_session.id);
          for (const session of next.recent_sessions || []) {
            ids.add(session.id);
          }
          if (prev && ids.has(prev)) return prev;
          return next.current_session?.id ?? next.recent_sessions[0]?.id ?? prev;
        });
      });
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Dashboard konnte nicht geladen werden.");
    }
  };

  useEffect(() => {
    let alive = true;
    const tick = () => {
      if (!alive) return;
      refreshDashboard();
    };

    tick();
    const timer = window.setInterval(tick, DASHBOARD_REFRESH_MS);

    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!dashboard || appliedDefaultView.current) {
      return;
    }

    const requested = dashboard.settings?.ui?.default_view ?? dashboard.state?.default_view ?? "voice-chat";
    const normalized =
      requested === "voice" || requested === "speech" || requested === "listen"
        ? "home"
        : requested === "voice-chat"
          ? "home"
        : requested;

    if (typeof normalized === "string" && normalized) {
      setActiveView(normalized);
    }

    appliedDefaultView.current = true;
  }, [dashboard]);

  const handleSendCommand = async (text: string) => {
    await jarvisApi.sendCommand(text);
    await refreshDashboard(true);
  };

  const handleToggleMute = async (muted: boolean) => {
    await jarvisApi.setMute(muted);
    await refreshDashboard(true);
  };

  const handleStartNewChat = async () => {
    const result = await jarvisApi.startNewSession();
    await refreshDashboard(true);
    const sessionId = (result as { session_id?: string; current_session?: ChatSession | null })?.current_session?.id
      ?? (result as { session_id?: string })?.session_id
      ?? null;
    if (sessionId) {
      setSelectedChatId(sessionId);
    }
    setActiveView("chats");
  };

  const handleSettingsSaved = async () => {
    await refreshDashboard(true);
  };

  const currentSession =
    dashboard?.current_session ?? null;

  const resources = dashboard?.resources ?? null;
  const state = dashboard?.state ?? null;

  const resourceBadges = [
    {
      label: "CPU",
      value: `${resources?.cpu_percent?.toFixed?.(1) ?? "0.0"}%`,
      tone: "text-[#1fb6ff]",
      bg: "bg-[#1fb6ff]/15",
    },
    {
      label: "RAM",
      value: `${resources?.memory_percent?.toFixed?.(1) ?? "0.0"}%`,
      tone: "text-[#7ce6c8]",
      bg: "bg-[#7ce6c8]/15",
    },
    {
      label: "Disk",
      value: `${resources?.disk_percent?.toFixed?.(1) ?? "0.0"}%`,
      tone: "text-[#ffb86b]",
      bg: "bg-[#ffb86b]/15",
    },
  ];

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="relative flex min-h-screen w-full overflow-hidden bg-[#041018] text-slate-100">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(0,212,255,0.16),_transparent_40%),radial-gradient(circle_at_top_right,_rgba(124,230,200,0.12),_transparent_35%),linear-gradient(180deg,_rgba(4,16,24,0.98),_rgba(3,10,16,1))]" />
          <div className="absolute left-0 top-0 h-80 w-80 rounded-full bg-[#00d4ff]/10 blur-3xl" />
          <div className="absolute bottom-0 right-0 h-96 w-96 rounded-full bg-[#7ce6c8]/10 blur-3xl" />
        </div>

        <AppSidebar
          activeView={activeView}
          onViewChange={setActiveView}
          dashboard={dashboard}
          onSettingsSaved={handleSettingsSaved}
        />

        <SidebarInset className="relative z-10 flex-1 bg-transparent">
          <div className="flex h-screen flex-col">
            <header className="sticky top-0 z-20 border-b border-white/10 bg-[#06131d]/70 backdrop-blur-2xl">
              <div className="flex flex-col gap-3 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-6">
                <div className="flex items-center gap-3">
                  <SidebarTrigger className="text-cyan-200 hover:bg-white/10" />
                  <div>
                    <div className="flex items-center gap-2 text-xs uppercase tracking-[0.35em] text-cyan-200/70">
                      <Sparkles className="h-4 w-4" />
                      Jarvis
                    </div>
                    <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">
                      {viewTitles[activeView] ?? "JARVIS"}
                    </h1>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">
                    {state?.state ?? "LISTENING"}
                  </span>
                  <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100">
                    {state?.voice_focus ? "Voice first" : "Chat optional"}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                    {currentSession?.title ?? "No active chat"}
                  </span>
                </div>
              </div>

              <div className="grid gap-2 border-t border-white/10 px-4 py-3 md:grid-cols-3 md:px-6">
                {resourceBadges.map((badge) => (
                  <div
                    key={badge.label}
                    className={`flex items-center justify-between rounded-2xl border border-white/10 ${badge.bg} px-4 py-3`}
                  >
                    <span className="text-xs uppercase tracking-[0.25em] text-slate-300">
                      {badge.label}
                    </span>
                    <span className={`text-sm font-semibold ${badge.tone}`}>{badge.value}</span>
                  </div>
                ))}
              </div>
            </header>

            <main className="flex-1 overflow-hidden p-4 md:p-6">
              <div className="h-full overflow-hidden rounded-[2rem] border border-white/10 bg-[#071823]/75 shadow-[0_24px_80px_rgba(0,0,0,0.45)] backdrop-blur-2xl">
                {loadError ? (
                  <div className="flex h-full items-center justify-center p-8 text-center">
                    <div className="max-w-lg rounded-3xl border border-rose-400/20 bg-rose-400/10 p-8 text-rose-50">
                      <div className="mb-2 flex items-center justify-center gap-2 text-rose-200">
                        <Activity className="h-5 w-5" />
                        Backend connection issue
                      </div>
                      <p className="text-sm text-rose-100/80">{loadError}</p>
                    </div>
                  </div>
                ) : (
                  <>
                    {activeView === "home" && (
                      <HomeView dashboard={dashboard} onStartNewChat={handleStartNewChat} />
                    )}
                    {activeView === "voice-chat" && (
                      <VoiceChatView
                        dashboard={dashboard}
                        onSendCommand={handleSendCommand}
                        onToggleMute={handleToggleMute}
                        onStartNewChat={handleStartNewChat}
                      />
                    )}
                    {activeView === "chats" && (
                      <ChatsView
                        dashboard={dashboard}
                        selectedChatId={selectedChatId}
                        onSelectChat={setSelectedChatId}
                        onStartNewChat={handleStartNewChat}
                        onRefresh={refreshDashboard}
                      />
                    )}
                    {activeView === "documents" && (
                      <DocumentsView currentFile={state?.current_file ?? null} />
                    )}
                    {activeView === "memory" && <MemoryView />}
                    {activeView === "resources" && <ResourcesView dashboard={dashboard} />}
                  </>
                )}
              </div>
            </main>
          </div>
        </SidebarInset>
      </div>
      <div className="fixed bottom-4 right-4 z-50 rounded-full border border-white/10 bg-[#06131d]/80 px-4 py-2 text-xs text-slate-300 shadow-2xl backdrop-blur-xl">
        {lastUpdated ? `Updated ${new Date(lastUpdated).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Connecting..."}
      </div>
    </SidebarProvider>
  );
}
