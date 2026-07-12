import { memo, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, BookOpen, Bot, BrainCircuit, Check, CheckCircle2, ChevronRight,
  Boxes, CircleDashed, CircleDollarSign, Clock3, Copy, Database, Download, FileJson, FlaskConical, FolderTree, Gauge, GitBranch, History,
  Command, KanbanSquare, ListChecks, Loader2, Pause, Pencil, Play, Plus, RefreshCw, Save, Search,
  Network, ShieldCheck, ShieldX, SlidersHorizontal, Sparkles, Square, Terminal, Trash2, Trophy, Upload, Users, Wrench, X,
} from "lucide-react";
import { micaApi } from "../lib/api";
import "../../styles/capability-center.css";
import type {
  ActionRecordPayload, ApprovalPayload, ApprovalsPayload, CommandCenterPayload,
  PlatformAgent, PlatformAgentRun, PlatformPayload, PlatformWorkflow, TaskPipeline, TaskPipelinesPayload,
} from "../lib/types";

type HubTab = "hub" | "tasks" | "agents" | "flows" | "approvals" | "activity";
type AgentTone = "cyan" | "amber" | "emerald" | "blue" | "violet" | "rose";

type HubAgent = {
  id: string;
  name: string;
  role: string;
  description: string;
  model: string;
  status: string;
  tone: AgentTone;
  task: string;
  progress: number;
  source?: PlatformAgent;
};

const NAV: Array<{ id: HubTab; label: string; icon: typeof Activity }> = [
  { id: "hub", label: "Hub", icon: BrainCircuit },
  { id: "tasks", label: "Aufgaben", icon: KanbanSquare },
  { id: "agents", label: "Agenten", icon: Users },
  { id: "flows", label: "Abläufe", icon: GitBranch },
  { id: "approvals", label: "Freigaben", icon: ShieldCheck },
  { id: "activity", label: "Aktivität", icon: Activity },
];

const ROLE_PRESETS: Array<Omit<HubAgent, "model" | "status" | "task" | "progress">> = [
  { id: "orchestrator", name: "Orchestrator", role: "Koordination", description: "Koordiniert Aufgaben und Agenten", tone: "cyan" },
  { id: "planner", name: "Planer", role: "Planung", description: "Erstellt Pläne und Abhängigkeiten", tone: "amber" },
  { id: "research", name: "Recherche", role: "Information & Recherche", description: "Findet und prüft Informationen", tone: "emerald" },
  { id: "execution", name: "Ausführung", role: "Umsetzung", description: "Führt sichere Arbeitsschritte aus", tone: "blue" },
  { id: "review", name: "Review", role: "Qualität", description: "Prüft Ergebnisse und Evidenz", tone: "violet" },
  { id: "monitor", name: "Monitor", role: "Überwachung", description: "Überwacht Prozesse und Systeme", tone: "rose" },
];

const AGENT_TEMPLATES: Array<{ id: string; name: string; description: string; draft: Omit<AgentDraft, "id" | "name"> }> = [
  { id: "research", name: "Research Analyst", description: "Quellen finden, vergleichen und mit Evidenz zusammenfassen", draft: { model: "quality", prompt: "Recherchiere gründlich, trenne Fakten von Annahmen und liefere überprüfbare Quellen sowie ein kompaktes Fazit.", tools: ["web_search"], knowledge: ["local-documents", "mica-memory"], permissions: ["tools:execute", "knowledge:read", "artifacts:write"], parameters: JSON.stringify({ temperature: 0.2, max_tokens: 2400, role: "research" }, null, 2), visibility: "private", owner: "u-admin" } },
  { id: "builder", name: "Implementation Agent", description: "Plant, implementiert und verifiziert technische Änderungen", draft: { model: "quality", prompt: "Setze den Auftrag in kleinen, überprüfbaren Schritten um. Bewahre bestehende Änderungen, teste proportional zum Risiko und dokumentiere Evidenz.", tools: ["file_controller", "code_helper"], knowledge: ["local-documents", "mica-memory"], permissions: ["tools:execute", "tools:write", "knowledge:read", "artifacts:write"], parameters: JSON.stringify({ temperature: 0.15, max_tokens: 3200, role: "execution" }, null, 2), visibility: "private", owner: "u-admin" } },
  { id: "reviewer", name: "Quality Reviewer", description: "Prüft Ergebnisse, Risiken, Tests und offene Annahmen", draft: { model: "quality", prompt: "Prüfe Arbeit unabhängig gegen Ziel, Sicherheitsgrenzen und aktuelle Evidenz. Melde konkrete Findings nach Priorität und bestätige nur belegte Ergebnisse.", tools: ["code_helper"], knowledge: ["local-documents", "mica-memory"], permissions: ["tools:execute", "knowledge:read", "artifacts:read"], parameters: JSON.stringify({ temperature: 0.1, max_tokens: 2200, role: "review" }, null, 2), visibility: "team", owner: "u-admin" } },
  { id: "monitor", name: "Operations Monitor", description: "Beobachtet Läufe, Fehler, Budgets und blockierte Arbeit", draft: { model: "local", prompt: "Überwache Systemzustand und Agentenläufe. Eskaliere Abweichungen knapp mit Ursache, Auswirkung und nächstem sicheren Schritt.", tools: [], knowledge: ["mica-memory"], permissions: ["knowledge:read", "artifacts:read"], parameters: JSON.stringify({ temperature: 0.1, max_tokens: 1200, role: "monitor" }, null, 2), visibility: "team", owner: "u-admin" } },
];

const statusLabel = (status: string) => {
  const value = status.toLowerCase();
  if (["running", "active", "ready"].includes(value)) return value === "running" ? "Läuft" : "Aktiv";
  if (["completed", "passed", "ok"].includes(value)) return "Erledigt";
  if (["paused", "blocked"].includes(value)) return value === "paused" ? "Pausiert" : "Blockiert";
  if (value === "stopped") return "Gestoppt";
  return status || "Bereit";
};

const progressFor = (pipeline?: TaskPipeline) => {
  if (!pipeline?.steps.length) return 0;
  return Math.round((pipeline.steps.filter((step) => step.status === "completed").length / pipeline.steps.length) * 100);
};

function Empty({ children }: { children: string }) {
  return <div className="agent-hub-empty"><CircleDashed />{children}</div>;
}

function StatusDot({ status }: { status: string }) {
  return <span className={`agent-hub-status-dot agent-hub-status-${status.toLowerCase()}`} aria-hidden="true" />;
}

function AgentAvatar({ agent, large = false }: { agent: HubAgent; large?: boolean }) {
  return (
    <div className={`agent-hub-avatar agent-hub-tone-${agent.tone} ${large ? "agent-hub-avatar-large" : ""}`}>
      <div className="agent-hub-avatar-head"><span /><span /></div>
      <div className="agent-hub-avatar-body" />
    </div>
  );
}

function ApprovalCard({ item, busy, onDecide }: { item: ApprovalPayload; busy: boolean; onDecide: (item: ApprovalPayload, approve: boolean) => void }) {
  return (
    <article className="agent-hub-approval-card">
      <div className="agent-hub-row-between">
        <strong>{item.summary || item.action}</strong>
        <span className={`agent-hub-risk agent-hub-risk-${item.risk_level}`}>{item.risk_level || "offen"}</span>
      </div>
      <p>{item.reason || `Tool ${item.tool_name} möchte ${item.action} ausführen.`}</p>
      <div className="agent-hub-consequence"><AlertTriangle />Auswirkung: Die Aktion erhält Zugriff im Rahmen der angezeigten Berechtigung.</div>
      <div className="agent-hub-approval-actions">
        <button disabled={busy} onClick={() => onDecide(item, false)}><X />Ablehnen</button>
        <button disabled={busy} onClick={() => onDecide(item, true)} className="agent-hub-primary"><Check />Freigeben</button>
      </div>
    </article>
  );
}

function PipelineRow({ pipeline, busy, onAction }: { pipeline: TaskPipeline; busy: boolean; onAction: (pipeline: TaskPipeline, action: string) => void }) {
  const progress = progressFor(pipeline);
  return (
    <article className="agent-hub-pipeline-row">
      <div className="agent-hub-row-between">
        <div className="agent-hub-min"><strong>{pipeline.goal}</strong><span>{pipeline.steps.length} Schritte · {statusLabel(pipeline.status)}</span></div>
        <button className="agent-hub-icon-button" disabled={busy || pipeline.status === "completed"} onClick={() => onAction(pipeline, pipeline.status === "paused" ? "resume" : "pause")} title={pipeline.status === "paused" ? "Fortsetzen" : "Pausieren"}>
          {pipeline.status === "paused" ? <Play /> : <Pause />}
        </button>
      </div>
      <div className="agent-hub-progress"><span style={{ width: `${progress}%` }} /></div>
      <div className="agent-hub-row-between agent-hub-meta"><span>{progress}%</span><span>{new Date(pipeline.updated_at).toLocaleString("de-AT")}</span></div>
    </article>
  );
}

export const AgentHubView = memo(function AgentHubView() {
  const [tab, setTab] = useState<HubTab>("hub");
  const [platform, setPlatform] = useState<PlatformPayload | null>(null);
  const [pipelines, setPipelines] = useState<TaskPipelinesPayload>({ pipelines: [], active: [] });
  const [approvals, setApprovals] = useState<ApprovalsPayload>({ permission_level: "normal", pending: [] });
  const [commandCenter, setCommandCenter] = useState<CommandCenterPayload | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState("research");
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");

  const load = useCallback(async () => {
    try {
      const [nextPlatform, nextPipelines, nextApprovals, nextCenter] = await Promise.all([
        micaApi.getPlatform(), micaApi.getTaskPipelines(), micaApi.getApprovals(), micaApi.getCommandCenter(),
      ]);
      setPlatform(nextPlatform);
      setPipelines({
        ...nextPipelines,
        pipelines: Array.isArray(nextPipelines?.pipelines) ? nextPipelines.pipelines : [],
        active: Array.isArray(nextPipelines?.active) ? nextPipelines.active : [],
      });
      setApprovals({
        ...nextApprovals,
        permission_level: nextApprovals?.permission_level || "normal",
        pending: Array.isArray(nextApprovals?.pending) ? nextApprovals.pending : [],
      });
      setCommandCenter(nextCenter);
      setLastUpdated(new Date()); setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Agent-Hub-Daten konnten nicht geladen werden.");
    }
  }, []);

  useEffect(() => {
    void load();
    let liveRefreshTimer: number | null = null;
    const unsubscribe = micaApi.subscribeToLiveEvents(() => {
      if (liveRefreshTimer !== null) window.clearTimeout(liveRefreshTimer);
      liveRefreshTimer = window.setTimeout(() => {
        liveRefreshTimer = null;
        void load();
      }, 300);
    });
    const timer = window.setInterval(() => void load(), 30_000);
    return () => {
      unsubscribe();
      window.clearInterval(timer);
      if (liveRefreshTimer !== null) window.clearTimeout(liveRefreshTimer);
    };
  }, [load]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setCommandOpen((open) => !open); }
      if (event.key === "Escape") setCommandOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const activePipeline = pipelines.active[0] ?? pipelines.pipelines.find((item) => !["completed", "cancelled"].includes(item.status));
  const agents = useMemo<HubAgent[]>(() => ROLE_PRESETS.map((preset, index) => {
    const real = platform?.agents.find((agent) => agent.id === preset.id);
    const agentRun = platform?.agent_runs?.find((run) => run.agent_id === preset.id && ["running", "paused"].includes(run.status));
    const pipeline = pipelines.active[index % Math.max(pipelines.active.length, 1)] ?? activePipeline;
    const isWorking = Boolean(agentRun || (pipeline && index < Math.min(4, pipeline.steps.length + 1)));
    return {
      ...preset,
      model: real?.model || (index === 5 ? "lokal" : "Standardmodell"),
      status: agentRun?.status || (isWorking ? (pipeline?.status || "running") : "ready"),
      task: agentRun?.assignment || (isWorking ? pipeline?.goal || "Systemstatus auswerten" : "Bereit für einen Auftrag"),
      progress: agentRun ? 35 : isWorking ? progressFor(pipeline) : 0,
      source: real,
    };
  }), [activePipeline, pipelines.active, platform?.agent_runs, platform?.agents]);
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0];
  const actions = commandCenter?.recent_actions ?? [];
  const runningCount = pipelines.active.length + (platform?.runs.filter((run) => run.status === "running").length ?? 0);
  const commands = [
    ...NAV.map((item) => ({ id: `open-${item.id}`, label: `${item.label} öffnen`, hint: "Ansicht", icon: item.icon, run: () => setTab(item.id) })),
    { id: "new-agent", label: "Neuen Agenten erstellen", hint: "Agenten", icon: Plus, run: () => { setTab("agents"); window.setTimeout(() => window.dispatchEvent(new CustomEvent("mica:new-agent")), 0); } },
    { id: "new-run", label: "Neuen Auftrag eingeben", hint: "Lauf", icon: Play, run: () => window.setTimeout(() => (document.querySelector(".agent-hub-goal input") as HTMLInputElement | null)?.focus(), 0) },
    { id: "refresh", label: "Alle Hub-Daten aktualisieren", hint: "System", icon: RefreshCw, run: () => void load() },
  ].filter((item) => `${item.label} ${item.hint}`.toLowerCase().includes(commandQuery.trim().toLowerCase()));

  const startRun = async () => {
    const value = goal.trim(); if (!value) return;
    setBusy("start"); setError(null);
    try {
      const result = await micaApi.taskPipelineAction({ action: "create", goal: value });
      setPipelines({ ...result.task_pipelines, pipelines: result.task_pipelines?.pipelines ?? [], active: result.task_pipelines?.active ?? [] }); setGoal(""); setTab("hub");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Lauf konnte nicht gestartet werden."); }
    finally { setBusy(null); }
  };

  const pipelineAction = async (pipeline: TaskPipeline, action: string) => {
    setBusy(pipeline.id);
    try { const result = await micaApi.taskPipelineAction({ action, pipeline_id: pipeline.id }); setPipelines({ ...result.task_pipelines, pipelines: result.task_pipelines?.pipelines ?? [], active: result.task_pipelines?.active ?? [] }); setError(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Pipeline-Aktion fehlgeschlagen."); }
    finally { setBusy(null); }
  };

  const decideApproval = async (item: ApprovalPayload, approve: boolean) => {
    setBusy(`${item.tool_name}:${item.action}`);
    try { setApprovals(approve ? await micaApi.approveAction(item) : await micaApi.denyAction(item)); setError(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Freigabe konnte nicht verarbeitet werden."); }
    finally { setBusy(null); }
  };

  return (
    <div className="agent-hub-shell">
      <aside className="agent-hub-nav" aria-label="Agent-Hub Navigation">
        <nav className="agent-hub-icon-rail">{NAV.map(({ id, label, icon: Icon }) => (
          <button key={id} aria-label={label} title={label} className={tab === id ? "active" : ""} onClick={() => setTab(id)}><Icon />{id === "approvals" && approvals.pending.length ? <b>{approvals.pending.length}</b> : null}</button>
        ))}</nav>
        <div className="agent-hub-explorer">
          <div className="agent-hub-explorer-head"><span>EXPLORER</span><button title="Explorer-Aktionen">•••</button></div>
          <div className="agent-hub-workspace-name"><FolderTree /><strong>M.I.C.A WORKSPACE</strong></div>
          <div className="agent-hub-tree">
            <div className="agent-hub-tree-group"><button onClick={() => setTab("agents")}><span>⌄</span><Users />agents <b>{agents.length}</b></button>{agents.map((agent) => <button key={agent.id} className={selectedAgent.id === agent.id ? "selected" : ""} onClick={() => { setSelectedAgentId(agent.id); setTab("agents"); }}><i className={`agent-tree-dot agent-hub-tone-${agent.tone}`} />{agent.id}.agent <StatusDot status={agent.status} /></button>)}</div>
            <div className="agent-hub-tree-group"><button onClick={() => setTab("flows")}><span>›</span><GitBranch />workflows <b>{platform?.workflows.length ?? 0}</b></button></div>
            <div className="agent-hub-tree-group"><button onClick={() => setTab("tasks")}><span>›</span><KanbanSquare />tasks <b>{pipelines.pipelines.length}</b></button></div>
            <div className="agent-hub-tree-group"><button><span>›</span><Database />knowledge <b>{platform?.knowledge.length ?? 0}</b></button></div>
            <div className="agent-hub-tree-group"><button onClick={() => setTab("activity")}><span>›</span><Terminal />logs <b>{actions.length}</b></button></div>
          </div>
          <div className="agent-hub-explorer-sections"><button><span>›</span> OUTLINE</button><button><span>›</span> TIMELINE</button></div>
          <div className="agent-hub-nav-footer"><span><StatusDot status={error ? "blocked" : "active"} />{error ? "Eingeschränkt" : "M.I.C.A verbunden"}</span><small>{lastUpdated ? `Stand ${lastUpdated.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" })}` : "Lädt…"}</small></div>
        </div>
      </aside>

      <main className="agent-hub-main">
        <header className="agent-hub-toolbar">
          <div className="agent-hub-goal"><Search /><input value={goal} onChange={(event) => setGoal(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void startRun(); }} placeholder="Ziel oder Auftrag eingeben…" /></div>
          <button className="agent-hub-command-trigger" onClick={() => setCommandOpen(true)} title="Befehlspalette öffnen"><Command /><span>Befehle</span><kbd>Ctrl K</kbd></button>
          <button className="agent-hub-primary agent-hub-start" disabled={!goal.trim() || busy === "start"} onClick={() => void startRun()}>{busy === "start" ? <Loader2 className="agent-hub-spin" /> : <Play />}Lauf starten</button>
          <button className="agent-hub-icon-button" onClick={() => void load()} title="Aktualisieren"><RefreshCw /></button>
        </header>
        {error ? <div className="agent-hub-error"><AlertTriangle />{error}</div> : null}

        <section className="agent-hub-content">
          {tab === "hub" ? (
            <div className="agent-hub-dashboard">
              <div className="agent-hub-canvas">
                <div className="agent-hub-canvas-label"><div><h2>Agent-Hub</h2><span><StatusDot status="active" />{runningCount ? `${runningCount} aktive Läufe` : "Alles normal"}</span></div><small>Räumliche Übersicht</small></div>
                <div className="agent-hub-room" aria-label="Räumliche Übersicht der Agenten">
                  <div className="agent-hub-room-wall agent-hub-wall-vault"><Database /><strong>Wissens-Vault</strong><span>Dokumente, Richtlinien und Wissen</span></div>
                  <div className="agent-hub-room-wall agent-hub-wall-plan"><ListChecks /><strong>Planungs-Board</strong><span>Zeitpläne, Ziele und Abhängigkeiten</span></div>
                  <div className="agent-hub-room-wall agent-hub-wall-kanban"><KanbanSquare /><strong>Kanban-Wand</strong><div className="agent-hub-mini-kanban"><i /><i /><i /><i /><i /></div></div>
                  <div className="agent-hub-room-wall agent-hub-wall-gate"><ShieldCheck /><strong>Security Gate</strong><span>Zugriff und Compliance</span></div>
                  <div className="agent-hub-orchestrator"><BrainCircuit /><strong>Orchestrator</strong><span>Koordiniert Agenten</span></div>
                  <svg className="agent-hub-links" viewBox="0 0 1000 620" preserveAspectRatio="none" aria-hidden="true">{[[500,320,250,235],[500,320,500,145],[500,320,735,235],[500,320,300,440],[500,320,700,440]].map((line, index) => <line key={index} x1={line[0]} y1={line[1]} x2={line[2]} y2={line[3]} />)}</svg>
                  {agents.filter((agent) => agent.id !== "orchestrator").map((agent, index) => <button key={agent.id} className={`agent-hub-station agent-hub-station-${index + 1} ${selectedAgent.id === agent.id ? "selected" : ""}`} onClick={() => setSelectedAgentId(agent.id)}><AgentAvatar agent={agent} /><span><strong>{agent.name}</strong><small><StatusDot status={agent.status} />{statusLabel(agent.status)}</small></span></button>)}
                  <div className="agent-hub-human"><Users /><span><strong>Human-in-the-Loop</strong>Kontrolle und Eingriff</span></div>
                </div>
                <div className="agent-hub-agent-detail">
                  <AgentAvatar agent={selectedAgent} large />
                  <div className="agent-hub-agent-identity"><h3>{selectedAgent.name}</h3><span><StatusDot status={selectedAgent.status} />{statusLabel(selectedAgent.status)}</span><small>{selectedAgent.role}</small><small>Modell: {selectedAgent.model}</small></div>
                  <div className="agent-hub-current-task"><small>Aktueller Auftrag</small><strong>{selectedAgent.task}</strong><div className="agent-hub-progress"><span style={{ width: `${selectedAgent.progress}%` }} /></div><small>{selectedAgent.progress}% abgeschlossen</small></div>
                  <div className="agent-hub-detail-actions"><button disabled={!activePipeline || busy === activePipeline.id} onClick={() => activePipeline && void pipelineAction(activePipeline, activePipeline.status === "paused" ? "resume" : "pause")}>{activePipeline?.status === "paused" ? <Play /> : <Pause />}{activePipeline?.status === "paused" ? "Fortsetzen" : "Pausieren"}</button><button onClick={() => setTab("agents")}><ChevronRight />Details</button></div>
                </div>
              </div>
              <aside className="agent-hub-rail">
                <section><div className="agent-hub-section-title"><span>Ausstehende Freigaben</span><b>{approvals.pending.length}</b></div>{approvals.pending.slice(0, 2).map((item) => <ApprovalCard key={`${item.tool_name}:${item.action}`} item={item} busy={busy === `${item.tool_name}:${item.action}`} onDecide={decideApproval} />)}{!approvals.pending.length ? <Empty>Keine offenen Freigaben</Empty> : null}</section>
                <section><div className="agent-hub-section-title"><span>Aktive Läufe</span><button onClick={() => setTab("flows")}>Alle anzeigen</button></div>{pipelines.active.slice(0, 3).map((pipeline) => <PipelineRow key={pipeline.id} pipeline={pipeline} busy={busy === pipeline.id} onAction={pipelineAction} />)}{!pipelines.active.length ? <Empty>Keine aktiven Läufe</Empty> : null}</section>
                <section><div className="agent-hub-section-title"><span>Modellnutzung</span><button onClick={() => setTab("agents")}>Agenten öffnen</button></div><div className="agent-hub-model-usage">{Array.from(new Set(agents.map((agent) => agent.model))).map((model) => { const count = agents.filter((agent) => agent.model === model).length; return <div key={model}><span>{model}</span><div><i style={{ width: `${Math.max(14, count / agents.length * 100)}%` }} /></div><b>{count}</b></div>; })}</div><div className="agent-hub-stat-grid"><div><b>{platform?.agents.length ?? 0}</b><span>Agenten</span></div><div><b>{platform?.workflows.length ?? 0}</b><span>Workflows</span></div></div></section>
              </aside>
              <div className="agent-hub-live"><div className="agent-hub-terminal-tabs"><button className="active"><Terminal />TERMINAL</button><button>OUTPUT</button><button>EVENT LOG</button><button onClick={() => setTab("activity")}>PROBLEME {actions.filter((item) => item.status === "error").length || ""}</button><span>{selectedAgent.name} ▾</span></div><ActivityTable actions={actions.slice(0, 5)} /><div className="agent-hub-terminal-status"><span><StatusDot status="active" />Agenten online {agents.filter((agent) => agent.status !== "blocked").length}/{agents.length}</span><span>UTF-8</span><span>M.I.C.A · Connected</span></div></div>
            </div>
          ) : null}
          {tab === "tasks" ? <TasksView pipelines={pipelines.pipelines} busy={busy} onAction={pipelineAction} /> : null}
          {tab === "agents" ? <AgentsView platform={platform} selected={selectedAgentId} onSelect={setSelectedAgentId} onPlatform={setPlatform} /> : null}
          {tab === "flows" ? <FlowsView pipelines={pipelines.pipelines} platform={platform} busy={busy} onAction={pipelineAction} onPlatform={setPlatform} /> : null}
          {tab === "approvals" ? <ApprovalsView approvals={approvals} busy={busy} onDecide={decideApproval} /> : null}
          {tab === "activity" ? <ActivityView actions={actions} /> : null}
        </section>
      </main>
      {commandOpen ? <div className="agent-hub-command-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) setCommandOpen(false); }}><section className="agent-hub-command" role="dialog" aria-modal="true" aria-label="Befehlspalette"><header><Search /><input autoFocus value={commandQuery} onChange={(event) => setCommandQuery(event.target.value)} placeholder="Ansichten und Aktionen durchsuchen…" /><kbd>Esc</kbd></header><div>{commands.map(({ id, label, hint, icon: Icon, run }) => <button key={id} onClick={() => { run(); setCommandOpen(false); setCommandQuery(""); }}><Icon /><span>{label}</span><small>{hint}</small></button>)}{!commands.length ? <Empty>Kein passender Befehl</Empty> : null}</div><footer><span>↑↓ navigieren</span><span>↵ auswählen</span><span>Minimal sichtbar, sofort erreichbar</span></footer></section></div> : null}
    </div>
  );
});

function ViewHeader({ icon: Icon, title, subtitle }: { icon: typeof Activity; title: string; subtitle: string }) { return <header className="agent-hub-view-header"><div><Icon /><span><h2>{title}</h2><p>{subtitle}</p></span></div></header>; }

function TasksView({ pipelines, busy, onAction }: { pipelines: TaskPipeline[]; busy: string | null; onAction: (pipeline: TaskPipeline, action: string) => void }) {
  const columns = [
    { id: "backlog", title: "Backlog", items: pipelines.filter((p) => p.status === "ready") },
    { id: "active", title: "Aktiv", items: pipelines.filter((p) => p.status === "running" || p.status === "paused") },
    { id: "review", title: "Review", items: pipelines.filter((p) => p.status === "blocked" || p.requires_approval) },
    { id: "done", title: "Erledigt", items: pipelines.filter((p) => p.status === "completed") },
  ];
  return <div className="agent-hub-view"><ViewHeader icon={KanbanSquare} title="Aufgaben" subtitle="Alle Aufträge und ihr aktueller Arbeitsstand" /><div className="agent-hub-kanban">{columns.map((column) => <section key={column.id}><div className="agent-hub-section-title"><span>{column.title}</span><b>{column.items.length}</b></div>{column.items.map((pipeline) => <article key={pipeline.id} className="agent-hub-task-card"><div className="agent-hub-row-between"><strong>{pipeline.goal}</strong>{["running", "paused"].includes(pipeline.status) ? <button className="agent-hub-icon-button" disabled={busy === pipeline.id} title={pipeline.status === "paused" ? "Fortsetzen" : "Pausieren"} onClick={() => onAction(pipeline, pipeline.status === "paused" ? "resume" : "pause")}>{pipeline.status === "paused" ? <Play /> : <Pause />}</button> : null}</div><p>{pipeline.steps.filter((step) => step.status === "completed").length}/{pipeline.steps.length} Schritte erledigt</p><div className="agent-hub-progress"><span style={{ width: `${progressFor(pipeline)}%` }} /></div>{pipeline.requires_approval ? <small><ShieldCheck />Freigabe erforderlich</small> : null}</article>)}{!column.items.length ? <Empty>Keine Aufgaben</Empty> : null}</section>)}</div></div>;
}

type AgentDraft = {
  id: string; name: string; model: string; prompt: string; tools: string[]; knowledge: string[];
  permissions: string[]; parameters: string; visibility: string; owner: string;
};

const emptyAgentDraft = (): AgentDraft => ({
  id: "", name: "", model: "fast", prompt: "Du bist ein hilfreicher M.I.C.A-Agent.", tools: [], knowledge: [],
  permissions: ["tools:execute", "knowledge:read"], parameters: JSON.stringify({ temperature: 0.4, max_tokens: 1600 }, null, 2), visibility: "private", owner: "u-admin",
});

const draftFromAgent = (agent: PlatformAgent): AgentDraft => ({
  id: agent.id, name: agent.name, model: agent.model, prompt: agent.prompt, tools: [...agent.tools], knowledge: [...agent.knowledge],
  permissions: [...(agent.permissions ?? [])], parameters: JSON.stringify(agent.parameters ?? {}, null, 2), visibility: agent.visibility, owner: agent.owner,
});

const hubAgentFromPlatform = (agent: PlatformAgent, index: number, run?: PlatformAgentRun): HubAgent => ({
  id: agent.id, name: agent.name, role: agent.visibility === "private" ? "Privater Agent" : "Team-Agent",
  description: agent.prompt || "M.I.C.A Agent", model: agent.model, status: run?.status || "ready",
  tone: (["cyan", "amber", "emerald", "blue", "violet", "rose"] as AgentTone[])[index % 6],
  task: run?.assignment || "Bereit für einen Auftrag", progress: run?.status === "stopped" ? 100 : run ? 35 : 0, source: agent,
});

function AgentEditor({ draft, platform, busy, onChange, onClose, onSave }: {
  draft: AgentDraft; platform: PlatformPayload; busy: boolean; onChange: (next: AgentDraft) => void; onClose: () => void; onSave: () => void;
}) {
  const toggle = (key: "tools" | "knowledge" | "permissions", value: string) => onChange({ ...draft, [key]: draft[key].includes(value) ? draft[key].filter((item) => item !== value) : [...draft[key], value] });
  const permissionOptions = Array.from(new Set(["tools:execute", "tools:write", "knowledge:read", "knowledge:write", "workflows:execute", "artifacts:read", "artifacts:write", ...platform.roles.flatMap((role) => role.permissions)])).sort();
  const toolOptions = Array.from(new Set([...draft.tools, ...platform.tools.map((tool) => tool.name)])).sort();
  const knowledgeOptions = Array.from(new Set([...draft.knowledge, ...platform.knowledge.map((source) => source.id)])).sort();
  return <div className="agent-manager-modal" role="dialog" aria-modal="true" aria-label={draft.id ? "Agent bearbeiten" : "Agent erstellen"}>
    <div className="agent-manager-modal-card">
      <header><div><Bot /><span><h3>{draft.id ? "Agent bearbeiten" : "Agent erstellen"}</h3><p>Identität, Modell, Fähigkeiten und Sicherheitsgrenzen konfigurieren</p></span></div><button onClick={onClose} aria-label="Schließen"><X /></button></header>
      <div className="agent-manager-editor-grid">
        <label>Name<input value={draft.name} onChange={(e) => onChange({ ...draft, name: e.target.value })} placeholder="Research Agent" /></label>
        <label>ID<input value={draft.id} disabled={Boolean(draft.id)} onChange={(e) => onChange({ ...draft, id: e.target.value })} placeholder="research-agent" /></label>
        <label>Modell<input list="agent-models" value={draft.model} onChange={(e) => onChange({ ...draft, model: e.target.value })} /><datalist id="agent-models">{Array.from(new Set(["fast", "local", "quality", ...platform.agents.map((item) => item.model)])).map((model) => <option key={model} value={model} />)}</datalist></label>
        <label>Sichtbarkeit<select value={draft.visibility} onChange={(e) => onChange({ ...draft, visibility: e.target.value })}><option value="private">Privat</option><option value="team">Team</option><option value="public">Öffentlich</option></select></label>
        <label className="wide">System-Prompt<textarea value={draft.prompt} onChange={(e) => onChange({ ...draft, prompt: e.target.value })} rows={5} /></label>
        <fieldset><legend><Wrench />Tools</legend><div className="agent-manager-checks">{toolOptions.map((name) => { const tool = platform.tools.find((item) => item.name === name); return <label key={name}><input type="checkbox" checked={draft.tools.includes(name)} onChange={() => toggle("tools", name)} />{name}<small>{tool?.kind || "Agent-Tool"}</small></label>; })}{!toolOptions.length ? <span>Keine Tools registriert</span> : null}</div></fieldset>
        <fieldset><legend><BookOpen />Wissensquellen</legend><div className="agent-manager-checks">{knowledgeOptions.map((id) => { const source = platform.knowledge.find((item) => item.id === id); return <label key={id}><input type="checkbox" checked={draft.knowledge.includes(id)} onChange={() => toggle("knowledge", id)} />{source?.target || source?.source || id}<small>{source?.status || "Agent-Quelle"}</small></label>; })}{!knowledgeOptions.length ? <span>Keine Quellen registriert</span> : null}</div></fieldset>
        <fieldset><legend><ShieldCheck />Berechtigungen</legend><div className="agent-manager-checks">{permissionOptions.map((permission) => <label key={permission}><input type="checkbox" checked={draft.permissions.includes(permission)} onChange={() => toggle("permissions", permission)} />{permission}</label>)}</div></fieldset>
        <label>Parameter (JSON)<textarea className="agent-manager-code" value={draft.parameters} onChange={(e) => onChange({ ...draft, parameters: e.target.value })} rows={8} /></label>
      </div>
      <footer><button onClick={onClose}>Abbrechen</button><button className="agent-hub-primary" disabled={busy || !draft.name.trim()} onClick={onSave}>{busy ? <Loader2 className="agent-hub-spin" /> : <Save />}Agent speichern</button></footer>
    </div>
  </div>;
}

function FleetOperations({ platform, onPlatform, onClose }: { platform: PlatformPayload; onPlatform: (next: PlatformPayload) => void; onClose: () => void }) {
  const [goal, setGoal] = useState("");
  const [selected, setSelected] = useState<string[]>(platform.agents.filter((agent) => agent.id !== "orchestrator").slice(0, 3).map((agent) => agent.id));
  const [maxTokens, setMaxTokens] = useState(2400);
  const [maxCost, setMaxCost] = useState(0.02);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const metrics = platform.metric_events?.length ? platform.metric_events : platform.metrics;
  const totals = metrics.reduce((sum, item) => ({ tokens: sum.tokens + (item.tokens || 0), cost: sum.cost + (item.cost || 0), latency: sum.latency + (item.latency_ms || 0), calls: sum.calls + (item.tool_calls || 0) }), { tokens: 0, cost: 0, latency: 0, calls: 0 });
  const failures = platform.agent_runs?.filter((run) => ["failed", "blocked", "stopped"].includes(run.status)).length ?? 0;
  const latestChain = platform.agent_chain_runs?.[0];
  const toggle = (id: string) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const delegate = async () => {
    if (!goal.trim() || !selected.length) return;
    setBusy(true); setError(null);
    try { const response = await micaApi.platformAction("run_agent_chain", { agent_id: "orchestrator", agent_ids: selected, goal: goal.trim(), max_tokens: maxTokens, max_cost: maxCost }); onPlatform(response.platform); setGoal(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Delegationskette konnte nicht gestartet werden."); }
    finally { setBusy(false); }
  };
  return <div className="agent-manager-modal" role="dialog" aria-modal="true" aria-label="Fleet Operations"><div className="agent-fleet-operations">
    <header><div><Gauge /><span><h3>Fleet Operations</h3><p>Teams delegieren, Budgets begrenzen und Flottenzustand beobachten</p></span></div><button onClick={onClose} aria-label="Schließen"><X /></button></header>
    <div className="agent-fleet-stats"><article><Bot /><span><small>Agenten</small><strong>{platform.agents.length}</strong></span></article><article><Activity /><span><small>Tool-Aufrufe</small><strong>{totals.calls}</strong></span></article><article><CircleDollarSign /><span><small>Kosten</small><strong>${totals.cost.toFixed(4)}</strong></span></article><article><AlertTriangle /><span><small>Auffällig</small><strong>{failures}</strong></span></article></div>
    <div className="agent-fleet-grid"><section><div className="agent-hub-section-title"><span>Delegationsteam</span><b>{selected.length}</b></div><div className="agent-fleet-team">{platform.agents.filter((agent) => agent.id !== "orchestrator").map((agent) => <label key={agent.id}><input type="checkbox" checked={selected.includes(agent.id)} onChange={() => toggle(agent.id)} /><span><strong>{agent.name}</strong><small>{String(agent.parameters?.role || agent.model)}</small></span></label>)}</div></section><section className="agent-fleet-delegate"><div className="agent-hub-section-title"><span>Gemeinsamer Auftrag</span><small>Orchestrator → Team</small></div><textarea rows={4} value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="Ziel, Kontext und erwartetes Ergebnis…" /><div className="agent-fleet-budget"><label>Tokenlimit<input type="number" min={300} step={100} value={maxTokens} onChange={(event) => setMaxTokens(Number(event.target.value))} /></label><label>Kostenlimit ($)<input type="number" min={0} step={0.005} value={maxCost} onChange={(event) => setMaxCost(Number(event.target.value))} /></label></div>{error ? <div className="agent-hub-error"><AlertTriangle />{error}</div> : null}<button className="agent-hub-primary" disabled={busy || !goal.trim() || !selected.length} onClick={() => void delegate()}>{busy ? <Loader2 className="agent-hub-spin" /> : <Network />}Delegieren</button></section></div>
    <section className="agent-fleet-chain"><div className="agent-hub-section-title"><span>Letzte Delegationskette</span><b>{platform.agent_chain_runs?.length ?? 0}</b></div>{latestChain ? <><div className="agent-fleet-chain-head"><span><StatusDot status={latestChain.status} /><strong>{latestChain.goal}</strong></span><small>{latestChain.budget ? `${latestChain.budget.used_tokens}/${latestChain.budget.max_tokens || "∞"} Tokens · $${latestChain.budget.used_cost.toFixed(4)}` : latestChain.status}</small></div><div className="agent-fleet-chain-steps">{latestChain.steps.map((step, index) => <article key={`${latestChain.id}-${step.subagent_id}`}><b>{index + 1}</b><span><strong>{step.name}</strong><small>{step.role} · {step.tokens_in + step.tokens_out} Tokens</small></span><CheckCircle2 /></article>)}</div>{latestChain.budget?.reason ? <div className="agent-hub-error"><AlertTriangle />{latestChain.budget.reason}</div> : null}</> : <Empty>Noch keine Delegationskette</Empty>}</section>
  </div></div>;
}

function QualityLab({ platform, onPlatform, onClose }: { platform: PlatformPayload; onPlatform: (next: PlatformPayload) => void; onClose: () => void }) {
  const agents = platform.agents;
  const [baseline, setBaseline] = useState(agents[0]?.id || "");
  const [challenger, setChallenger] = useState(agents[1]?.id || agents[0]?.id || "");
  const [dataset, setDataset] = useState(platform.evaluation_datasets[0]?.id || "manual");
  const [minScore, setMinScore] = useState(0.8);
  const [maxRegressions, setMaxRegressions] = useState(0);
  const [caseInput, setCaseInput] = useState("");
  const [caseExpected, setCaseExpected] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const latest = platform.evaluation_runs?.[0];
  const evaluation = platform.evaluations.find((item) => item.id === latest?.evaluation_id) ?? platform.evaluations[0];
  const gate = latest?.gate ?? { status: "unknown", min_score: minScore, max_regressions: maxRegressions };
  const act = async (action: string, payload: Record<string, unknown>) => { setBusy(action); setError(null); try { const response = await micaApi.platformAction(action, payload); onPlatform(response.platform); return response.result; } catch (reason) { setError(reason instanceof Error ? reason.message : "Quality-Aktion fehlgeschlagen."); return null; } finally { setBusy(null); } };
  const run = async () => { if (!baseline || !challenger || baseline === challenger) return; await act("run_evaluation", { id: evaluation?.id || "eval-agent-hub", agents: [baseline, challenger], baseline, challenger, dataset, min_score: minScore, max_regressions: maxRegressions }); };
  const addCase = async () => { if (!caseInput.trim() || !caseExpected.trim()) return; const name = `Agent Hub Golden ${Date.now().toString().slice(-4)}`; const result = await act("save_evaluation_dataset", { name, cases: [{ id: `case-${Date.now()}`, input: caseInput.trim(), expected: caseExpected.trim(), rubric: "groundedness, correctness, clarity" }] }); if (result && typeof result === "object" && "id" in result) { setDataset(String((result as { id: string }).id)); setCaseInput(""); setCaseExpected(""); } };
  const winnerId = latest?.winner || "";
  const winnerName = latest ? agents.find((agent) => agent.id === winnerId)?.name || winnerId || "–" : "–";
  return <div className="agent-manager-modal" role="dialog" aria-modal="true" aria-label="Quality Lab"><div className="quality-lab">
    <header><div><FlaskConical /><span><h3>Quality Lab</h3><p>Agenten vergleichen und Qualitätsregressionen vor dem Einsatz stoppen</p></span></div><button onClick={onClose} aria-label="Schließen"><X /></button></header>
    <div className="quality-lab-grid"><section className="quality-lab-config"><div className="agent-hub-section-title"><span>Vergleichslauf</span><small>Baseline vs. Challenger</small></div><div className="quality-lab-versus"><label>Baseline<select value={baseline} onChange={(event) => setBaseline(event.target.value)}>{agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select></label><b>VS</b><label>Challenger<select value={challenger} onChange={(event) => setChallenger(event.target.value)}>{agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select></label></div><label>Golden Dataset<select value={dataset} onChange={(event) => setDataset(event.target.value)}>{platform.evaluation_datasets.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.cases.length} Fälle</option>)}</select></label><div className="quality-lab-gates"><label>Mindestscore<input type="number" min={0} max={1} step={0.01} value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} /></label><label>Max. Regressionen<input type="number" min={0} step={1} value={maxRegressions} onChange={(event) => setMaxRegressions(Number(event.target.value))} /></label></div>{error ? <div className="agent-hub-error"><AlertTriangle />{error}</div> : null}<button className="agent-hub-primary" disabled={busy !== null || !baseline || !challenger || baseline === challenger} onClick={() => void run()}>{busy === "run_evaluation" ? <Loader2 className="agent-hub-spin" /> : <Play />}Evaluation starten</button></section><section className="quality-lab-case"><div className="agent-hub-section-title"><span>Testfall hinzufügen</span><small>Neues Golden Dataset</small></div><label>Eingabe<textarea rows={3} value={caseInput} onChange={(event) => setCaseInput(event.target.value)} placeholder="Nutzerfrage oder Aufgabe…" /></label><label>Erwartetes Ergebnis<textarea rows={3} value={caseExpected} onChange={(event) => setCaseExpected(event.target.value)} placeholder="Welche Eigenschaften muss eine gute Antwort erfüllen?" /></label><button disabled={busy !== null || !caseInput.trim() || !caseExpected.trim()} onClick={() => void addCase()}><Plus />Testfall speichern</button></section></div>
    <section className="quality-lab-results"><div className="agent-hub-section-title"><span>Letztes Ergebnis</span><b>{platform.evaluation_runs.length}</b></div>{latest ? <><div className="quality-lab-score"><article className={gate.status === "passed" ? "passed" : "failed"}><span>Regression Gate</span><strong>{gate.status === "passed" ? "BESTANDEN" : "BLOCKIERT"}</strong><small>≥ {(gate.min_score * 100).toFixed(0)}% · max. {gate.max_regressions} Regressionen</small></article><article><span>Gesamtscore</span><strong>{(latest.score * 100).toFixed(1)}%</strong><small>{latest.cases.length} bewertete Antworten</small></article><article><span>Gewinner</span><strong><Trophy />{winnerName}</strong><small>ELO {evaluation?.elo?.[winnerId] || 1200}</small></article><article><span>Regressionen</span><strong>{latest.regressions}</strong><small>{latest.regressions ? "Prüfung erforderlich" : "Keine erkannt"}</small></article></div><div className="quality-lab-cases">{latest.cases.slice(0, 8).map((item) => <div key={`${latest.id}-${item.case_id}-${item.agent}`}><span><StatusDot status={item.regression ? "failed" : "completed"} /><strong>{agents.find((agent) => agent.id === item.agent)?.name || item.agent}</strong></span><span>{item.case_id}</span><b>{(item.score * 100).toFixed(1)}%</b></div>)}</div></> : <Empty>Noch keine Evaluation durchgeführt</Empty>}</section>
  </div></div>;
}

function KnowledgeDeliveryCenter({ platform, selectedAgentId, onPlatform, onClose }: { platform: PlatformPayload; selectedAgentId: string; onPlatform: (platform: PlatformPayload) => void; onClose: () => void }) {
  const [tab, setTab] = useState<"knowledge" | "artifacts" | "publish">("knowledge");
  const [busy, setBusy] = useState<string | null>(null); const [error, setError] = useState<string | null>(null);
  const [sourceId, setSourceId] = useState(platform.knowledge[0]?.id || ""); const [sourceName, setSourceName] = useState(""); const [sourceUri, setSourceUri] = useState(""); const [schedule, setSchedule] = useState("manual"); const [query, setQuery] = useState("");
  const [searchResult, setSearchResult] = useState(platform.knowledge_searches?.[0] || null);
  const [artifactId, setArtifactId] = useState(platform.artifacts[0]?.id || ""); const [artifactTitle, setArtifactTitle] = useState(""); const [artifactKind, setArtifactKind] = useState("report"); const [artifactContent, setArtifactContent] = useState(platform.artifacts[0]?.content || ""); const [newArtifactContent, setNewArtifactContent] = useState("");
  const [agentId, setAgentId] = useState(selectedAgentId || platform.agents[0]?.id || ""); const [publishKind, setPublishKind] = useState("web-app"); const [auth, setAuth] = useState("workspace"); const [rateLimit, setRateLimit] = useState(60);
  const initialReadiness = platform.deployment.readiness as { status?: string; checks?: Array<{ name: string; status: string; detail?: string }> } | undefined;
  const [readiness, setReadiness] = useState(initialReadiness || null);
  const artifact = platform.artifacts.find((item) => item.id === artifactId); const publication = platform.publishing.find((item) => item.agent_id === agentId && item.kind === publishKind);
  const act = async (action: string, payload: Record<string, unknown>) => { setBusy(action); setError(null); try { const response = await micaApi.platformAction(action, payload); onPlatform(response.platform); return response.result; } catch (reason) { setError(reason instanceof Error ? reason.message : "Aktion konnte nicht ausgeführt werden."); return null; } finally { setBusy(null); } };
  const addSource = async () => { if (!sourceName.trim()) return; const result = await act("save_knowledge_source", { target: sourceName.trim(), source: "Folder", uri: sourceUri.trim(), schedule }); if (result && typeof result === "object" && "id" in result) setSourceId(String((result as { id: string }).id)); };
  const search = async () => { if (!query.trim()) return; const result = await act("search_knowledge", { query: query.trim(), source_ids: sourceId ? [sourceId] : [] }); if (result && typeof result === "object" && "results" in result) setSearchResult(result as NonNullable<typeof searchResult>); };
  const createArtifact = async () => { if (!artifactTitle.trim()) return; const result = await act("create_artifact", { title: artifactTitle.trim(), kind: artifactKind, content: newArtifactContent }); if (result && typeof result === "object" && "id" in result) { setArtifactId(String((result as { id: string }).id)); setArtifactContent(newArtifactContent); setArtifactTitle(""); setNewArtifactContent(""); } };
  const publish = () => act("publish_agent", { agent_id: agentId, kind: publishKind, policy: { auth, rate_limit_per_minute: rateLimit, allowed_groups: ["core"], audit_invocations: true } });
  return <div className="agent-manager-modal" role="dialog" aria-modal="true" aria-label="Knowledge & Delivery Center"><div className="knowledge-delivery">
    <header><div><Boxes /><span><h3>Knowledge & Delivery</h3><p>Wissen einspeisen, Ergebnisse versionieren und Agenten sicher ausliefern</p></span></div><button onClick={onClose} aria-label="Schließen"><X /></button></header>
    <nav>{[["knowledge", Database, "Wissen"], ["artifacts", FileJson, "Artefakte"], ["publish", Upload, "Veröffentlichen"]].map(([id, Icon, label]) => <button key={String(id)} className={tab === id ? "active" : ""} onClick={() => setTab(id as typeof tab)}><Icon />{String(label)}</button>)}</nav>
    {error ? <div className="agent-hub-error"><AlertTriangle />{error}</div> : null}
    {tab === "knowledge" ? <div className="knowledge-delivery-grid"><section><div className="agent-hub-section-title"><span>Wissensquellen</span><b>{platform.knowledge.length}</b></div><div className="delivery-list">{platform.knowledge.map((source) => <button key={source.id} className={sourceId === source.id ? "active" : ""} onClick={() => { setSourceId(source.id); setSchedule(source.schedule || "manual"); }}><Database /><span><strong>{source.target || source.id}</strong><small>{source.source} · {source.status} · {source.rag}</small></span><StatusDot status={source.status} /></button>)}</div><div className="delivery-actions"><button disabled={!sourceId || busy !== null} onClick={() => void act("sync_knowledge", { id: sourceId })}>{busy === "sync_knowledge" ? <Loader2 className="agent-hub-spin" /> : <RefreshCw />}Synchronisieren</button><select value={schedule} onChange={(event) => setSchedule(event.target.value)}><option value="manual">Manuell</option><option value="watch">Live beobachten</option><option value="hourly">Stündlich</option><option value="daily">Täglich</option><option value="*/15 * * * *">Alle 15 Minuten</option></select><button disabled={!sourceId || busy !== null} onClick={() => void act("schedule_knowledge_sync", { id: sourceId, schedule })}><Clock3 />Speichern</button></div></section><aside><div className="agent-hub-section-title"><span>Quelle hinzufügen</span></div><label>Name<input value={sourceName} onChange={(event) => setSourceName(event.target.value)} placeholder="Projektwissen" /></label><label>Ordner oder URI<input value={sourceUri} onChange={(event) => setSourceUri(event.target.value)} placeholder="C:\\Wissen oder Connector-URI" /></label><button className="agent-hub-primary" disabled={!sourceName.trim() || busy !== null} onClick={() => void addSource()}><Plus />Quelle anlegen</button><div className="agent-hub-section-title"><span>Hybrid-Suche testen</span></div><label>Suchanfrage<input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void search(); }} placeholder="Was weiß M.I.C.A darüber?" /></label><button disabled={!query.trim() || busy !== null} onClick={() => void search()}><Search />Suchen</button>{searchResult ? <div className="delivery-search-results"><small>{searchResult.retrieval}</small>{searchResult.results.slice(0, 4).map((item) => <article key={item.chunk_id}><p>{item.text}</p><span>{item.source_id}</span><b>{Math.round(item.rerank_score * 100)}%</b></article>)}</div> : null}</aside></div> : null}
    {tab === "artifacts" ? <div className="knowledge-delivery-grid"><section><div className="agent-hub-section-title"><span>Artefakte & Versionen</span><b>{platform.artifacts.length}</b></div><div className="delivery-list">{platform.artifacts.map((item) => <button key={item.id} className={artifactId === item.id ? "active" : ""} onClick={() => { setArtifactId(item.id); setArtifactContent(item.content); }}><FileJson /><span><strong>{item.title}</strong><small>{item.kind} · Version {item.version || 1} · {item.render_status || "ready"}</small></span><StatusDot status={item.render_status || "ready"} /></button>)}</div>{artifact ? <div className="delivery-artifact-detail"><div><strong>{artifact.title}</strong><small>{artifact.versions?.length || 1} Versionen</small></div><textarea rows={8} value={artifactContent} onChange={(event) => setArtifactContent(event.target.value)} /><footer><button disabled={busy !== null} onClick={() => void act("version_artifact", { id: artifact.id, content: artifactContent })}><History />Neue Version</button><button className="agent-hub-primary" disabled={busy !== null} onClick={() => void act("render_artifact", { id: artifact.id })}><Play />Rendern</button></footer>{artifact.last_render ? <pre>{artifact.last_render.preview}</pre> : null}</div> : null}</section><aside><div className="agent-hub-section-title"><span>Artefakt erstellen</span></div><label>Titel<input value={artifactTitle} onChange={(event) => setArtifactTitle(event.target.value)} placeholder="Ergebnisbericht" /></label><label>Typ<select value={artifactKind} onChange={(event) => setArtifactKind(event.target.value)}><option value="report">Bericht</option><option value="note">Notiz</option><option value="dashboard">Dashboard</option><option value="html">HTML</option><option value="json">JSON</option></select></label><label>Inhalt<textarea rows={10} value={newArtifactContent} onChange={(event) => setNewArtifactContent(event.target.value)} placeholder="Markdown, HTML, JSON oder Klartext…" /></label><button className="agent-hub-primary" disabled={!artifactTitle.trim() || busy !== null} onClick={() => void createArtifact()}><Plus />Artefakt erstellen</button></aside></div> : null}
    {tab === "publish" ? <div className="knowledge-delivery-grid"><section><div className="agent-hub-section-title"><span>Veröffentlichungen</span><b>{platform.publishing.length}</b></div><div className="delivery-list">{platform.publishing.map((item) => <button key={item.id} className={publication?.id === item.id ? "active" : ""} onClick={() => { setAgentId(item.agent_id); setPublishKind(item.kind); setAuth(item.policy?.auth || "workspace"); setRateLimit(item.policy?.rate_limit_per_minute || 60); }}><Upload /><span><strong>{platform.agents.find((agent) => agent.id === item.agent_id)?.name || item.agent_id}</strong><small>{item.kind} · {item.url} · {item.policy?.auth || "workspace"}</small></span><StatusDot status={item.status} /></button>)}</div><div className="delivery-readiness"><div className="agent-hub-section-title"><span>Deployment Readiness</span><button disabled={busy !== null} onClick={async () => { const result = await act("check_deployment_readiness", { target: "production" }); if (result && typeof result === "object") setReadiness(result as typeof readiness); }}><ShieldCheck />Prüfen</button></div>{readiness ? <><strong className={readiness.status === "ready" ? "ready" : "attention"}>{readiness.status === "ready" ? "BEREIT" : "PRÜFUNG ERFORDERLICH"}</strong><div>{readiness.checks?.slice(0, 12).map((check) => <span key={check.name}><StatusDot status={check.status} />{check.name}<small>{check.detail}</small></span>)}</div></> : <Empty>Noch keine Produktionsprüfung ausgeführt</Empty>}</div></section><aside><div className="agent-hub-section-title"><span>Agent ausliefern</span></div><label>Agent<select value={agentId} onChange={(event) => setAgentId(event.target.value)}>{platform.agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select></label><label>Ziel<select value={publishKind} onChange={(event) => setPublishKind(event.target.value)}><option value="web-app">Web App</option><option value="embeddable-chat">Embeddable Chat</option><option value="rest-api">REST API</option><option value="mcp-server">MCP Server</option></select></label><label>Authentifizierung<select value={auth} onChange={(event) => setAuth(event.target.value)}><option value="workspace">Workspace</option><option value="api-key">API Key</option><option value="public">Öffentlich</option></select></label><label>Rate Limit / Minute<input type="number" min={1} value={rateLimit} onChange={(event) => setRateLimit(Number(event.target.value))} /></label>{publication ? <div className="delivery-publication-current"><CheckCircle2 /><span><strong>Bereits veröffentlicht</strong><small>{publication.url}</small></span></div> : null}<button className="agent-hub-primary" disabled={!agentId || busy !== null} onClick={() => void publish()}>{busy === "publish_agent" ? <Loader2 className="agent-hub-spin" /> : <Upload />}{publication ? "Neu veröffentlichen" : "Veröffentlichen"}</button>{publication ? <button disabled={busy !== null} onClick={() => void act("save_publish_policy", { id: publication.id, auth, rate_limit_per_minute: rateLimit, allowed_groups: ["core"], audit_invocations: true })}><Save />Policy speichern</button> : null}</aside></div> : null}
    <footer><span>{platform.knowledge.length} Quellen</span><span>{platform.artifacts.length} Artefakte</span><span>{platform.publishing.length} Veröffentlichungen</span><span>Versioniert und auditierbar</span></footer>
  </div></div>;
}

function RuntimeAccessCenter({ platform, selectedAgentId, onPlatform, onClose }: { platform: PlatformPayload; selectedAgentId: string; onPlatform: (platform: PlatformPayload) => void; onClose: () => void }) {
  const [tab, setTab] = useState<"integrations" | "secrets" | "team">("integrations"); const [busy, setBusy] = useState<string | null>(null); const [error, setError] = useState<string | null>(null);
  const [secretName, setSecretName] = useState(""); const [envVar, setEnvVar] = useState(""); const [secretScope, setSecretScope] = useState("connectors");
  const [groupId, setGroupId] = useState(platform.groups[0]?.id || "core"); const group = platform.groups.find((item) => item.id === groupId); const [members, setMembers] = useState<string[]>(group?.members || []); const [access, setAccess] = useState("execute"); const [visibility, setVisibility] = useState("team");
  const integrationItems = [
    ...platform.knowledge.map((item) => ({ id: item.id, category: "knowledge", name: item.target, kind: item.source, status: item.connector_status || item.status, detail: item.uri || item.rag })),
    ...platform.identity_providers.map((item) => ({ id: item.id, category: "identity", name: item.name, kind: item.type, status: item.status, detail: item.issuer || item.ldap_url || "Identity Provider" })),
    ...platform.marketplace.filter((item) => item.kind === "connector").map((item) => ({ id: item.id, category: "marketplace", name: item.name, kind: item.kind, status: item.installed && item.enabled ? "ready" : "needs-setup", detail: item.description })),
    ...(platform.mcp.servers || []).map((raw) => { const item = raw as Record<string, unknown>; return { id: String(item.id || item.name || "mcp"), category: "mcp", name: String(item.name || item.id || "MCP Server"), kind: "MCP", status: String(item.status || "registered"), detail: String(item.url || item.command || "Deferred server") }; }),
  ];
  const act = async (action: string, payload: Record<string, unknown>) => { setBusy(`${action}:${String(payload.id || "")}`); setError(null); try { const response = await micaApi.platformAction(action, payload); onPlatform(response.platform); return response.result; } catch (reason) { setError(reason instanceof Error ? reason.message : "Runtime-Aktion fehlgeschlagen."); return null; } finally { setBusy(null); } };
  const saveSecret = async () => { if (!secretName.trim() || !envVar.trim()) return; const result = await act("save_secret_reference", { name: secretName.trim(), env_var: envVar.trim().toUpperCase(), scope: secretScope }); if (result) { setSecretName(""); setEnvVar(""); } };
  const selectGroup = (id: string) => { setGroupId(id); setMembers(platform.groups.find((item) => item.id === id)?.members || []); };
  const toggleMember = (id: string) => setMembers((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  return <div className="agent-manager-modal" role="dialog" aria-modal="true" aria-label="Runtime & Access Center"><div className="runtime-access">
    <header><div><Network /><span><h3>Runtime & Access</h3><p>Integrationen, Secret-Referenzen und Zusammenarbeit zentral steuern</p></span></div><button onClick={onClose} aria-label="Schließen"><X /></button></header>
    <nav>{[["integrations", Network, "Integrationen"], ["secrets", ShieldCheck, "Secrets"], ["team", Users, "Team & Zugriff"]].map(([id, Icon, label]) => <button key={String(id)} className={tab === id ? "active" : ""} onClick={() => setTab(id as typeof tab)}><Icon />{String(label)}</button>)}</nav>
    {error ? <div className="agent-hub-error"><AlertTriangle />{error}</div> : null}
    {tab === "integrations" ? <div className="runtime-access-body"><section className="runtime-integrations"><div className="agent-hub-section-title"><span>Verbundene Systeme</span><b>{integrationItems.length}</b></div>{integrationItems.map((item) => { const latest = platform.integration_checks?.find((check) => check.category === item.category && check.integration_id === item.id); const status = latest?.status || item.status; return <article key={`${item.category}:${item.id}`}><div className="runtime-integration-icon"><Network /></div><span><strong>{item.name}</strong><small>{item.kind} · {item.detail}</small></span><span className="runtime-integration-status"><StatusDot status={status} />{statusLabel(status)}</span><button disabled={busy !== null} onClick={() => void act("test_integration", { category: item.category, id: item.id })}>{busy === `test_integration:${item.id}` ? <Loader2 className="agent-hub-spin" /> : <RefreshCw />}Testen</button></article>; })}{!integrationItems.length ? <Empty>Keine Integrationen registriert</Empty> : null}</section><aside><div className="agent-hub-section-title"><span>Letzte Prüfungen</span></div>{platform.integration_checks?.slice(0, 10).map((check) => <div className="runtime-check" key={check.id}><StatusDot status={check.status} /><span><strong>{check.integration_id}</strong><small>{check.detail}</small></span><time>{new Date(check.checked_at).toLocaleTimeString("de-AT")}</time></div>)}{!platform.integration_checks?.length ? <Empty>Noch keine Integration geprüft</Empty> : null}</aside></div> : null}
    {tab === "secrets" ? <div className="runtime-access-body"><section><div className="agent-hub-section-title"><span>Secret-Referenzen</span><b>{platform.secret_references?.length || 0}</b></div><div className="runtime-secrets">{platform.secret_references?.map((secret) => <article key={secret.id}><ShieldCheck /><span><strong>{secret.name}</strong><small>{secret.env_var} · {secret.scope}</small></span><span><StatusDot status={secret.status} />{secret.status === "configured" ? "Konfiguriert" : "Fehlt"}</span><button title="Referenz entfernen" disabled={busy !== null} onClick={() => void act("delete_secret_reference", { id: secret.id })}><Trash2 /></button></article>)}</div><div className="runtime-secret-note"><ShieldCheck /><p>Geheime Werte werden nie im Agent-Hub gespeichert oder angezeigt. M.I.C.A verwaltet ausschließlich Namen von Umgebungsvariablen und prüft, ob sie im Runtime-Prozess vorhanden sind.</p></div></section><aside><div className="agent-hub-section-title"><span>Referenz hinzufügen</span></div><label>Name<input value={secretName} onChange={(event) => setSecretName(event.target.value)} placeholder="Produktions-API" /></label><label>Umgebungsvariable<input value={envVar} onChange={(event) => setEnvVar(event.target.value.replace(/[^a-zA-Z0-9_]/g, "").toUpperCase())} placeholder="MICA_PROD_API_KEY" /></label><label>Gültigkeitsbereich<select value={secretScope} onChange={(event) => setSecretScope(event.target.value)}><option value="connectors">Connectoren</option><option value="models">Modelle</option><option value="publishing">Veröffentlichung</option><option value="workspace">Workspace</option></select></label><button className="agent-hub-primary" disabled={!secretName.trim() || envVar.length < 2 || busy !== null} onClick={() => void saveSecret()}><Plus />Referenz speichern</button></aside></div> : null}
    {tab === "team" ? <div className="runtime-access-body"><section><div className="agent-hub-section-title"><span>Gruppen & Mitglieder</span><b>{platform.groups.length}</b></div><div className="runtime-group-tabs">{platform.groups.map((item) => <button className={item.id === groupId ? "active" : ""} key={item.id} onClick={() => selectGroup(item.id)}>{item.name}<small>{item.members.length}</small></button>)}</div><div className="runtime-members">{platform.users.map((user) => <label key={user.id}><input type="checkbox" checked={members.includes(user.id)} onChange={() => toggleMember(user.id)} /><span><strong>{user.name}</strong><small>{user.email} · {user.roles.join(", ")}</small></span></label>)}</div><button disabled={!group || busy !== null} onClick={() => void act("save_group", { id: groupId, name: group?.name, members })}><Save />Mitglieder speichern</button></section><aside><div className="agent-hub-section-title"><span>Agent teilen</span></div><label>Agent<select value={selectedAgentId} disabled><option>{platform.agents.find((item) => item.id === selectedAgentId)?.name || selectedAgentId}</option></select></label><label>Gruppe<select value={groupId} onChange={(event) => selectGroup(event.target.value)}>{platform.groups.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Zugriff<select value={access} onChange={(event) => setAccess(event.target.value)}><option value="read">Lesen</option><option value="execute">Ausführen</option><option value="write">Bearbeiten</option><option value="owner">Verwalten</option></select></label><label>Sichtbarkeit<select value={visibility} onChange={(event) => setVisibility(event.target.value)}><option value="private">Privat</option><option value="team">Team</option><option value="workspace">Workspace</option></select></label><button className="agent-hub-primary" disabled={!selectedAgentId || !groupId || busy !== null} onClick={() => void act("share_agent", { agent_id: selectedAgentId, visibility, subjects: [{ type: "group", id: groupId, access }] })}><Users />Zugriff speichern</button><div className="runtime-acl-preview"><small>Effektive Regel</small><code>agent:{selectedAgentId} → group:{groupId}:{access}</code></div></aside></div> : null}
    <footer><span>{integrationItems.length} Integrationen</span><span>{platform.secret_references?.length || 0} Secret-Referenzen</span><span>{platform.users.length} Mitglieder</span><span>Least privilege · Audit aktiv</span></footer>
  </div></div>;
}

function CapabilityCenter({ platform, selectedAgentId, onPlatform, onClose }: { platform: PlatformPayload; selectedAgentId: string; onPlatform: (platform: PlatformPayload) => void; onClose: () => void }) {
  const [tab, setTab] = useState<"tools" | "mcp" | "marketplace">("tools"); const [busy, setBusy] = useState<string | null>(null); const [error, setError] = useState<string | null>(null); const [query, setQuery] = useState("");
  const [selectedToolId, setSelectedToolId] = useState(platform.tools[0]?.id || ""); const selectedTool = platform.tools.find((item) => item.id === selectedToolId); const agent = platform.agents.find((item) => item.id === selectedAgentId) || platform.agents[0];
  const [toolName, setToolName] = useState(""); const [toolKind, setToolKind] = useState("function"); const [toolCode, setToolCode] = useState("return parameters"); const [testParameters, setTestParameters] = useState("{}"); const [mcpQuery, setMcpQuery] = useState("");
  const visibleTools = platform.tools.filter((item) => `${item.name} ${item.kind} ${item.status} ${item.description || ""}`.toLowerCase().includes(query.toLowerCase())); const visibleMarket = platform.marketplace.filter((item) => `${item.name} ${item.kind} ${item.description} ${item.trust}`.toLowerCase().includes(query.toLowerCase()));
  const act = async (action: string, payload: Record<string, unknown>) => { setBusy(`${action}:${String(payload.id || payload.name || "")}`); setError(null); try { const response = await micaApi.platformAction(action, payload); onPlatform(response.platform); return response.result; } catch (reason) { setError(reason instanceof Error ? reason.message : "Capability-Aktion fehlgeschlagen."); return null; } finally { setBusy(null); } };
  const createTool = async () => { if (!toolName.trim()) return; const result = await act("save_tool", { name: toolName.trim(), kind: toolKind, code: toolCode, status: "draft", schema: { type: "object" }, test_parameters: {} }); if (result && typeof result === "object" && "id" in result) { setSelectedToolId(String((result as { id: string }).id)); setToolName(""); } };
  const testTool = async () => { if (!selectedTool) return; let parameters: Record<string, unknown>; try { parameters = JSON.parse(testParameters) as Record<string, unknown>; } catch { setError("Testparameter müssen gültiges JSON sein."); return; } await act("test_tool", { id: selectedTool.id, parameters }); };
  const toggleToolForAgent = async () => { if (!selectedTool || !agent) return; const tools = agent.tools.includes(selectedTool.name) ? agent.tools.filter((name) => name !== selectedTool.name) : [...agent.tools, selectedTool.name]; await act("save_agent", { ...agent, tools }); };
  const marketplaceAction = async (item: PlatformPayload["marketplace"][number]) => { if (item.installed) return act("set_marketplace_item_enabled", { id: item.id, enabled: !item.enabled }); if (item.review_status === "pending" || item.review_status === "needs-review") return act("review_marketplace_item", { id: item.id, verdict: "approved", notes: "Im Capability Center geprüft" }); if (item.verification?.status !== "passed") return act("verify_marketplace_item", { id: item.id, signature: item.signature === "unsigned" ? `mica:${item.checksum?.replace(/^sha256:/, "") || item.id}` : item.signature }); return act("install_marketplace_item", { id: item.id }); };
  return <div className="agent-manager-modal" role="dialog" aria-modal="true" aria-label="Capability Center"><div className="capability-center">
    <header><div><Wrench /><span><h3>Capability Center</h3><p>Tools, MCP und geprüfte Erweiterungen kontrolliert bereitstellen</p></span></div><button onClick={onClose} aria-label="Schließen"><X /></button></header>
    <nav>{[["tools", Wrench, "Tools"], ["mcp", Network, "MCP"], ["marketplace", Boxes, "Marketplace"]].map(([id, Icon, label]) => <button key={String(id)} className={tab === id ? "active" : ""} onClick={() => setTab(id as typeof tab)}><Icon />{String(label)}</button>)}<label><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Capabilities filtern…" /></label></nav>
    {error ? <div className="agent-hub-error"><AlertTriangle />{error}</div> : null}
    {tab === "tools" ? <div className="capability-body"><section><div className="agent-hub-section-title"><span>Tool Registry</span><b>{visibleTools.length}</b></div><div className="capability-list">{visibleTools.map((tool) => <button key={tool.id} className={tool.id === selectedToolId ? "active" : ""} onClick={() => { setSelectedToolId(tool.id); setTestParameters(JSON.stringify(tool.test_parameters || {}, null, 2)); }}><Wrench /><span><strong>{tool.name}</strong><small>{tool.kind} · {tool.description || tool.test_result || "Registriertes Tool"}</small></span><span><StatusDot status={tool.status} />{statusLabel(tool.status)}</span></button>)}</div>{selectedTool ? <div className="capability-tool-detail"><div><span><strong>{selectedTool.name}</strong><small>{selectedTool.id} · {selectedTool.kind}</small></span><span><StatusDot status={selectedTool.status} />{selectedTool.status}</span></div><p>{selectedTool.test_result || "Noch nicht getestet"}</p><label>Testparameter<textarea rows={5} value={testParameters} onChange={(event) => setTestParameters(event.target.value)} /></label><footer><button disabled={busy !== null} onClick={() => void testTool()}>{busy?.startsWith("test_tool:") ? <Loader2 className="agent-hub-spin" /> : <FlaskConical />}Testen</button><button className={agent?.tools.includes(selectedTool.name) ? "assigned" : "agent-hub-primary"} disabled={!agent || busy !== null} onClick={() => void toggleToolForAgent()}>{agent?.tools.includes(selectedTool.name) ? <Check /> : <Plus />}{agent?.tools.includes(selectedTool.name) ? `${agent.name} zugewiesen` : `${agent?.name || "Agent"} zuweisen`}</button></footer></div> : null}</section><aside><div className="agent-hub-section-title"><span>Tool erstellen</span></div><label>Name<input value={toolName} onChange={(event) => setToolName(event.target.value)} placeholder="normalize_input" /></label><label>Typ<select value={toolKind} onChange={(event) => setToolKind(event.target.value)}><option value="function">Function</option><option value="filter">Filter</option><option value="pipe">Pipe</option><option value="action">Action</option></select></label><label>Code<textarea rows={11} value={toolCode} onChange={(event) => setToolCode(event.target.value)} /></label><button className="agent-hub-primary" disabled={!toolName.trim() || busy !== null} onClick={() => void createTool()}><Plus />Tool speichern</button><div className="capability-security-note"><ShieldCheck /><span><strong>Sandbox-Test</strong><small>Custom-Code läuft isoliert, zeitbegrenzt und ohne Netzwerkzugriff.</small></span></div></aside></div> : null}
    {tab === "mcp" ? <div className="capability-body"><section><div className="agent-hub-section-title"><span>Deferred MCP Tools</span><b>{platform.mcp.tools.length}</b></div><div className="capability-mcp-search"><input value={mcpQuery} onChange={(event) => setMcpQuery(event.target.value)} placeholder="Server und Tools durchsuchen…" /><button disabled={busy !== null} onClick={() => void act("discover_mcp_tools", { query: mcpQuery })}><Search />Entdecken</button></div><div className="capability-list">{platform.mcp.tools.map((tool) => <article key={`${tool.server_id}:${tool.name}`}><Network /><span><strong>{tool.name}</strong><small>{tool.server_id || "local"} · {tool.description}</small></span><span><StatusDot status={tool.loaded ? "ready" : "deferred"} />{tool.loaded ? "Geladen" : "Deferred"}</span><button disabled={busy !== null} onClick={() => void act(tool.loaded ? "unload_mcp_tool" : "load_mcp_tool", { name: tool.name })}>{busy?.endsWith(`:${tool.name}`) ? <Loader2 className="agent-hub-spin" /> : tool.loaded ? <Pause /> : <Download />}{tool.loaded ? "Entladen" : "Laden"}</button></article>)}</div></section><aside><div className="agent-hub-section-title"><span>Runtime-Prinzip</span></div><div className="capability-mcp-flow"><span><Database />Catalog</span><ChevronRight /><span><Search />Discover</span><ChevronRight /><span><Download />Load</span><ChevronRight /><span><Bot />Agent</span></div><p>Tools werden erst bei Bedarf geladen. Das hält den Kontext klein und macht aktive Fähigkeiten jederzeit sichtbar.</p><div className="capability-stat"><strong>{platform.mcp.loaded_tools.length}</strong><span>aktiv geladen</span></div><div className="capability-stat"><strong>{platform.mcp.tools.length - platform.mcp.loaded_tools.length}</strong><span>deferred</span></div></aside></div> : null}
    {tab === "marketplace" ? <div className="capability-market"><div className="agent-hub-section-title"><span>Kuratierter Marketplace</span><b>{visibleMarket.length}</b></div><div className="capability-market-policy"><ShieldCheck /><span><strong>Installations-Gate aktiv</strong><small>Review + Signatur · maximales Risiko {platform.marketplace_policy?.max_risk || "medium"} · verbotene Rechte: {platform.marketplace_policy?.permission_denylist?.join(", ")}</small></span></div><div className="capability-market-list">{visibleMarket.map((item) => <article key={item.id}><div className="capability-market-icon"><Boxes /></div><div><strong>{item.name}</strong><small>{item.description}</small><span><i>{item.kind}</i><i>{item.publisher || item.trust}</i><i>v{item.version}{item.latest_version && item.latest_version !== item.version ? ` → ${item.latest_version}` : ""}</i></span></div><div className="capability-market-security"><span><StatusDot status={item.review_status === "approved" || item.review_status === "verified" ? "ready" : "blocked"} />Review: {item.review_status}</span><span><StatusDot status={item.verification?.status === "passed" ? "ready" : "blocked"} />Signatur: {item.verification?.status || "offen"}</span><span><StatusDot status={item.risk?.level === "high" ? "blocked" : "ready"} />Risiko: {item.risk?.level || "unbekannt"}</span></div><div className="capability-market-actions"><button disabled={busy !== null} onClick={() => void marketplaceAction(item)}>{busy?.endsWith(`:${item.id}`) ? <Loader2 className="agent-hub-spin" /> : item.installed ? item.enabled ? <Pause /> : <Play /> : item.review_status === "pending" ? <ShieldCheck /> : item.verification?.status !== "passed" ? <CheckCircle2 /> : <Download />}{item.installed ? item.enabled ? "Deaktivieren" : "Aktivieren" : item.review_status === "pending" ? "Prüfen" : item.verification?.status !== "passed" ? "Verifizieren" : "Installieren"}</button>{item.installed ? <button className="danger" disabled={busy !== null} onClick={() => void act("uninstall_marketplace_item", { id: item.id })}><Trash2 />Entfernen</button> : null}</div></article>)}</div></div> : null}
    <footer><span>{platform.tools.length} Tools</span><span>{platform.mcp.loaded_tools.length} MCP geladen</span><span>{platform.marketplace.filter((item) => item.installed).length} Erweiterungen installiert</span><span>Review · Signatur · Sandbox</span></footer>
  </div></div>;
}

function AgentsView({ platform, selected, onSelect, onPlatform }: { platform: PlatformPayload | null; selected: string; onSelect: (id: string) => void; onPlatform: (platform: PlatformPayload) => void }) {
  const [draft, setDraft] = useState<AgentDraft | null>(null);
  const [assignment, setAssignment] = useState("");
  const [runModel, setRunModel] = useState("");
  const [importText, setImportText] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showOperations, setShowOperations] = useState(false);
  const [showQuality, setShowQuality] = useState(false);
  const [showDelivery, setShowDelivery] = useState(false);
  const [showRuntime, setShowRuntime] = useState(false);
  const [showCenters, setShowCenters] = useState(false);
  const [showCapabilities, setShowCapabilities] = useState(false);
  const [agentQuery, setAgentQuery] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const open = () => setDraft(emptyAgentDraft());
    window.addEventListener("mica:new-agent", open);
    return () => window.removeEventListener("mica:new-agent", open);
  }, []);
  if (!platform) return <div className="agent-hub-view"><Empty>Agentendaten werden geladen</Empty></div>;
  const realAgents = platform.agents;
  const visibleAgents = realAgents.filter((item) => `${item.name} ${item.id} ${item.model} ${item.visibility}`.toLowerCase().includes(agentQuery.trim().toLowerCase()));
  const agent = realAgents.find((item) => item.id === selected) ?? realAgents[0];
  const runs = (platform.agent_runs ?? []).filter((run) => !agent || run.agent_id === agent.id);
  const invocations = (platform.invocations ?? []).filter((run) => !agent || run.agent_id === agent.id);
  const activeRun = runs.find((run) => ["running", "paused"].includes(run.status));
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0];
  const avatarAgent = agent ? hubAgentFromPlatform(agent, Math.max(0, realAgents.indexOf(agent)), activeRun) : null;

  const action = async (name: string, payload: Record<string, unknown>) => {
    setBusy(name); setError(null);
    try { const result = await micaApi.platformAction(name, payload); onPlatform(result.platform); return result.result; }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Agenten-Aktion fehlgeschlagen."); return null; }
    finally { setBusy(null); }
  };
  const save = async () => {
    if (!draft) return;
    let parameters: Record<string, unknown>;
    try { parameters = JSON.parse(draft.parameters) as Record<string, unknown>; } catch { setError("Parameter müssen gültiges JSON sein."); return; }
    const result = await action("save_agent", { ...draft, parameters });
    if (result && typeof result === "object") { const saved = result as PlatformAgent; onSelect(saved.id); setDraft(null); }
  };
  const duplicate = async () => {
    if (!agent) return;
    const copyId = `${agent.id}-copy-${Date.now().toString().slice(-4)}`;
    const result = await action("save_agent", { ...agent, id: copyId, name: `${agent.name} Kopie`, visibility: "private" });
    if (result && typeof result === "object") onSelect((result as PlatformAgent).id);
  };
  const exportAgent = async () => {
    if (!agent) return;
    const result = await action("export_agent_package", { agent_id: agent.id });
    if (!result || typeof result !== "object") return;
    const pkg = (result as { package?: unknown }).package ?? result;
    const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${agent.id}.mica-agent.json`; anchor.click(); URL.revokeObjectURL(url);
  };
  const importAgent = async () => {
    let pkg: unknown; try { pkg = JSON.parse(importText); } catch { setError("Das Agent-Paket enthält kein gültiges JSON."); return; }
    const result = await action("import_agent_package", { package: pkg, clone: true });
    if (result && typeof result === "object") { const imported = (result as { agent?: PlatformAgent }).agent; if (imported) onSelect(imported.id); setImportText(""); setShowImport(false); }
  };

  return <div className="agent-hub-view agent-manager-view">
    <div className="agent-manager-header"><ViewHeader icon={Users} title="Agenten" subtitle="Agenten erstellen, konfigurieren, ausführen und überwachen" /><div><div className="agent-manager-center-menu"><button className={showCenters ? "active" : ""} onClick={() => setShowCenters((open) => !open)}><Boxes />Center<ChevronRight /></button>{showCenters ? <div role="menu" aria-label="Agent Center"><button role="menuitem" onClick={() => { setShowCapabilities(true); setShowCenters(false); }}><Wrench /><span><strong>Capability Center</strong><small>Tools, MCP und Marketplace</small></span></button><button role="menuitem" onClick={() => { setShowRuntime(true); setShowCenters(false); }}><Network /><span><strong>Runtime & Access</strong><small>Integrationen, Secrets und Teamzugriff</small></span></button><button role="menuitem" onClick={() => { setShowDelivery(true); setShowCenters(false); }}><Database /><span><strong>Knowledge & Delivery</strong><small>Wissen, Artefakte und Veröffentlichung</small></span></button><button role="menuitem" onClick={() => { setShowQuality(true); setShowCenters(false); }}><FlaskConical /><span><strong>Quality Lab</strong><small>Evaluationen und Regression Gates</small></span></button><button role="menuitem" onClick={() => { setShowOperations(true); setShowCenters(false); }}><Gauge /><span><strong>Operations</strong><small>Teams, Budgets und Agentenketten</small></span></button></div> : null}</div><button onClick={() => setShowTemplates(true)}><Sparkles />Vorlagen</button><button onClick={() => setShowImport(true)}><Upload />Importieren</button><button className="agent-hub-primary" onClick={() => setDraft(emptyAgentDraft())}><Bot />Agent erstellen</button></div></div>
    {error ? <div className="agent-hub-error"><AlertTriangle />{error}<button onClick={() => setError(null)}><X /></button></div> : null}
    <div className="agent-manager-layout">
      <aside className="agent-manager-list"><div className="agent-hub-section-title"><span>Registrierte Agenten</span><b>{visibleAgents.length}/{realAgents.length}</b></div><label className="agent-manager-search"><Search /><input value={agentQuery} onChange={(event) => setAgentQuery(event.target.value)} placeholder="Agenten filtern…" /></label>{visibleAgents.map((item) => { const index = realAgents.indexOf(item); const run = (platform.agent_runs ?? []).find((candidate) => candidate.agent_id === item.id && ["running", "paused"].includes(candidate.status)); const cardAgent = hubAgentFromPlatform(item, index, run); return <button key={item.id} className={item.id === agent?.id ? "active" : ""} onClick={() => onSelect(item.id)}><AgentAvatar agent={cardAgent} /><span><strong>{item.name}</strong><small>{item.model} · {item.visibility}</small></span><span className="agent-hub-agent-state"><StatusDot status={run?.status || "ready"} />{statusLabel(run?.status || "ready")}</span></button>; })}{!visibleAgents.length ? <Empty>Keine passenden Agenten</Empty> : null}</aside>
      {agent && avatarAgent ? <main className="agent-manager-detail">
        <header className="agent-manager-profile-head"><AgentAvatar agent={avatarAgent} large /><div><h2>{agent.name}</h2><p>{agent.prompt}</p><span><StatusDot status={activeRun?.status || "ready"} />{statusLabel(activeRun?.status || "ready")} · {agent.model}</span></div><div className="agent-manager-actions"><button onClick={() => setDraft(draftFromAgent(agent))}><Pencil />Bearbeiten</button><button onClick={() => void duplicate()} disabled={busy !== null}><Copy />Duplizieren</button><button onClick={() => void exportAgent()} disabled={busy !== null}><Download />Exportieren</button><button className="danger" onClick={() => setShowDelete(true)}><Trash2 />Löschen</button></div></header>
        <section className="agent-manager-assignment"><div><Play /><span><strong>Auftrag zuweisen</strong><small>Startet einen steuerbaren Lauf mit diesem Agenten</small></span></div><textarea value={assignment} onChange={(e) => setAssignment(e.target.value)} placeholder="Beschreibe Ziel, Kontext und erwartetes Ergebnis…" rows={3} /><div><label>Modell <select value={runModel || agent.model} onChange={(e) => setRunModel(e.target.value)}><option value={agent.model}>{agent.model}</option><option value="fast">fast</option><option value="quality">quality</option><option value="local">local</option></select></label><button className="agent-hub-primary" disabled={!assignment.trim() || busy !== null} onClick={async () => { const result = await action("start_agent_run", { agent_id: agent.id, assignment, model: runModel || agent.model }); if (result) { setAssignment(""); setSelectedRunId((result as PlatformAgentRun).id); } }}><Play />Agent starten</button></div></section>
        <div className="agent-manager-info-grid"><section><Wrench /><span><small>Tools</small><strong>{agent.tools.join(", ") || "Keine"}</strong></span></section><section><BookOpen /><span><small>Wissensquellen</small><strong>{agent.knowledge.join(", ") || "Keine"}</strong></span></section><section><ShieldCheck /><span><small>Berechtigungen</small><strong>{agent.permissions?.join(", ") || "Standard"}</strong></span></section><section><SlidersHorizontal /><span><small>Parameter</small><strong>{Object.entries(agent.parameters).map(([key, value]) => `${key}: ${value}`).join(" · ") || "Standard"}</strong></span></section></div>
        <section className="agent-manager-runs"><div className="agent-hub-section-title"><span><History />Läufe und Logs</span><b>{runs.length + invocations.length}</b></div><div className="agent-manager-run-layout"><div className="agent-manager-run-list">{runs.map((run) => <button key={run.id} className={selectedRun?.id === run.id ? "active" : ""} onClick={() => setSelectedRunId(run.id)}><span><strong>{run.assignment}</strong><small>{new Date(run.started_at).toLocaleString("de-AT")}</small></span><span><StatusDot status={run.status} />{statusLabel(run.status)}</span></button>)}{invocations.map((run) => <button key={run.id}><span><strong>{run.input || "Direkter Aufruf"}</strong><small>{new Date(run.created_at).toLocaleString("de-AT")}</small></span><span><StatusDot status={run.status} />{statusLabel(run.status)}</span></button>)}{!runs.length && !invocations.length ? <Empty>Noch keine Läufe vorhanden</Empty> : null}</div><div className="agent-manager-log">{selectedRun ? <><header><div><strong>{selectedRun.assignment}</strong><small>{selectedRun.id} · {selectedRun.model}</small></div><div>{selectedRun.status === "running" ? <button onClick={() => void action("pause_agent_run", { run_id: selectedRun.id })}><Pause />Pausieren</button> : null}{selectedRun.status === "paused" ? <button onClick={() => void action("resume_agent_run", { run_id: selectedRun.id })}><Play />Fortsetzen</button> : null}{["running", "paused"].includes(selectedRun.status) ? <button className="danger" onClick={() => void action("stop_agent_run", { run_id: selectedRun.id })}><Square />Stoppen</button> : null}</div></header><div className="agent-manager-log-lines">{selectedRun.logs.map((line, index) => <div key={`${line.timestamp}-${index}`}><time>{new Date(line.timestamp).toLocaleTimeString("de-AT")}</time><span className={`level-${line.level}`}>{line.level}</span><p>{line.message}</p></div>)}</div>{selectedRun.result ? <pre>{selectedRun.result}</pre> : null}</> : <Empty>Wähle einen Lauf für Details</Empty>}</div></div></section>
      </main> : <div className="agent-manager-no-selection"><Bot /><h3>Erstelle deinen ersten Agenten</h3><p>Konfiguriere Modell, Prompt, Tools, Wissen und Berechtigungen.</p><button className="agent-hub-primary" onClick={() => setDraft(emptyAgentDraft())}>Agent erstellen</button></div>}
    </div>
    {draft ? <AgentEditor draft={draft} platform={platform} busy={busy === "save_agent"} onChange={setDraft} onClose={() => setDraft(null)} onSave={() => void save()} /> : null}
    {showTemplates ? <div className="agent-manager-modal" role="dialog" aria-modal="true" aria-label="Agentenvorlagen"><div className="agent-manager-templates"><header><div><Sparkles /><span><h3>Agent aus Vorlage</h3><p>Ein sinnvoller Startpunkt – vollständig anpassbar vor dem Speichern</p></span></div><button onClick={() => setShowTemplates(false)}><X /></button></header><div>{AGENT_TEMPLATES.map((template) => <button key={template.id} onClick={() => { setDraft({ id: "", name: template.name, ...template.draft }); setShowTemplates(false); }}><span><strong>{template.name}</strong><small>{template.description}</small></span><ChevronRight /></button>)}</div></div></div> : null}
    {showOperations ? <FleetOperations platform={platform} onPlatform={onPlatform} onClose={() => setShowOperations(false)} /> : null}
    {showQuality ? <QualityLab platform={platform} onPlatform={onPlatform} onClose={() => setShowQuality(false)} /> : null}
    {showDelivery ? <KnowledgeDeliveryCenter platform={platform} selectedAgentId={agent?.id || ""} onPlatform={onPlatform} onClose={() => setShowDelivery(false)} /> : null}
    {showRuntime ? <RuntimeAccessCenter platform={platform} selectedAgentId={agent?.id || ""} onPlatform={onPlatform} onClose={() => setShowRuntime(false)} /> : null}
    {showCapabilities ? <CapabilityCenter platform={platform} selectedAgentId={agent?.id || ""} onPlatform={onPlatform} onClose={() => setShowCapabilities(false)} /> : null}
    {showImport ? <div className="agent-manager-modal" role="dialog" aria-modal="true" aria-label="Agent importieren"><div className="agent-manager-import"><header><div><FileJson /><span><h3>Agent importieren</h3><p>M.I.C.A-Agent-Paket als JSON einfügen</p></span></div><button onClick={() => setShowImport(false)}><X /></button></header><textarea value={importText} onChange={(e) => setImportText(e.target.value)} rows={18} placeholder='{ "format": "mica-agent-package/v1", "manifest": { ... } }' /><footer><button onClick={() => setShowImport(false)}>Abbrechen</button><button className="agent-hub-primary" disabled={!importText.trim() || busy !== null} onClick={() => void importAgent()}><Upload />Importieren</button></footer></div></div> : null}
    {showDelete && agent ? <div className="agent-manager-modal" role="alertdialog" aria-modal="true" aria-label="Agent löschen"><div className="agent-manager-confirm"><ShieldX /><h3>{agent.name} löschen?</h3><p>Der Agent und seine Veröffentlichungen werden entfernt. Abgeschlossene Laufprotokolle bleiben für die Nachvollziehbarkeit erhalten. Aktive Läufe müssen zuerst gestoppt werden.</p><div><button onClick={() => setShowDelete(false)}>Abbrechen</button><button className="danger" disabled={busy !== null} onClick={async () => { const result = await action("delete_agent", { agent_id: agent.id }); if (result) { setShowDelete(false); const remaining = platform.agents.filter((item) => item.id !== agent.id); onSelect(remaining[0]?.id || ""); } }}><Trash2 />Endgültig löschen</button></div></div></div> : null}
  </div>;
}

function WorkflowEditor({ workflow, platform, onPlatform, onClose }: { workflow?: PlatformWorkflow; platform: PlatformPayload; onPlatform: (platform: PlatformPayload) => void; onClose: () => void }) {
  const [activeId, setActiveId] = useState(workflow?.id || "");
  const active = platform.workflows.find((item) => item.id === activeId) ?? workflow;
  const [name, setName] = useState(active?.name || "Neuer Workflow");
  const [nodeLabel, setNodeLabel] = useState("");
  const [nodeType, setNodeType] = useState("agent");
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [edgeLabel, setEdgeLabel] = useState("next");
  const [schedule, setSchedule] = useState(active?.schedule || "manual");
  const [triggerType, setTriggerType] = useState(active?.trigger?.type || "manual");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const act = async (action: string, payload: Record<string, unknown>) => { setBusy(action); setError(null); try { const result = await micaApi.platformAction(action, payload); onPlatform(result.platform); return result.result; } catch (reason) { setError(reason instanceof Error ? reason.message : "Workflow-Aktion fehlgeschlagen."); return null; } finally { setBusy(null); } };
  const create = async () => { const result = await act("save_workflow", { name, nodes: [], edges: [], status: "draft" }); if (result && typeof result === "object" && "id" in result) setActiveId(String((result as PlatformWorkflow).id)); };
  const addNode = async () => { if (!active || !nodeLabel.trim()) return; await act("edit_workflow_node", { workflow_id: active.id, node: { type: nodeType, label: nodeLabel.trim(), x: 12 + (active.nodes.length % 4) * 25, y: 20 + Math.floor(active.nodes.length / 4) * 34, config: { agent_id: nodeType === "agent" ? "orchestrator" : undefined } } }); setNodeLabel(""); };
  const connect = async () => { if (!active || !source || !target || source === target) return; await act("connect_workflow_nodes", { workflow_id: active.id, source, target, label: edgeLabel || "next" }); };
  const saveSchedule = async () => { if (!active) return; await act("schedule_workflow", { workflow_id: active.id, schedule, trigger_type: triggerType, enabled: true, webhook_path: triggerType === "webhook" ? `/hooks/${active.id}` : "", event: triggerType === "event" ? "agent.completed" : "" }); };
  const run = async () => { if (active) await act("run_workflow", { workflow_id: active.id }); };
  return <div className="agent-manager-modal" role="dialog" aria-modal="true" aria-label="Workflow Studio"><div className="workflow-studio">
    <header><div><Network /><span><h3>Workflow Studio</h3><p>Graphen, Trigger und Versionen in einer fokussierten Arbeitsfläche</p></span></div><button onClick={onClose} aria-label="Schließen"><X /></button></header>
    {!active ? <section className="workflow-studio-create"><GitBranch /><h3>Neuen Ablauf erstellen</h3><label>Name<input value={name} onChange={(event) => setName(event.target.value)} /></label><button className="agent-hub-primary" disabled={busy !== null || !name.trim()} onClick={() => void create()}><Plus />Workflow erstellen</button></section> : <><div className="workflow-studio-toolbar"><select value={active.id} onChange={(event) => { setActiveId(event.target.value); const next = platform.workflows.find((item) => item.id === event.target.value); setSchedule(next?.schedule || "manual"); setTriggerType(next?.trigger?.type || "manual"); }}><option value={active.id}>{active.name}</option>{platform.workflows.filter((item) => item.id !== active.id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><span>v{active.version || 1}</span><span>{active.status}</span><button disabled={busy !== null} onClick={() => void act("version_workflow", { workflow_id: active.id, reason: "manual-checkpoint" })}><History />Version</button><button className="agent-hub-primary" disabled={busy !== null || !active.nodes.length} onClick={() => void run()}>{busy === "run_workflow" ? <Loader2 className="agent-hub-spin" /> : <Play />}Ausführen</button></div>{error ? <div className="agent-hub-error"><AlertTriangle />{error}</div> : null}<div className="workflow-studio-body"><section className="workflow-studio-canvas"><div className="workflow-studio-grid" />{active.edges.map((edge, index) => <div key={`${edge.join("-")}-${index}`} className="workflow-studio-edge"><span>{edge[0]}</span><ChevronRight /><span>{edge[1]}</span><small>{edge[2] || "next"}</small></div>)}{active.nodes.map((node, index) => <article key={node.id} style={{ left: `${Math.min(78, node.x ?? 10)}%`, top: `${Math.min(78, node.y ?? 12)}%` }}><i>{index + 1}</i><span><strong>{node.label}</strong><small>{node.type}</small></span><StatusDot status="ready" /></article>)}{!active.nodes.length ? <Empty>Füge rechts den ersten Knoten hinzu</Empty> : null}</section><aside className="workflow-studio-inspector"><section><div className="agent-hub-section-title"><span>Knoten hinzufügen</span></div><label>Typ<select value={nodeType} onChange={(event) => setNodeType(event.target.value)}>{["agent","tool","condition","branch","loop","human","output"].map((type) => <option key={type}>{type}</option>)}</select></label><label>Bezeichnung<input value={nodeLabel} onChange={(event) => setNodeLabel(event.target.value)} placeholder="Ergebnis prüfen" /></label><button disabled={busy !== null || !nodeLabel.trim()} onClick={() => void addNode()}><Plus />Knoten hinzufügen</button></section><section><div className="agent-hub-section-title"><span>Verbinden</span></div><label>Von<select value={source} onChange={(event) => setSource(event.target.value)}><option value="">Knoten wählen</option>{active.nodes.map((node) => <option key={node.id} value={node.id}>{node.label}</option>)}</select></label><label>Nach<select value={target} onChange={(event) => setTarget(event.target.value)}><option value="">Knoten wählen</option>{active.nodes.map((node) => <option key={node.id} value={node.id}>{node.label}</option>)}</select></label><label>Route<input value={edgeLabel} onChange={(event) => setEdgeLabel(event.target.value)} /></label><button disabled={busy !== null || !source || !target || source === target} onClick={() => void connect()}><Network />Verbinden</button></section><section><div className="agent-hub-section-title"><span>Automation</span></div><label>Trigger<select value={triggerType} onChange={(event) => setTriggerType(event.target.value)}><option value="manual">Manuell</option><option value="schedule">Zeitplan</option><option value="webhook">Webhook</option><option value="event">Ereignis</option></select></label><label>Zeitplan<select value={schedule} onChange={(event) => setSchedule(event.target.value)}><option value="manual">Manuell</option><option value="hourly">Stündlich</option><option value="daily">Täglich</option><option value="*/15 * * * *">Alle 15 Minuten</option></select></label><button disabled={busy !== null} onClick={() => void saveSchedule()}><Clock3 />Automation speichern</button>{active.next_run ? <small>Nächster Lauf: {new Date(active.next_run).toLocaleString("de-AT")}</small> : null}</section></aside></div><footer><span>{active.nodes.length} Knoten</span><span>{active.edges.length} Verbindungen</span><span>{active.versions?.length || 0} Versionen</span><span>{active.canvas?.supports?.join(" · ")}</span></footer></>}
  </div></div>;
}

function FlowsView({ pipelines, platform, busy, onAction, onPlatform }: { pipelines: TaskPipeline[]; platform: PlatformPayload | null; busy: string | null; onAction: (p: TaskPipeline, action: string) => void; onPlatform: (platform: PlatformPayload) => void }) {
  const [flowBusy, setFlowBusy] = useState<string | null>(null);
  const [flowError, setFlowError] = useState<string | null>(null);
  const [editor, setEditor] = useState<{ open: boolean; workflow?: PlatformWorkflow }>({ open: false });
  const runWorkflow = async (workflowId: string) => { setFlowBusy(workflowId); setFlowError(null); try { const result = await micaApi.platformAction("run_workflow", { workflow_id: workflowId }); onPlatform(result.platform); } catch (reason) { setFlowError(reason instanceof Error ? reason.message : "Workflow konnte nicht gestartet werden."); } finally { setFlowBusy(null); } };
  return <div className="agent-hub-view"><div className="agent-manager-header"><ViewHeader icon={GitBranch} title="Abläufe" subtitle="Aktive Crews, Task-Pipelines und Workflow-Graphen" /><div><button onClick={() => setEditor({ open: true })}><Plus />Workflow</button>{platform?.workflows[0] ? <button className="agent-hub-primary" onClick={() => setEditor({ open: true, workflow: platform.workflows[0] })}><Network />Studio öffnen</button> : null}</div></div>{flowError ? <div className="agent-hub-error"><AlertTriangle />{flowError}</div> : null}<div className="agent-hub-flows-layout"><section><div className="agent-hub-section-title"><span>Task-Pipelines</span><b>{pipelines.length}</b></div>{pipelines.map((pipeline) => <PipelineRow key={pipeline.id} pipeline={pipeline} busy={busy === pipeline.id} onAction={onAction} />)}{!pipelines.length ? <Empty>Keine Pipelines vorhanden</Empty> : null}</section><section><div className="agent-hub-section-title"><span>Workflows & Crews</span><b>{platform?.workflows.length ?? 0}</b></div>{platform?.workflows.map((workflow) => <article className="agent-hub-workflow" key={workflow.id}><GitBranch /><div><strong>{workflow.name}</strong><span>{workflow.nodes.length} Knoten · Version {workflow.version}{workflow.schedule && workflow.schedule !== "manual" ? ` · ${workflow.schedule}` : ""}</span></div><span>{workflow.status}</span><button className="agent-hub-icon-button" title="Bearbeiten" onClick={() => setEditor({ open: true, workflow })}><Pencil /></button><button className="agent-hub-icon-button" disabled={flowBusy !== null} title="Workflow starten" onClick={() => void runWorkflow(workflow.id)}>{flowBusy === workflow.id ? <Loader2 className="agent-hub-spin" /> : <Play />}</button></article>)}{!platform?.workflows.length ? <Empty>Keine Workflows vorhanden</Empty> : null}</section></div>{editor.open && platform ? <WorkflowEditor workflow={editor.workflow} platform={platform} onPlatform={onPlatform} onClose={() => setEditor({ open: false })} /> : null}</div>;
}

function ApprovalsView({ approvals, busy, onDecide }: { approvals: ApprovalsPayload; busy: string | null; onDecide: (item: ApprovalPayload, approve: boolean) => void }) { return <div className="agent-hub-view"><ViewHeader icon={ShieldCheck} title="Freigaben" subtitle="Sicherheitsrelevante Aktionen mit verständlichen Konsequenzen" /><div className="agent-hub-approval-list">{approvals.pending.map((item) => <ApprovalCard key={`${item.tool_name}:${item.action}`} item={item} busy={busy === `${item.tool_name}:${item.action}`} onDecide={onDecide} />)}{!approvals.pending.length ? <div className="agent-hub-success-empty"><CheckCircle2 /><h3>Alles geprüft</h3><p>Es warten keine sicherheitsrelevanten Aktionen auf deine Entscheidung.</p></div> : null}</div></div>; }

function ActivityTable({ actions }: { actions: ActionRecordPayload[] }) { return <div className="agent-hub-activity-table"><div className="agent-hub-activity-head"><span>Zeit</span><span>Aktion</span><span>Status</span><span>Quelle</span></div>{actions.map((action) => <div key={action.id}><time>{new Date(action.timestamp).toLocaleTimeString("de-AT")}</time><span><strong>{action.tool_name || action.action_type}</strong><small>{action.action || action.result}</small></span><span className={`agent-hub-activity-status agent-hub-activity-${action.status}`}><StatusDot status={action.status} />{statusLabel(action.status)}</span><span>{action.action_type || "M.I.C.A"}</span></div>)}{!actions.length ? <Empty>Noch keine Aktivität</Empty> : null}</div>; }
function ActivityView({ actions }: { actions: ActionRecordPayload[] }) { const [filter, setFilter] = useState("all"); const visible = filter === "all" ? actions : actions.filter((item) => item.status.toLowerCase().includes(filter)); return <div className="agent-hub-view"><ViewHeader icon={Activity} title="Aktivität" subtitle="Ergebnisse, Kostenhinweise, Warnungen und Fehler in Echtzeit" /><div className="agent-hub-filterbar">{[["all","Alle"],["success","Erfolg"],["warning","Warnungen"],["error","Fehler"]].map(([id,label]) => <button key={id} className={filter === id ? "active" : ""} onClick={() => setFilter(id)}>{label}</button>)}</div><ActivityTable actions={visible} /></div>; }
