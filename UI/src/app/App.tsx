import { Component, startTransition, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType, PointerEvent as ReactPointerEvent, ReactNode } from "react";
import {
  Activity,
  Bot,
  ChevronDown,
  CircleDot,
  Home,
  LayoutDashboard,
  Maximize2,
  MessageSquareText,
  Mic,
  Minimize2,
  PanelRightClose,
  Pause,
  PlayCircle,
  Radio,
  Settings,
  Shield,
  Sparkles,
  Square,
} from "lucide-react";
import { Button } from "./components/ui/button";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "./components/ui/resizable";
import { CommandCenterView } from "./components/CommandCenterView";
import { HomeView } from "./components/HomeView";
import { VoiceChatView } from "./components/VoiceChatView";
import { ChatsView } from "./components/ChatsView";
import { SettingsModal } from "./components/SettingsModal";
import { jarvisApi } from "./lib/api";
import type { ArtifactPanelItem, ChatSession, DashboardResponse } from "./lib/types";

type ViewId =
  | "command-center"
  | "home"
  | "voice-chat"
  | "chats";

type ActiveViewId = ViewId | null;

type ViewDefinition = {
  id: ViewId;
  label: string;
  category: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
  supportsFullscreen?: boolean;
};

const viewRegistry: ViewDefinition[] = [
  {
    id: "command-center",
    label: "Command",
    category: "ARTIFACTS",
    description: "Active tasks, search results, actions",
    icon: LayoutDashboard,
    supportsFullscreen: true,
  },
  {
    id: "home",
    label: "System",
    category: "SYSTEM",
    description: "Dashboard and operational overview",
    icon: Home,
    supportsFullscreen: true,
  },
  {
    id: "voice-chat",
    label: "Voice",
    category: "VOICE",
    description: "Conversation and listening controls",
    icon: Mic,
    supportsFullscreen: true,
  },
  {
    id: "chats",
    label: "Chats",
    category: "CHAT",
    description: "Session history and transcript",
    icon: MessageSquareText,
    supportsFullscreen: true,
  },
];

const DASHBOARD_REFRESH_MS = 2000;

class ViewErrorBoundary extends Component<
  { viewKey: string; children: ReactNode },
  { error: Error | null; viewKey: string }
> {
  constructor(props: { viewKey: string; children: ReactNode }) {
    super(props);
    this.state = { error: null, viewKey: props.viewKey };
  }

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  static getDerivedStateFromProps(
    props: { viewKey: string; children: ReactNode },
    state: { error: Error | null; viewKey: string },
  ) {
    if (props.viewKey !== state.viewKey) {
      return { error: null, viewKey: props.viewKey };
    }
    return null;
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full items-center justify-center p-8 text-center">
          <div className="max-w-xl rounded-xl border border-rose-400/20 bg-rose-400/10 p-6 text-rose-50">
            <div className="text-sm font-semibold text-rose-100">
              Ansicht konnte nicht gerendert werden
            </div>
            <p className="mt-2 text-xs text-rose-100/75">
              {this.state.error.message || "Unbekannter UI-Fehler"}
            </p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function roundResourceMetric(value: unknown) {
  return Math.round(Number(value ?? 0) * 10) / 10;
}

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
          cpu_percent: roundResourceMetric(resources.cpu_percent),
          memory_percent: roundResourceMetric(resources.memory_percent),
          disk_percent: roundResourceMetric(resources.disk_percent),
          threads: resources.threads ?? 0,
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
    command_center: dashboard.command_center,
    artifacts: dashboard.artifacts,
  });
}

function getValidViewId(value: string): ViewId {
  return viewRegistry.some((view) => view.id === value) ? (value as ViewId) : "voice-chat";
}

function JarvisHead({
  speaking,
  compact = false,
}: {
  speaking: boolean;
  compact?: boolean;
}) {
  return (
    <div
      className={`jarvis-head ${speaking ? "jarvis-head-speaking" : ""} relative flex aspect-square items-center justify-center ${
        compact
          ? "w-24"
          : "w-[86%] min-w-[280px] max-w-[680px]"
      }`}
    >
      <div className="jarvis-head-orbit absolute inset-[-9%] rounded-full border border-cyan-200/10" />
      <div className="jarvis-head-scan absolute inset-[7%] rounded-full" />
      <div
        className={`absolute inset-0 rounded-full border-[#3498df] shadow-[0_0_34px_rgba(52,152,223,0.36),inset_0_0_28px_rgba(0,0,0,0.72)] ${
          compact ? "border-[5px]" : "border-[9px]"
        }`}
      />
      <div className="absolute inset-[4.5%] rounded-full border border-white/[0.045] bg-[#020707] shadow-[inset_0_22px_80px_rgba(255,255,255,0.025)]" />
      <div className="absolute inset-[12%] rounded-full border border-white/[0.025]" />

      <div className="relative flex w-[42%] items-center justify-between">
        {[0, 1].map((eye) => (
          <div
            key={eye}
            className={`jarvis-eye rounded-[46%] bg-gradient-to-b from-white via-cyan-100 to-cyan-300 shadow-[0_0_34px_rgba(125,226,255,0.32)] ${
              compact ? "h-6 w-4" : "h-14 w-10 sm:h-16 sm:w-11"
            }`}
          >
            <div
              className={`mx-auto rounded-full bg-[#26343b] ${
                compact ? "mt-2 h-3 w-2" : "mt-4 h-7 w-5 sm:h-8 sm:w-6"
              }`}
            />
          </div>
        ))}
      </div>
      <div
        className={`jarvis-mouth absolute bottom-[31%] rounded-full bg-slate-200/90 ${
          compact ? "h-px w-7" : "h-px w-16"
        }`}
      />
    </div>
  );
}

function ArtifactCard({ artifact }: { artifact: ArtifactPanelItem }) {
  const createdAt = artifact.created_at
    ? new Date(artifact.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";
  const progress =
    typeof artifact.progress === "number"
      ? Math.max(0, Math.min(100, Math.round(artifact.progress)))
      : null;

  return (
    <article className="apple-panel rounded-[1.35rem] border border-white/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-[0.26em] text-cyan-100/55">
            {artifact.kind}
          </div>
          <h2 className="mt-1 truncate text-base font-semibold text-white">{artifact.title}</h2>
        </div>
        {createdAt ? <span className="shrink-0 text-[11px] text-slate-500">{createdAt}</span> : null}
      </div>

      {artifact.kind === "table" && artifact.rows?.length ? (
        <div className="mt-4 overflow-auto rounded-xl border border-white/10 bg-black/25">
          <table className="min-w-full text-left text-xs text-slate-300">
            <thead className="border-b border-white/10 text-slate-500">
              <tr>
                {(artifact.columns?.length ? artifact.columns : Object.keys(artifact.rows[0] ?? {})).map((column) => (
                  <th key={column} className="px-3 py-2 font-medium">{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {artifact.rows.slice(0, 50).map((row, index) => (
                <tr key={index} className="border-b border-white/[0.04] last:border-0">
                  {(artifact.columns?.length ? artifact.columns : Object.keys(row)).map((column) => (
                    <td key={column} className="max-w-[220px] truncate px-3 py-2">
                      {String(row[column] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {artifact.kind === "code" ? (
        <pre className="mt-4 max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-black/35 p-3 font-mono text-xs leading-5 text-slate-200">
          {artifact.content ?? ""}
        </pre>
      ) : null}

      {artifact.kind === "progress" && progress !== null ? (
        <div className="mt-4">
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-cyan-200" style={{ width: `${progress}%` }} />
          </div>
          <div className="mt-2 text-xs text-slate-400">{progress}%</div>
        </div>
      ) : null}

      {artifact.url ? (
        <a
          href={artifact.url}
          target="_blank"
          rel="noreferrer"
          className="mt-4 block truncate rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-cyan-100 hover:bg-white/[0.08]"
        >
          {artifact.url}
        </a>
      ) : null}

      {artifact.kind !== "code" && artifact.content ? (
        <div className="mt-4 whitespace-pre-wrap rounded-xl bg-black/20 p-3 text-sm leading-6 text-slate-300">
          {artifact.content}
        </div>
      ) : null}
    </article>
  );
}

function ArtifactSpaceView({ artifacts }: { artifacts: ArtifactPanelItem[] }) {
  if (!artifacts.length) {
    return <div className="h-full" aria-label="Artifact panel empty" />;
  }

  return (
    <div className="h-full min-h-0 overflow-y-auto p-4 md:p-5">
      <div className="grid gap-3 xl:grid-cols-2">
        {artifacts.map((artifact) => (
          <ArtifactCard key={artifact.id} artifact={artifact} />
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [activeView, setActiveView] = useState<ActiveViewId>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [isPanelFullscreen, setIsPanelFullscreen] = useState(false);
  const [isPanelHidden, setIsPanelHidden] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isViewMenuOpen, setIsViewMenuOpen] = useState(false);
  const [isCompanionMode, setIsCompanionMode] = useState(false);
  const [companionPosition, setCompanionPosition] = useState({ x: 24, y: 24 });
  const appliedVoiceDefault = useRef(false);
  const lastDashboardSignature = useRef<string | null>(null);
  const knownArtifactIds = useRef<Set<string> | null>(null);
  const companionDrag = useRef<{ pointerId: number; dx: number; dy: number } | null>(null);
  const companionPositionInitialized = useRef(false);

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
    if (appliedVoiceDefault.current || !dashboard) return;
    appliedVoiceDefault.current = true;
    const voice = dashboard.state?.voice;
    const shouldEnableOpenMic =
      dashboard.settings?.ui?.voice_first !== false &&
      (!voice || voice.input_mode === "push_to_talk" || dashboard.state?.muted);

    if (shouldEnableOpenMic) {
      handleSetVoiceMode({
        input_mode: "open_mic",
        push_to_talk_active: true,
        wakeword_enabled: false,
      }).catch(() => undefined);
      if (dashboard.state?.muted) {
        handleToggleMute(false).catch(() => undefined);
      }
    }
  }, [dashboard]);

  useEffect(() => {
    if (!dashboard) return;
    const artifacts = dashboard.artifacts ?? [];
    const nextIds = new Set(artifacts.map((artifact) => artifact.id));
    const previousIds = knownArtifactIds.current;
    knownArtifactIds.current = nextIds;

    if (!previousIds) return;
    const hasNewArtifact = artifacts.some((artifact) => !previousIds.has(artifact.id));
    if (!hasNewArtifact) return;

    setActiveView(null);
    setIsPanelHidden(false);
    setIsViewMenuOpen(false);
  }, [dashboard]);

  useEffect(() => {
    if (!isCompanionMode) return;
    setCompanionPosition(({ x, y }) => {
      if (!companionPositionInitialized.current) {
        companionPositionInitialized.current = true;
        return {
          x: Math.max(12, window.innerWidth - 340),
          y: Math.max(12, window.innerHeight - 150),
        };
      }
      return {
        x: Math.max(12, Math.min(x, window.innerWidth - 340)),
        y: Math.max(12, Math.min(y, window.innerHeight - 150)),
      };
    });
  }, [isCompanionMode]);

  const handleCompanionPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest("button")) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    companionDrag.current = {
      pointerId: event.pointerId,
      dx: event.clientX - companionPosition.x,
      dy: event.clientY - companionPosition.y,
    };
  };

  const handleCompanionPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = companionDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const nextX = event.clientX - drag.dx;
    const nextY = event.clientY - drag.dy;
    setCompanionPosition({
      x: Math.max(12, Math.min(nextX, window.innerWidth - 340)),
      y: Math.max(12, Math.min(nextY, window.innerHeight - 150)),
    });
  };

  const handleCompanionPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (companionDrag.current?.pointerId === event.pointerId) {
      companionDrag.current = null;
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handleViewChange = (view: string) => {
    setActiveView(getValidViewId(view));
    setIsPanelHidden(false);
    setIsViewMenuOpen(false);
  };

  const handleArtifactsView = () => {
    setActiveView(null);
    setIsPanelHidden(false);
    setIsViewMenuOpen(false);
  };

  const handleSendCommand = async (text: string) => {
    await jarvisApi.sendCommand(text);
    await refreshDashboard(true);
  };

  const handleToggleMute = async (muted: boolean) => {
    await jarvisApi.setMute(muted);
    await refreshDashboard(true);
  };

  const handleSetVoiceMode = async (settings: Parameters<typeof jarvisApi.setVoiceMode>[0]) => {
    await jarvisApi.setVoiceMode(settings);
    await refreshDashboard(true);
  };

  const handleInterruptVoice = async () => {
    await jarvisApi.interruptVoice();
    await refreshDashboard(true);
  };

  const handleStartNewChat = async () => {
    const result = await jarvisApi.startNewSession();
    await refreshDashboard(true);
    const sessionId =
      (result as { session_id?: string; current_session?: ChatSession | null })?.current_session?.id ??
      (result as { session_id?: string })?.session_id ??
      null;
    if (sessionId) {
      setSelectedChatId(sessionId);
    }
    handleViewChange("chats");
  };

  const handleSettingsSaved = async () => {
    await refreshDashboard(true);
  };

  const currentView = useMemo<ViewDefinition | null>(
    () => viewRegistry.find((view) => view.id === activeView) ?? null,
    [activeView],
  );
  const CurrentViewIcon = currentView?.icon ?? Sparkles;
  const resources = dashboard?.resources ?? null;
  const state = dashboard?.state ?? null;
  const isMuted = Boolean(state?.muted);
  const isSpeaking = Boolean(state?.speaking);
  const performance = resources?.performance;
  const activity = performance?.current_activity ?? state?.state ?? "idle";

  const renderActiveView = () => {
    if (loadError) {
      return (
        <div className="flex h-full items-center justify-center p-8 text-center">
          <div className="max-w-lg rounded-xl border border-rose-400/20 bg-rose-400/10 p-8 text-rose-50">
            <div className="mb-2 flex items-center justify-center gap-2 text-rose-200">
              <Activity className="h-5 w-5" />
              Backend connection issue
            </div>
            <p className="text-sm text-rose-100/80">{loadError}</p>
          </div>
        </div>
      );
    }

    return (
      <ViewErrorBoundary viewKey={activeView ?? "empty"}>
        {activeView === null && (
          <ArtifactSpaceView artifacts={dashboard?.artifacts ?? []} />
        )}
        {activeView === "command-center" && (
          <CommandCenterView
            dashboard={dashboard}
            onSendCommand={handleSendCommand}
            onStartNewChat={handleStartNewChat}
            onViewChange={handleViewChange}
          />
        )}
        {activeView === "home" && (
          <HomeView dashboard={dashboard} onStartNewChat={handleStartNewChat} />
        )}
        {activeView === "voice-chat" && (
          <VoiceChatView
            dashboard={dashboard}
            onSendCommand={handleSendCommand}
            onToggleMute={handleToggleMute}
            onSetVoiceMode={handleSetVoiceMode}
            onInterruptVoice={handleInterruptVoice}
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
      </ViewErrorBoundary>
    );
  };

  if (isCompanionMode) {
    return (
      <div className="min-h-screen overflow-hidden bg-transparent text-slate-100">
        <div
          className="fixed z-50 cursor-grab rounded-[1.75rem] border border-white/10 bg-[#071011]/80 p-3 shadow-[0_24px_90px_rgba(0,0,0,0.55)] backdrop-blur-2xl active:cursor-grabbing"
          style={{ left: companionPosition.x, top: companionPosition.y }}
          onPointerDown={handleCompanionPointerDown}
          onPointerMove={handleCompanionPointerMove}
          onPointerUp={handleCompanionPointerUp}
          onPointerCancel={handleCompanionPointerUp}
        >
          <div className="flex items-center gap-4">
            <JarvisHead speaking={isSpeaking} compact />
            <div className="min-w-0">
              <div className="text-[10px] uppercase tracking-[0.34em] text-cyan-100/60">
                Jarvis
              </div>
              <div className="mt-1 text-xs text-slate-300">
                {isSpeaking ? "spricht" : isMuted ? "stumm" : "bereit"}
              </div>
              <div className="mt-3 flex gap-2">
                <Button
                  size="icon"
                  title={isMuted ? "Voice aktivieren" : "Voice stummschalten"}
                  onClick={() => handleToggleMute(!isMuted)}
                  className="h-8 w-8 rounded-lg bg-cyan-200 text-slate-950 hover:bg-cyan-100"
                >
                  <Mic className="h-4 w-4" />
                </Button>
                <Button
                  size="icon"
                  title="Antwort stoppen"
                  onClick={handleInterruptVoice}
                  disabled={!isSpeaking}
                  className="h-8 w-8 rounded-lg border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10 disabled:opacity-45"
                >
                  <Square className="h-4 w-4" />
                </Button>
                <Button
                  size="icon"
                  title="UI öffnen"
                  onClick={() => setIsCompanionMode(false)}
                  className="h-8 w-8 rounded-lg border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
                >
                  <Maximize2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="apple-chrome min-h-screen overflow-hidden text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(90deg,_rgba(255,255,255,0.025)_1px,_transparent_1px),linear-gradient(180deg,_rgba(255,255,255,0.018)_1px,_transparent_1px)] bg-[size:80px_80px]" />
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_22%_48%,_rgba(55,169,255,0.16),_transparent_24%),radial-gradient(circle_at_78%_18%,_rgba(125,226,255,0.08),_transparent_28%),linear-gradient(180deg,_#070b0c_0%,_#030707_72%)]" />

      <main className="relative z-10 min-h-screen overflow-x-hidden overflow-y-auto p-4 sm:p-6 lg:h-screen lg:min-h-[720px] lg:overflow-hidden">
        <ResizablePanelGroup direction="horizontal" className="min-h-[calc(100vh-3rem)] gap-5 lg:min-h-0">
          {!isPanelFullscreen ? (
            <>
              <ResizablePanel
                id="jarvis-companion"
                order={1}
                defaultSize={26}
                minSize={18}
                maxSize={42}
                collapsible
                className={isPanelHidden ? "hidden lg:block" : ""}
              >
        <section
          className={`apple-panel relative h-full min-h-[500px] min-w-0 overflow-hidden rounded-[1.75rem] border border-white/[0.08] transition-all duration-500 ease-out lg:min-h-0 ${
            isPanelFullscreen ? "hidden pointer-events-none opacity-0 lg:block" : "opacity-100"
          }`}
        >
          <div className="absolute left-8 top-8 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-300/20 bg-cyan-300/10 text-cyan-100 shadow-[0_0_24px_rgba(56,189,248,0.16)]">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.42em] text-slate-400">
                JARVIS
              </div>
              <div className="text-xs text-cyan-100/70">Unified system interface</div>
            </div>
          </div>

          <div className="flex h-full flex-col items-center justify-center px-8 pb-28 pt-24">
            <div className="relative">
              <JarvisHead speaking={isSpeaking} />

              <div className="absolute -bottom-16 left-1/2 grid w-[min(330px,86vw)] -translate-x-1/2 grid-cols-3 gap-2 lg:w-[300px]">
                <div className="rounded-lg border border-white/[0.07] bg-black/30 px-3 py-2 backdrop-blur-xl">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">State</div>
                  <div className="mt-1 truncate text-xs text-cyan-100">{state?.state ?? "LISTENING"}</div>
                </div>
                <div className="rounded-lg border border-white/[0.07] bg-black/30 px-3 py-2 backdrop-blur-xl">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Activity</div>
                  <div className="mt-1 truncate text-xs text-slate-200">{activity}</div>
                </div>
                <div className="rounded-lg border border-white/[0.07] bg-black/30 px-3 py-2 backdrop-blur-xl">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Privacy</div>
                  <div className="mt-1 truncate text-xs text-emerald-100">{dashboard?.privacy?.mode ?? "balanced"}</div>
                </div>
              </div>
            </div>
          </div>

          <div className="apple-panel absolute bottom-7 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-2xl border border-white/[0.08] p-1.5">
            <Button
              size="icon"
              title={isMuted ? "Voice aktivieren" : "Voice stummschalten"}
              onClick={() => handleToggleMute(!isMuted)}
              className={`apple-button h-9 w-9 rounded-xl border text-slate-950 ${
                isMuted
                  ? "border-white/10 bg-white/85 hover:bg-white"
                  : "border-cyan-200/30 bg-cyan-200 hover:bg-cyan-100"
              }`}
            >
              {isMuted ? <Pause className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            </Button>
            <Button
              size="icon"
              title="Neue Sitzung"
              onClick={handleStartNewChat}
              className="apple-button h-9 w-9 rounded-xl border border-white/10 bg-white/[0.055] text-slate-200 hover:bg-white/10"
            >
              <PlayCircle className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              title="Chats öffnen"
              onClick={() => handleViewChange("chats")}
              className="apple-button h-9 w-9 rounded-xl border border-white/10 bg-white/[0.055] text-slate-200 hover:bg-white/10"
            >
              <MessageSquareText className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              title="Voice unterbrechen"
              onClick={handleInterruptVoice}
              disabled={!isSpeaking}
              className="apple-button h-9 w-9 rounded-xl border border-white/10 bg-white/[0.055] text-slate-200 hover:bg-white/10 disabled:opacity-45"
            >
              <Square className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              title="Mini-Pet"
              onClick={() => setIsCompanionMode(true)}
              className="apple-button h-9 w-9 rounded-xl border border-white/10 bg-white/[0.055] text-slate-200 hover:bg-white/10"
            >
              <Bot className="h-4 w-4" />
            </Button>
          </div>
        </section>
              </ResizablePanel>
              <ResizableHandle
                withHandle
                className="jarvis-resize-handle hidden lg:flex"
              />
            </>
          ) : null}

          <ResizablePanel
            id="jarvis-artifacts"
            order={2}
            defaultSize={isPanelFullscreen ? 100 : 74}
            minSize={35}
            className="min-w-0"
          >
        <section
          className={`relative h-full min-h-[720px] min-w-0 overflow-hidden lg:min-h-0 ${
            isPanelHidden ? "hidden pointer-events-none opacity-0 lg:block" : "opacity-100"
          }`}
        >
          <div className="flex h-full flex-col pb-10 pt-0 lg:pb-0">
            <div className="mb-5 flex flex-col items-start justify-between gap-4 sm:flex-row">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.32em] text-cyan-100/70">
                  <span className="rounded-sm bg-cyan-300/20 px-1.5 py-0.5 text-cyan-100">
                    ARTIFACT PANEL
                  </span>
                  <span>{currentView?.category ?? "EMPTY"}</span>
                </div>
                <h1 className="mt-1 truncate text-[22px] font-semibold leading-tight text-white">
                  {currentView?.label ?? "Artifacts"}
                </h1>
              </div>

              <div className="relative flex w-full shrink-0 items-center gap-2 sm:w-auto">
                <Button
                  type="button"
                  onClick={() => setIsViewMenuOpen((open) => !open)}
                  className="apple-button h-10 rounded-2xl border border-white/[0.08] bg-white/[0.055] px-3 text-sm text-slate-100 shadow-none hover:bg-white/[0.08]"
                  aria-expanded={isViewMenuOpen}
                  aria-haspopup="menu"
                >
                  <CurrentViewIcon className="h-4 w-4 text-cyan-100" />
                  <span className="max-w-28 truncate">{currentView?.label ?? "Switch"}</span>
                  <ChevronDown className="h-4 w-4 text-slate-400" />
                </Button>

                {isViewMenuOpen ? (
                  <div
                    role="menu"
                    className="apple-panel absolute right-0 top-12 z-50 w-80 rounded-[1.35rem] border border-white/[0.08] p-2 text-slate-100"
                  >
                    <div className="px-3 py-2 text-[11px] uppercase tracking-[0.28em] text-slate-500">
                      Artefakt-Panel
                    </div>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={handleArtifactsView}
                      className={`flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-left text-slate-200 outline-none transition hover:bg-cyan-300/10 hover:text-cyan-50 focus:bg-cyan-300/10 focus:text-cyan-50 ${
                        activeView === null ? "bg-cyan-300/10 text-cyan-50" : ""
                      }`}
                    >
                      <Sparkles className="h-4 w-4 text-cyan-100" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm">Artifacts</span>
                          {activeView === null ? <CircleDot className="h-3.5 w-3.5 text-cyan-200" /> : null}
                        </div>
                        <div className="truncate text-xs text-slate-500">Empty artifact space</div>
                      </div>
                    </button>
                    {viewRegistry.map((view) => {
                      const Icon = view.icon;
                      const isActive = view.id === activeView;
                      return (
                        <button
                          key={view.id}
                          type="button"
                          role="menuitem"
                          onClick={() => handleViewChange(view.id)}
                          className={`flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-left text-slate-200 outline-none transition hover:bg-cyan-300/10 hover:text-cyan-50 focus:bg-cyan-300/10 focus:text-cyan-50 ${
                            isActive ? "bg-cyan-300/10 text-cyan-50" : ""
                          }`}
                        >
                          <Icon className="h-4 w-4 text-cyan-100" />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm">{view.label}</span>
                              {isActive ? <CircleDot className="h-3.5 w-3.5 text-cyan-200" /> : null}
                            </div>
                            <div className="truncate text-xs text-slate-500">{view.description}</div>
                          </div>
                        </button>
                      );
                    })}
                    <div className="mx-2 my-2 h-px bg-white/[0.08]" />
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => setIsSettingsModalOpen(true)}
                      className="flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-left text-slate-200 transition hover:bg-cyan-300/10 hover:text-cyan-50 focus:bg-cyan-300/10 focus:text-cyan-50"
                    >
                      <Settings className="h-4 w-4 text-cyan-100" />
                      Settings
                    </button>
                  </div>
                ) : null}

                <Button
                  size="icon"
                  title={isPanelFullscreen ? "Panel verkleinern" : "Fullscreen"}
                  onClick={() => setIsPanelFullscreen((value) => !value)}
                  className="apple-button hidden h-10 w-10 rounded-2xl border border-white/[0.08] bg-white/[0.055] text-slate-200 shadow-none hover:bg-white/[0.08] sm:flex"
                >
                  {isPanelFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                </Button>
                <Button
                  size="icon"
                  title="Hide"
                  onClick={() => setIsPanelHidden(true)}
                  className="apple-button hidden h-10 w-10 rounded-2xl border border-white/[0.08] bg-white/[0.055] text-slate-200 shadow-none hover:bg-white/[0.08] sm:flex"
                >
                  <PanelRightClose className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="apple-panel min-h-0 flex-1 overflow-hidden rounded-[1.75rem] border border-white/[0.08] transition-all duration-500 ease-out">
              {renderActiveView()}
            </div>
          </div>
        </section>
          </ResizablePanel>
        </ResizablePanelGroup>

        {isPanelHidden ? (
          <button
            onClick={() => setIsPanelHidden(false)}
            className="absolute right-6 top-6 z-30 flex items-center gap-2 rounded-lg border border-white/[0.08] bg-[#131b1f]/90 px-3 py-2 text-sm text-slate-100 shadow-[0_18px_40px_rgba(0,0,0,0.38)] backdrop-blur-xl transition hover:bg-white/[0.08]"
          >
            <Sparkles className="h-4 w-4 text-cyan-100" />
            Show panel
          </button>
        ) : null}

        <div className="pointer-events-none absolute bottom-3 right-7 z-20 flex items-center gap-3 text-[11px] uppercase tracking-[0.2em] text-slate-500">
          <span className="flex items-center gap-1.5">
            <Radio className="h-3.5 w-3.5 text-cyan-200" />
            {lastUpdated
              ? `Updated ${new Date(lastUpdated).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
              : "Connecting"}
          </span>
          <span className="flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5 text-emerald-200" />
            {dashboard?.privacy?.mode ?? "balanced"}
          </span>
          <span className="flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-cyan-200" />
            {performance?.model_active ? "Model active" : "Standby"}
          </span>
        </div>
      </main>

      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        onSaved={handleSettingsSaved}
      />
    </div>
  );
}
