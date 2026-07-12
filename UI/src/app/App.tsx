import { Component, lazy, memo, startTransition, Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType, CSSProperties, FormEvent, PointerEvent as ReactPointerEvent, ReactNode, RefObject } from "react";
import {
  Activity,
  Bell,
  BrainCircuit,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Code2,
  Command,
  Copy,
  CornerDownLeft,
  FileText,
  Folder,
  Grid2X2,
  Home,
  Image as ImageIcon,
  List,
  LayoutDashboard,
  Maximize2,
  MessageSquareText,
  Mic,
  Moon,
  MoreHorizontal,
  Radio,
  Save,
  Search,
  Settings,
  Shield,
  Share2,
  Sun,
  Sparkles,
  Square,
  Volume2,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { AgentHubView } from "./components/AgentHubView";
import { getMicaBackgroundUrl } from "./lib/backgrounds";
import { micaApi } from "./lib/api";
import type { ArtifactPanelItem, ChatSession, DashboardResponse } from "./lib/types";

const CommandCenterView = lazy(() => import("./components/CommandCenterView").then((module) => ({ default: module.CommandCenterView })));
const HomeView = lazy(() => import("./components/HomeView").then((module) => ({ default: module.HomeView })));
const VoiceChatView = lazy(() => import("./components/VoiceChatView").then((module) => ({ default: module.VoiceChatView })));
const ChatsView = lazy(() => import("./components/ChatsView").then((module) => ({ default: module.ChatsView })));
const SettingsModal = lazy(() => import("./components/SettingsModal").then((module) => ({ default: module.SettingsModal })));
const IntelligenceCenterView = lazy(() => import("./components/IntelligenceCenterView").then((module) => ({ default: module.IntelligenceCenterView })));

type ViewId =
  | "command-center"
  | "home"
  | "voice-chat"
  | "chats"
  | "intelligence";

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
  {
    id: "intelligence",
    label: "Intelligence",
    category: "AI",
    description: "Teach Mode, Task Graphs, Evidence and budgets",
    icon: BrainCircuit,
    supportsFullscreen: true,
  },
];

const DASHBOARD_FALLBACK_REFRESH_MS = 30000;

const modeOptions = [
  { id: "focus", label: "Fokus" },
  { id: "coding", label: "Code" },
  { id: "research", label: "Recherche" },
  { id: "private", label: "Privat" },
  { id: "gaming", label: "Gaming" },
  { id: "admin", label: "Admin" },
];

const privacyOptions = [
  { id: "local_only", label: "Nur lokal" },
  { id: "balanced", label: "Ausgewogen" },
  { id: "cloud_allowed", label: "Cloud erlaubt" },
  { id: "private_with_approval", label: "Privat mit Freigabe" },
];

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

function getValidViewId(value: string): ViewId {
  return viewRegistry.some((view) => view.id === value) ? (value as ViewId) : "voice-chat";
}

type MicaFaceMode = "idle" | "listening" | "thinking" | "speaking" | "muted";

function MicaHead({
  speaking,
  mode = speaking ? "speaking" : "idle",
  compact = false,
}: {
  speaking: boolean;
  mode?: MicaFaceMode;
  compact?: boolean;
}) {
  const humanDetails = ["glance-left", "glance-right", "soft-smile", "curious", "calm"] as const;
  const [humanDetail, setHumanDetail] = useState<(typeof humanDetails)[number]>("calm");

  useEffect(() => {
    if (compact) return;
    const pickNextDetail = () => {
      setHumanDetail((current) => {
        const pool = humanDetails.filter((detail) => detail !== current);
        return pool[Math.floor(Math.random() * pool.length)] ?? "calm";
      });
    };
    const firstTimer = window.setTimeout(pickNextDetail, 1800 + Math.random() * 2200);
    const interval = window.setInterval(pickNextDetail, 6200 + Math.random() * 3800);
    return () => {
      window.clearTimeout(firstTimer);
      window.clearInterval(interval);
    };
  }, [compact]);

  return (
    <div
      className={`mica-face mica-orb mica-orb-${mode} mica-human-${humanDetail} ${speaking ? "mica-orb-speaking" : ""} relative flex aspect-square items-center justify-center ${
        compact
          ? "w-24"
          : "w-[min(27vw,342px)] min-w-[238px] max-w-[352px]"
      }`}
    >
      <div className="mica-orb-halo absolute inset-[-7%] rounded-full" />
      <div className="mica-orb-shell absolute inset-0 rounded-full" />
      <div className="mica-orb-glass absolute inset-[4%] rounded-full" />
      <div className="mica-orb-shade absolute inset-[10%] rounded-full" />
      <div className="mica-cheek mica-cheek-left absolute rounded-full" />
      <div className="mica-cheek mica-cheek-right absolute rounded-full" />
      <div className="mica-brow mica-brow-left absolute" />
      <div className="mica-brow mica-brow-right absolute" />
      <div className="mica-nose-light absolute" />

      <div className="relative mt-[5%] flex w-[45%] items-center justify-between">
        {[0, 1].map((eye) => (
          <div
            key={eye}
            className={`mica-orb-eye ${compact ? "h-5 w-5" : "h-[46px] w-[46px]"}`}
          >
            <span />
            <i />
          </div>
        ))}
      </div>
      <div
        className={`mica-orb-mouth absolute rounded-full ${
          compact ? "bottom-[31%] h-1 w-8" : "bottom-[27%] h-[22px] w-[76px]"
        }`}
      />
      <div className="mica-expression-line mica-expression-left absolute" />
      <div className="mica-expression-line mica-expression-right absolute" />
    </div>
  );
}

function VoicePulse({ speaking }: { speaking: boolean }) {
  return (
    <div className={`voice-pulse ${speaking ? "voice-pulse-active" : ""}`} aria-hidden="true">
      {[0, 1, 2, 3, 4, 5, 6].map((bar) => (
        <span key={bar} style={{ ["--bar" as string]: bar }} />
      ))}
    </div>
  );
}

const ARTIFACT_RENDER_LIMIT = 24;

const ArtifactCard = memo(function ArtifactCard({ artifact }: { artifact: ArtifactPanelItem }) {
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

      {(artifact.kind === "image" || artifact.mime_type?.startsWith("image/")) && (artifact.url || artifact.path) ? (
        <div className="mt-4 overflow-hidden rounded-xl border border-white/10 bg-black/20">
          <img
            src={artifact.url ?? artifact.path}
            alt={artifact.title}
            className="max-h-[420px] w-full object-contain"
          />
        </div>
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
});

function GlassPill({
  icon: Icon,
  label,
  value,
  tone = "neutral",
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone?: "neutral" | "cyan" | "emerald" | "amber";
}) {
  const toneClass = {
    neutral: "text-slate-200",
    cyan: "text-cyan-100",
    emerald: "text-emerald-100",
    amber: "text-amber-100",
  }[tone];

  return (
    <div className="liquid-pill flex min-w-0 items-center gap-2 px-3 py-2">
      <Icon className={`h-4 w-4 ${toneClass}`} />
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">{label}</div>
        <div className={`truncate text-xs font-medium ${toneClass}`}>{value}</div>
      </div>
    </div>
  );
}

function HintStrip({ dashboard }: { dashboard: DashboardResponse | null }) {
  const brain = dashboard?.silent_brain;
  const hints = brain?.hints ?? [];
  const critical = brain?.critical ?? [];
  const visible = critical.length ? critical : hints;

  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {visible.slice(0, 3).map((item) => (
        <div key={item.id} className="liquid-tile px-3 py-3">
          <div className="truncate text-sm font-medium text-white">{item.title}</div>
          {item.subtitle ? (
            <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-400">{item.subtitle}</div>
          ) : null}
        </div>
      ))}
      {!visible.length ? (
        <div className="liquid-tile px-3 py-3 text-sm text-slate-400 sm:col-span-3">
          Alles ruhig. M.I.C.A sammelt nur leise Kontext.
        </div>
      ) : null}
    </div>
  );
}

function CommandPalette({
  value,
  inputRef,
  placeholder,
  examples,
  sending,
  onChange,
  onSubmit,
  onExample,
}: {
  value: string;
  inputRef: RefObject<HTMLInputElement | null>;
  placeholder: string;
  examples: Array<{ id: string; label: string; command: string }>;
  sending: boolean;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  onExample: (command: string) => void;
}) {
  const visibleExamples = examples.slice(0, 3);
  const footers = [
    { id: "projects", label: "Projekte", icon: Folder },
    { id: "notes", label: "Notizen", icon: FileText },
    { id: "files", label: "Dateien", icon: Folder },
    { id: "apps", label: "Apps", icon: Grid2X2 },
  ];

  return (
    <form onSubmit={onSubmit} className="reference-command mx-auto w-full max-w-[760px]">
      <div className="reference-command-input">
        <Search className="h-6 w-6 shrink-0 text-[#8ed6ff]" />
        <input
          ref={inputRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className="min-w-0 flex-1 bg-transparent text-lg text-white outline-none placeholder:text-slate-300/70"
        />
        <Mic className="h-5 w-5 shrink-0 text-white/85" />
        <span className="reference-keycap">
          <Command className="h-3.5 w-3.5" />K
        </span>
        <Button
          type="submit"
          disabled={!value.trim() || sending}
          className="hidden"
        >
          Senden
        </Button>
      </div>
      <div className="reference-command-list">
        {visibleExamples.map((example, index) => {
          const Icon = index === 0 ? Radio : index === 1 ? List : Code2;
          const detail =
            index === 0
              ? "Starte Focus-Session mit Timer und Musik"
              : index === 1
                ? "Zeige meinen Tagesplan und offene Aufgaben"
                : "Starte VS Code, Projekt und Terminal";
          return (
          <button
            key={example.id}
            type="button"
            onClick={() => onExample(example.command)}
            className="reference-command-row"
          >
            <span className="reference-command-row-icon"><Icon className="h-5 w-5" /></span>
            <span className="min-w-0 flex-1 text-left">
              <span className="block truncate text-base text-white">{example.command}</span>
              <span className="block truncate text-sm text-slate-300/75">{detail}</span>
            </span>
            <CornerDownLeft className="h-4 w-4 text-white/70" />
          </button>
          );
        })}
      </div>
      <div className="reference-command-footer">
        {footers.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" className="reference-footer-button">
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
        <button type="button" className="reference-footer-dot">
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </div>
    </form>
  );
}

function ReferenceArtifactPanel({
  artifacts,
  artifactTab,
  onArtifactTab,
  onFullscreen,
  onShare,
  onSave,
}: {
  artifacts: ArtifactPanelItem[];
  artifactTab: string;
  onArtifactTab: (tab: string) => void;
  onFullscreen: () => void;
  onShare: () => void;
  onSave: () => void;
}) {
  const codeArtifact = artifacts.find((artifact) => artifact.kind === "code");
  const textArtifact = artifacts.find((artifact) => artifact.kind === "text");
  const imageArtifact = artifacts.find((artifact) => artifact.kind === "image" || artifact.mime_type?.startsWith("image/"));
  const imageSource = imageArtifact?.url ?? imageArtifact?.path;
  const content =
    codeArtifact?.content ??
    `import datetime
from core.memory import MemoryManager
from core.project import ProjectWorkspace

class MICACore:
    def __init__(self):
        self.memory = MemoryManager()
        self.project = ProjectWorkspace()
        self.now = lambda: datetime.datetime.now()

    def get_briefing(self):
        today = self.now().strftime("%d.%m.%Y")
        plan = self.project.get_today_plan()
        health = self.project.get_health()

        return {
            "datum": today,
            "plan": plan,
            "gesundheit": health,
        }`;
  const lines = content.split("\n");

  return (
    <aside className="reference-artifact-panel">
      <div className="reference-artifact-tabs">
        <button type="button" onClick={() => onArtifactTab("text")} className={`reference-artifact-tab ${artifactTab === "text" ? "reference-artifact-tab-active" : ""}`}>
          <FileText className="h-4 w-4" />Text
        </button>
        <button type="button" onClick={() => onArtifactTab("code")} className={`reference-artifact-tab ${artifactTab === "code" ? "reference-artifact-tab-active" : ""}`}>
          <Code2 className="h-5 w-5" />Code
        </button>
        <button type="button" onClick={() => onArtifactTab("image")} className={`reference-artifact-tab ${artifactTab === "image" ? "reference-artifact-tab-active" : ""}`}>
          <ImageIcon className="h-4 w-4" />Bild
        </button>
      </div>

      <div className="reference-code-card">
        <div className="reference-code-header">
          <div>
            <div className="text-base font-medium text-white">{codeArtifact?.title ?? "mica_core.py"}</div>
            <div className="mt-1 text-xs text-slate-300/70">core &gt; {codeArtifact?.title ?? "mica_core.py"}</div>
          </div>
          <button type="button" onClick={() => navigator.clipboard?.writeText(content)} className="reference-icon-action" title="Kopieren">
            <Copy className="h-5 w-5" />
          </button>
        </div>
        {artifactTab === "code" ? (
          <pre className="reference-code-body">
            {lines.map((line, index) => (
              <span key={`${index}-${line}`} className="reference-code-line">
                <span className="reference-line-number">{index + 1}</span>
                <code>{line || " "}</code>
              </span>
            ))}
          </pre>
        ) : null}
        {artifactTab === "text" ? (
          <div className="reference-text-body">
            {textArtifact?.content || "Noch kein Text-Artefakt vorhanden. Neue Antworten und Notizen erscheinen hier, sobald M.I.C.A Text erzeugt."}
          </div>
        ) : null}
        {artifactTab === "image" ? (
          <div className="reference-image-body">
            {imageSource ? (
              <img src={imageSource} alt="M.I.C.A Bildartefakt" />
            ) : (
              <span>Neue Bilder erscheinen hier, sobald M.I.C.A ein Bild erzeugt oder öffnet.</span>
            )}
          </div>
        ) : null}
      </div>

      <div className="reference-output">
        <div className="reference-output-title">
          <span className="flex items-center gap-2"><Sparkles className="h-4 w-4" />Ausgabe</span>
          <span className="flex items-center gap-2 text-xs text-slate-300/70"><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />Ausgeführt: Heute, 09:41</span>
        </div>
        <pre>{`Briefing geladen
• 5 Aufgaben geplant
• 2 Tasks überfällig
• Projektstatus: Gut`}</pre>
      </div>

      <div className="reference-artifact-actions">
        <button type="button" onClick={onSave} className="reference-save-button"><Save className="h-4 w-4" />Speichern</button>
        <div className="ml-auto flex items-center gap-5 text-white/80">
          <button type="button" onClick={onShare} className="reference-icon-action" title="Teilen"><Share2 className="h-5 w-5" /></button>
          <span className="h-7 w-px bg-white/20" />
          <button type="button" onClick={onFullscreen} className="reference-icon-action" title="Vollbild"><Maximize2 className="h-5 w-5" /></button>
        </div>
      </div>
    </aside>
  );
}

const ArtifactSpaceView = memo(function ArtifactSpaceView({ artifacts }: { artifacts: ArtifactPanelItem[] }) {
  if (!artifacts.length) {
    return <div className="h-full" aria-label="Artifact panel empty" />;
  }

  const visibleArtifacts = artifacts.slice(0, ARTIFACT_RENDER_LIMIT);
  const hiddenCount = Math.max(0, artifacts.length - visibleArtifacts.length);

  return (
    <div className="h-full min-h-0 overflow-y-auto p-4 md:p-5">
      <div className="grid gap-3 xl:grid-cols-2">
        {visibleArtifacts.map((artifact) => (
          <ArtifactCard key={artifact.id} artifact={artifact} />
        ))}
        {hiddenCount ? (
          <div className="apple-panel rounded-[1.35rem] border border-white/10 p-4 text-sm text-slate-400">
            {hiddenCount} weitere Artefakte ausgeblendet, damit die Ansicht flüssig bleibt.
          </div>
        ) : null}
      </div>
    </div>
  );
});

export default function App() {
  const [workspace, setWorkspace] = useState<"main" | "agent-hub">(() =>
    window.localStorage.getItem("mica.workspace") === "agent-hub" ? "agent-hub" : "main",
  );
  const [activeView, setActiveView] = useState<ActiveViewId>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isPanelFullscreen, setIsPanelFullscreen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [openTopMenu, setOpenTopMenu] = useState<"mode" | "privacy" | "hints" | "volume" | null>(null);
  const [isCompanionMode, setIsCompanionMode] = useState(false);
  const [companionPosition, setCompanionPosition] = useState({ x: 24, y: 24 });
  const [commandInput, setCommandInput] = useState("");
  const [isCommandSending, setIsCommandSending] = useState(false);
  const [isArtifactPanelOpen, setIsArtifactPanelOpen] = useState(false);
  const [artifactTab, setArtifactTab] = useState("code");
  const [voiceVolume, setVoiceVolume] = useState(82);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [, setCustomBackgroundVersion] = useState(0);
  const commandInputRef = useRef<HTMLInputElement>(null);
  const appliedVoiceDefault = useRef(false);
  const dashboardEtag = useRef<string | null>(null);
  const liveRefreshTimer = useRef<number | null>(null);
  const knownArtifactIds = useRef<Set<string> | null>(null);
  const companionDrag = useRef<{ pointerId: number; dx: number; dy: number } | null>(null);
  const companionPositionInitialized = useRef(false);

  const refreshDashboard = async (force = false) => {
    try {
      const response = await micaApi.getDashboardIfChanged(force ? null : dashboardEtag.current);
      if (!force && response.notModified) {
        setLoadError(null);
        return;
      }
      const next = response.dashboard;
      if (!next) {
        setLoadError(null);
        return;
      }

      dashboardEtag.current = response.etag ?? (next.revision ? `"${next.revision}"` : null);
      startTransition(() => {
        setDashboard(next);
        setLoadError(null);
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
    const unsubscribe = micaApi.subscribeToLiveEvents(() => {
      if (!alive || liveRefreshTimer.current !== null) return;
      liveRefreshTimer.current = window.setTimeout(() => {
        liveRefreshTimer.current = null;
        tick();
      }, 120);
    });
    const timer = window.setInterval(tick, DASHBOARD_FALLBACK_REFRESH_MS);

    return () => {
      alive = false;
      unsubscribe();
      if (liveRefreshTimer.current !== null) window.clearTimeout(liveRefreshTimer.current);
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
    setIsArtifactPanelOpen(true);
    setOpenTopMenu(null);
  }, [dashboard]);

  useEffect(() => {
    const nextVolume = Number(dashboard?.settings?.ui?.voice_volume);
    if (Number.isFinite(nextVolume)) {
      setVoiceVolume(Math.max(0, Math.min(200, Math.round(nextVolume))));
    }
    const nextTheme = dashboard?.settings?.ui?.theme === "light" ? "light" : "dark";
    setTheme(nextTheme);
  }, [dashboard?.settings?.ui?.theme, dashboard?.settings?.ui?.voice_volume]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsPanelFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        commandInputRef.current?.focus();
      }
      if (event.key === "Escape") {
        setOpenTopMenu(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

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
    setOpenTopMenu(null);
  };

  const handleModeSelect = async (mode: string) => {
    await micaApi.setMode(mode);
    setOpenTopMenu(null);
    await refreshDashboard(true);
  };

  const handlePrivacySelect = async (mode: string) => {
    await micaApi.setPrivacyMode({ mode });
    setOpenTopMenu(null);
    await refreshDashboard(true);
  };

  const handleThemeToggle = async () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    await micaApi.saveSettings({ ui: { theme: nextTheme } });
    await refreshDashboard(true);
  };

  const handleVoiceVolumeCommit = async (value: number) => {
    const nextVolume = Math.max(0, Math.min(200, Math.round(value)));
    setVoiceVolume(nextVolume);
    await micaApi.saveSettings({ ui: { voice_volume: nextVolume } });
    await refreshDashboard(true);
  };

  const handleFullscreen = async () => {
    const element = document.querySelector(".reference-window") as HTMLElement | null;
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      setIsPanelFullscreen(false);
      return;
    }
    await element?.requestFullscreen?.();
    setIsPanelFullscreen(true);
  };

  const handleSaveVisibleArtifact = () => {
    const artifact = filteredArtifacts[0] ?? artifacts[0];
    const content = artifact?.content || artifact?.url || artifact?.path || "M.I.C.A";
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${artifact?.title || "mica-artifact"}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const handleShare = async () => {
    const artifact = filteredArtifacts[0] ?? artifacts[0];
    const text = artifact?.content || artifact?.url || artifact?.title || "M.I.C.A";
    if (navigator.share) {
      await navigator.share({ title: artifact?.title || "M.I.C.A", text });
      return;
    }
    await navigator.clipboard?.writeText(text);
  };

  const handleSendCommand = async (text: string) => {
    await micaApi.sendCommand(text);
    await refreshDashboard(true);
  };

  const handleCommandPaletteSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const text = commandInput.trim();
    if (!text || isCommandSending) return;
    setIsCommandSending(true);
    try {
      await micaApi.runCommandPalette(text);
      setCommandInput("");
      await refreshDashboard(true);
    } finally {
      setIsCommandSending(false);
    }
  };

  const handleCommandExample = async (command: string) => {
    setCommandInput(command);
    commandInputRef.current?.focus();
  };

  const handleToggleMute = async (muted: boolean) => {
    await micaApi.setMute(muted);
    await refreshDashboard(true);
  };

  const handleSetVoiceMode = async (settings: Parameters<typeof micaApi.setVoiceMode>[0]) => {
    await micaApi.setVoiceMode(settings);
    await refreshDashboard(true);
  };

  const handleInterruptVoice = async () => {
    await micaApi.interruptVoice();
    await refreshDashboard(true);
  };

  const handleStartNewChat = async () => {
    const result = await micaApi.startNewSession();
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
    setCustomBackgroundVersion((version) => version + 1);
    await refreshDashboard(true);
  };

  const resources = dashboard?.resources ?? null;
  const state = dashboard?.state ?? null;
  const isMuted = Boolean(state?.muted);
  const isSpeaking = Boolean(state?.speaking);
  const performance = resources?.performance;
  const activity = performance?.current_activity ?? state?.state ?? "idle";
  const activityLabel = String(activity).toLowerCase();
  const faceMode: MicaFaceMode = isMuted
    ? "muted"
    : isSpeaking
      ? "speaking"
      : /listen|record|hearing|voice/.test(activityLabel)
        ? "listening"
        : /think|process|load|run|work/.test(activityLabel)
          ? "thinking"
          : "idle";
  const selectedBackgroundUrl = getMicaBackgroundUrl(
    dashboard?.settings?.ui?.background_id,
    dashboard?.settings?.ui?.background_url,
  );
  const wallpaperStyle = selectedBackgroundUrl
    ? ({ "--mica-background-image": `url("${selectedBackgroundUrl}")` } as CSSProperties)
    : undefined;

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
      <Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-cyan-100/70">Ansicht wird geladen…</div>}>
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
        {activeView === "intelligence" && (
          <IntelligenceCenterView dashboard={dashboard} />
        )}
      </ViewErrorBoundary>
      </Suspense>
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
            <MicaHead speaking={isSpeaking} mode={faceMode} compact />
            <div className="min-w-0">
              <div className="text-[10px] uppercase tracking-[0.34em] text-cyan-100/60">
                M.I.C.A
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

  const activeMode = dashboard?.active_mode;
  const silentBrain = dashboard?.silent_brain;
  const currentPrivacy = dashboard?.privacy?.mode ?? activeMode?.privacy_mode ?? "balanced";
  const artifacts = dashboard?.artifact_panel?.items ?? dashboard?.artifacts ?? [];
  const filteredArtifacts =
    artifactTab === "all" ? artifacts : artifacts.filter((artifact) => artifact.kind === artifactTab);
  const commandExamples = dashboard?.command_palette?.examples ?? [
    { id: "focus", label: "Fokus starten", command: "fokus starten" },
    { id: "today", label: "Heute", command: "was steht heute an" },
    { id: "coding", label: "Coding Setup", command: "öffne mein coding setup" },
    { id: "health", label: "Systemcheck", command: "was ist kaputt im system" },
  ];

  const handleWorkspaceChange = (next: "main" | "agent-hub") => {
    setWorkspace(next);
    window.localStorage.setItem("mica.workspace", next);
    setOpenTopMenu(null);
    setIsArtifactPanelOpen(false);
  };

  return (
    <div className={`reference-shell reference-shell-${theme} ${isPanelFullscreen ? "reference-shell-fullscreen" : ""} text-slate-100`}>
      <div className="reference-wallpaper pointer-events-none fixed inset-0" style={wallpaperStyle} />
      <main className={`reference-window relative z-10 h-full w-full overflow-hidden ${isPanelFullscreen ? "reference-window-fullscreen" : ""}`}>
        <header className="reference-topbar">
          <div className="reference-brand">M.I.C.A</div>

          <div className="workspace-switcher" role="group" aria-label="Arbeitsbereich auswählen">
            <button type="button" className={workspace === "main" ? "active" : ""} onClick={() => handleWorkspaceChange("main")}>Main</button>
            <button type="button" className={workspace === "agent-hub" ? "active" : ""} onClick={() => handleWorkspaceChange("agent-hub")}>Agent-Hub</button>
          </div>

          <div className={`reference-top-pills ${workspace === "agent-hub" ? "workspace-main-controls-hidden" : ""}`}>
            <button type="button" onClick={() => setOpenTopMenu(openTopMenu === "mode" ? null : "mode")} className="reference-top-pill">
              <Radio className="h-4 w-4 text-white/85" />
              {activeMode?.label ?? "Fokus"}
              <ChevronDown className="h-4 w-4 text-white/70" />
            </button>
            <button type="button" onClick={() => setOpenTopMenu(openTopMenu === "privacy" ? null : "privacy")} className="reference-top-pill">
              <Shield className="h-4 w-4 text-white/85" />
              {privacyOptions.find((option) => option.id === currentPrivacy)?.label ?? "Local Privacy"}
              <ChevronDown className="h-4 w-4 text-white/70" />
            </button>
            <button type="button" onClick={() => setOpenTopMenu(openTopMenu === "hints" ? null : "hints")} className="reference-top-pill">
              <Bell className="h-4 w-4 text-white/85" />
              {silentBrain?.hint_count ? `${silentBrain.hint_count} Hinweise` : "0 Hinweise"}
            </button>
            {openTopMenu === "mode" ? (
              <div className="reference-top-menu">
                {modeOptions.map((option) => (
                  <button key={option.id} type="button" onClick={() => handleModeSelect(option.id)} className="liquid-menu-row">
                    {option.label}
                  </button>
                ))}
              </div>
            ) : null}
            {openTopMenu === "privacy" ? (
              <div className="reference-top-menu reference-top-menu-privacy">
                {privacyOptions.map((option) => (
                  <button key={option.id} type="button" onClick={() => handlePrivacySelect(option.id)} className="liquid-menu-row">
                    {option.label}
                  </button>
                ))}
              </div>
            ) : null}
            {openTopMenu === "hints" ? (
              <div className="reference-top-menu reference-top-menu-hints">
                <HintStrip dashboard={dashboard} />
              </div>
            ) : null}
          </div>

          <div className="reference-window-actions">
            <Button
              size="icon"
              title={activeView === "intelligence" ? "Artifact Space" : "Intelligence Center"}
              onMouseEnter={() => void import("./components/IntelligenceCenterView")}
              onFocus={() => void import("./components/IntelligenceCenterView")}
              onClick={() => setActiveView((current) => current === "intelligence" ? null : "intelligence")}
              className="reference-round-action"
            >
              <BrainCircuit className="h-5 w-5" />
            </Button>
            <Button
              size="icon"
              title="M.I.C.A Lautstärke"
              onClick={() => setOpenTopMenu(openTopMenu === "volume" ? null : "volume")}
              className="reference-round-action"
            >
              <Volume2 className="h-5 w-5" />
            </Button>
            {openTopMenu === "volume" ? (
              <div className="reference-volume-popover">
                <span>{voiceVolume}%</span>
                <input
                  type="range"
                  min={0}
                  max={200}
                  value={voiceVolume}
                  onChange={(event) => setVoiceVolume(Number(event.target.value))}
                  onPointerUp={(event) => handleVoiceVolumeCommit(Number(event.currentTarget.value))}
                  onKeyUp={(event) => handleVoiceVolumeCommit(Number(event.currentTarget.value))}
                />
              </div>
            ) : null}
            <Button
              size="icon"
              title="Settings"
              onClick={() => setIsSettingsModalOpen(true)}
              className="reference-round-action"
            >
              <Settings className="h-5 w-5" />
            </Button>
            <Button
              size="icon"
              title={theme === "dark" ? "Light Mode" : "Dark Mode"}
              onClick={handleThemeToggle}
              className="reference-round-action"
            >
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
          </div>
        </header>

        {workspace === "agent-hub" ? (
          <div className="agent-hub-host">
            <ViewErrorBoundary viewKey="agent-hub"><AgentHubView /></ViewErrorBoundary>
          </div>
        ) : (
        <div className={`reference-main-grid ${isArtifactPanelOpen ? "reference-main-grid-open" : "reference-main-grid-closed"}`}>
          <section className="reference-stage">
            {activeView !== null ? (
              <div className="h-full min-h-0 w-full overflow-hidden px-3 pb-3 pt-2 lg:px-5 lg:pb-5">
                {renderActiveView()}
              </div>
            ) : (
              <>
            <div className="reference-centerpiece">
              <MicaHead speaking={isSpeaking} mode={faceMode} />
              <VoicePulse speaking={isSpeaking} />
              <div className="reference-ready">
                <div>Alles klar. Ich bin bereit.</div>
                <span>Wie kann ich dir helfen?</span>
              </div>
            </div>

            <button type="button" className="reference-mode-card">
              <span className="reference-mode-icon"><Radio className="h-5 w-5" /></span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-white/85">Aktiver Modus</span>
                <span className="mt-1 block text-base font-medium text-[#8ed6ff]">{activeMode?.label ?? "Focus"}</span>
                <span className="mt-2 block text-sm leading-4 text-white/65">Störungen minimiert<br />Fokus maximiert</span>
              </span>
              <ChevronDown className="h-5 w-5 -rotate-90 text-white/85" />
            </button>

            <div className="reference-bottom-tools">
              <Button size="icon" onClick={() => setOpenTopMenu(openTopMenu === "volume" ? null : "volume")} className="reference-small-control" title="M.I.C.A Lautstärke">
                <Volume2 className="h-4 w-4" />
              </Button>
              <Button size="icon" onClick={handleThemeToggle} className="reference-small-control" title={theme === "dark" ? "Light Mode" : "Dark Mode"}>
                {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
            </div>

            <div className="reference-command-wrap">
              <CommandPalette
                value={commandInput}
                inputRef={commandInputRef}
                placeholder="Befehl eingeben oder sprechen..."
                examples={commandExamples}
                sending={isCommandSending}
                onChange={setCommandInput}
                onSubmit={handleCommandPaletteSubmit}
                onExample={handleCommandExample}
              />
            </div>
              </>
            )}
          </section>

          {isArtifactPanelOpen ? (
            <ReferenceArtifactPanel
              artifacts={artifacts}
              artifactTab={artifactTab}
              onArtifactTab={setArtifactTab}
              onFullscreen={handleFullscreen}
              onShare={handleShare}
              onSave={handleSaveVisibleArtifact}
            />
          ) : null}
          <button
            type="button"
            onClick={() => setIsArtifactPanelOpen((open) => !open)}
            className="reference-sidebar-toggle"
            aria-label={isArtifactPanelOpen ? "Seitenleiste einklappen" : "Seitenleiste ausklappen"}
          >
            {isArtifactPanelOpen ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
          </button>
        </div>
        )}
      </main>

      {isSettingsModalOpen ? (
        <Suspense fallback={null}>
          <SettingsModal
            isOpen={isSettingsModalOpen}
            onClose={() => setIsSettingsModalOpen(false)}
            onSaved={handleSettingsSaved}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
