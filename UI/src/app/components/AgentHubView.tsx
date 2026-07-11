import { memo, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, BookOpen, Bot, BrainCircuit, Check, CheckCircle2, ChevronRight,
  CircleDashed, Clock3, Copy, Database, Download, FileJson, GitBranch, History,
  KanbanSquare, ListChecks, Loader2, Pause, Pencil, Play, RefreshCw, Save, Search,
  ShieldCheck, ShieldX, SlidersHorizontal, Sparkles, Square, Trash2, Upload, Users, Wrench, X,
} from "lucide-react";
import { micaApi } from "../lib/api";
import type {
  ActionRecordPayload, ApprovalPayload, ApprovalsPayload, CommandCenterPayload,
  PlatformAgent, PlatformAgentRun, PlatformPayload, TaskPipeline, TaskPipelinesPayload,
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
    const unsubscribe = micaApi.subscribeToLiveEvents(() => void load());
    const timer = window.setInterval(() => void load(), 30_000);
    return () => { unsubscribe(); window.clearInterval(timer); };
  }, [load]);

  const activePipeline = pipelines.active[0] ?? pipelines.pipelines.find((item) => !["completed", "cancelled"].includes(item.status));
  const agents = useMemo<HubAgent[]>(() => ROLE_PRESETS.map((preset, index) => {
    const real = platform?.agents[index % Math.max(platform.agents.length, 1)];
    const pipeline = pipelines.active[index % Math.max(pipelines.active.length, 1)] ?? activePipeline;
    const isWorking = Boolean(pipeline && index < Math.min(4, pipeline.steps.length + 1));
    return {
      ...preset,
      model: real?.model || (index === 5 ? "lokal" : "Standardmodell"),
      status: isWorking ? (pipeline?.status || "running") : "ready",
      task: isWorking ? pipeline?.goal || "Systemstatus auswerten" : "Bereit für einen Auftrag",
      progress: isWorking ? progressFor(pipeline) : 0,
      source: real,
    };
  }), [activePipeline, pipelines.active, platform?.agents]);
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0];
  const actions = commandCenter?.recent_actions ?? [];
  const runningCount = pipelines.active.length + (platform?.runs.filter((run) => run.status === "running").length ?? 0);

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
        <div className="agent-hub-nav-title"><BrainCircuit />Agent-Hub</div>
        <nav>{NAV.map(({ id, label, icon: Icon }) => (
          <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}><Icon />{label}{id === "approvals" && approvals.pending.length ? <b>{approvals.pending.length}</b> : null}</button>
        ))}</nav>
        <div className="agent-hub-nav-footer"><span><StatusDot status={error ? "blocked" : "active"} />{error ? "Eingeschränkt" : "Verbunden"}</span><small>{lastUpdated ? `Stand ${lastUpdated.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" })}` : "Lädt…"}</small></div>
      </aside>

      <main className="agent-hub-main">
        <header className="agent-hub-toolbar">
          <div className="agent-hub-goal"><Search /><input value={goal} onChange={(event) => setGoal(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void startRun(); }} placeholder="Ziel oder Auftrag eingeben…" /></div>
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
                <section><div className="agent-hub-section-title"><span>Systemübersicht</span></div><div className="agent-hub-stat-grid"><div><b>{platform?.agents.length ?? 0}</b><span>Agenten</span></div><div><b>{platform?.workflows.length ?? 0}</b><span>Workflows</span></div><div><b>{actions.length}</b><span>Aktionen</span></div><div><b>{approvals.permission_level}</b><span>Freigabestufe</span></div></div></section>
              </aside>
              <div className="agent-hub-live"><div className="agent-hub-section-title"><span>Live-Aktivität</span><button onClick={() => setTab("activity")}>Alle anzeigen</button></div><ActivityTable actions={actions.slice(0, 5)} /></div>
            </div>
          ) : null}
          {tab === "tasks" ? <TasksView pipelines={pipelines.pipelines} /> : null}
          {tab === "agents" ? <AgentsView platform={platform} selected={selectedAgentId} onSelect={setSelectedAgentId} onPlatform={setPlatform} /> : null}
          {tab === "flows" ? <FlowsView pipelines={pipelines.pipelines} platform={platform} busy={busy} onAction={pipelineAction} /> : null}
          {tab === "approvals" ? <ApprovalsView approvals={approvals} busy={busy} onDecide={decideApproval} /> : null}
          {tab === "activity" ? <ActivityView actions={actions} /> : null}
        </section>
      </main>
    </div>
  );
});

function ViewHeader({ icon: Icon, title, subtitle }: { icon: typeof Activity; title: string; subtitle: string }) { return <header className="agent-hub-view-header"><div><Icon /><span><h2>{title}</h2><p>{subtitle}</p></span></div></header>; }

function TasksView({ pipelines }: { pipelines: TaskPipeline[] }) {
  const columns = [
    { id: "backlog", title: "Backlog", items: pipelines.filter((p) => p.status === "ready") },
    { id: "active", title: "Aktiv", items: pipelines.filter((p) => p.status === "running" || p.status === "paused") },
    { id: "review", title: "Review", items: pipelines.filter((p) => p.status === "blocked" || p.requires_approval) },
    { id: "done", title: "Erledigt", items: pipelines.filter((p) => p.status === "completed") },
  ];
  return <div className="agent-hub-view"><ViewHeader icon={KanbanSquare} title="Aufgaben" subtitle="Alle Aufträge und ihr aktueller Arbeitsstand" /><div className="agent-hub-kanban">{columns.map((column) => <section key={column.id}><div className="agent-hub-section-title"><span>{column.title}</span><b>{column.items.length}</b></div>{column.items.map((pipeline) => <article key={pipeline.id} className="agent-hub-task-card"><strong>{pipeline.goal}</strong><p>{pipeline.steps.filter((step) => step.status === "completed").length}/{pipeline.steps.length} Schritte erledigt</p><div className="agent-hub-progress"><span style={{ width: `${progressFor(pipeline)}%` }} /></div>{pipeline.requires_approval ? <small><ShieldCheck />Freigabe erforderlich</small> : null}</article>)}{!column.items.length ? <Empty>Keine Aufgaben</Empty> : null}</section>)}</div></div>;
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

function AgentsView({ platform, selected, onSelect, onPlatform }: { platform: PlatformPayload | null; selected: string; onSelect: (id: string) => void; onPlatform: (platform: PlatformPayload) => void }) {
  const [draft, setDraft] = useState<AgentDraft | null>(null);
  const [assignment, setAssignment] = useState("");
  const [runModel, setRunModel] = useState("");
  const [importText, setImportText] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!platform) return <div className="agent-hub-view"><Empty>Agentendaten werden geladen</Empty></div>;
  const realAgents = platform.agents;
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
    <div className="agent-manager-header"><ViewHeader icon={Users} title="Agenten" subtitle="Agenten erstellen, konfigurieren, ausführen und überwachen" /><div><button onClick={() => setShowImport(true)}><Upload />Importieren</button><button className="agent-hub-primary" onClick={() => setDraft(emptyAgentDraft())}><Bot />Agent erstellen</button></div></div>
    {error ? <div className="agent-hub-error"><AlertTriangle />{error}<button onClick={() => setError(null)}><X /></button></div> : null}
    <div className="agent-manager-layout">
      <aside className="agent-manager-list"><div className="agent-hub-section-title"><span>Registrierte Agenten</span><b>{realAgents.length}</b></div>{realAgents.map((item, index) => { const run = (platform.agent_runs ?? []).find((candidate) => candidate.agent_id === item.id && ["running", "paused"].includes(candidate.status)); const cardAgent = hubAgentFromPlatform(item, index, run); return <button key={item.id} className={item.id === agent?.id ? "active" : ""} onClick={() => onSelect(item.id)}><AgentAvatar agent={cardAgent} /><span><strong>{item.name}</strong><small>{item.model} · {item.visibility}</small></span><span className="agent-hub-agent-state"><StatusDot status={run?.status || "ready"} />{statusLabel(run?.status || "ready")}</span></button>; })}{!realAgents.length ? <Empty>Noch keine Agenten erstellt</Empty> : null}</aside>
      {agent && avatarAgent ? <main className="agent-manager-detail">
        <header className="agent-manager-profile-head"><AgentAvatar agent={avatarAgent} large /><div><h2>{agent.name}</h2><p>{agent.prompt}</p><span><StatusDot status={activeRun?.status || "ready"} />{statusLabel(activeRun?.status || "ready")} · {agent.model}</span></div><div className="agent-manager-actions"><button onClick={() => setDraft(draftFromAgent(agent))}><Pencil />Bearbeiten</button><button onClick={() => void duplicate()} disabled={busy !== null}><Copy />Duplizieren</button><button onClick={() => void exportAgent()} disabled={busy !== null}><Download />Exportieren</button><button className="danger" onClick={() => setShowDelete(true)}><Trash2 />Löschen</button></div></header>
        <section className="agent-manager-assignment"><div><Play /><span><strong>Auftrag zuweisen</strong><small>Startet einen steuerbaren Lauf mit diesem Agenten</small></span></div><textarea value={assignment} onChange={(e) => setAssignment(e.target.value)} placeholder="Beschreibe Ziel, Kontext und erwartetes Ergebnis…" rows={3} /><div><label>Modell <select value={runModel || agent.model} onChange={(e) => setRunModel(e.target.value)}><option value={agent.model}>{agent.model}</option><option value="fast">fast</option><option value="quality">quality</option><option value="local">local</option></select></label><button className="agent-hub-primary" disabled={!assignment.trim() || busy !== null} onClick={async () => { const result = await action("start_agent_run", { agent_id: agent.id, assignment, model: runModel || agent.model }); if (result) { setAssignment(""); setSelectedRunId((result as PlatformAgentRun).id); } }}><Play />Agent starten</button></div></section>
        <div className="agent-manager-info-grid"><section><Wrench /><span><small>Tools</small><strong>{agent.tools.join(", ") || "Keine"}</strong></span></section><section><BookOpen /><span><small>Wissensquellen</small><strong>{agent.knowledge.join(", ") || "Keine"}</strong></span></section><section><ShieldCheck /><span><small>Berechtigungen</small><strong>{agent.permissions?.join(", ") || "Standard"}</strong></span></section><section><SlidersHorizontal /><span><small>Parameter</small><strong>{Object.entries(agent.parameters).map(([key, value]) => `${key}: ${value}`).join(" · ") || "Standard"}</strong></span></section></div>
        <section className="agent-manager-runs"><div className="agent-hub-section-title"><span><History />Läufe und Logs</span><b>{runs.length + invocations.length}</b></div><div className="agent-manager-run-layout"><div className="agent-manager-run-list">{runs.map((run) => <button key={run.id} className={selectedRun?.id === run.id ? "active" : ""} onClick={() => setSelectedRunId(run.id)}><span><strong>{run.assignment}</strong><small>{new Date(run.started_at).toLocaleString("de-AT")}</small></span><span><StatusDot status={run.status} />{statusLabel(run.status)}</span></button>)}{invocations.map((run) => <button key={run.id}><span><strong>{run.input || "Direkter Aufruf"}</strong><small>{new Date(run.created_at).toLocaleString("de-AT")}</small></span><span><StatusDot status={run.status} />{statusLabel(run.status)}</span></button>)}{!runs.length && !invocations.length ? <Empty>Noch keine Läufe vorhanden</Empty> : null}</div><div className="agent-manager-log">{selectedRun ? <><header><div><strong>{selectedRun.assignment}</strong><small>{selectedRun.id} · {selectedRun.model}</small></div><div>{selectedRun.status === "running" ? <button onClick={() => void action("pause_agent_run", { run_id: selectedRun.id })}><Pause />Pausieren</button> : null}{selectedRun.status === "paused" ? <button onClick={() => void action("resume_agent_run", { run_id: selectedRun.id })}><Play />Fortsetzen</button> : null}{["running", "paused"].includes(selectedRun.status) ? <button className="danger" onClick={() => void action("stop_agent_run", { run_id: selectedRun.id })}><Square />Stoppen</button> : null}</div></header><div className="agent-manager-log-lines">{selectedRun.logs.map((line, index) => <div key={`${line.timestamp}-${index}`}><time>{new Date(line.timestamp).toLocaleTimeString("de-AT")}</time><span className={`level-${line.level}`}>{line.level}</span><p>{line.message}</p></div>)}</div>{selectedRun.result ? <pre>{selectedRun.result}</pre> : null}</> : <Empty>Wähle einen Lauf für Details</Empty>}</div></div></section>
      </main> : <div className="agent-manager-no-selection"><Bot /><h3>Erstelle deinen ersten Agenten</h3><p>Konfiguriere Modell, Prompt, Tools, Wissen und Berechtigungen.</p><button className="agent-hub-primary" onClick={() => setDraft(emptyAgentDraft())}>Agent erstellen</button></div>}
    </div>
    {draft ? <AgentEditor draft={draft} platform={platform} busy={busy === "save_agent"} onChange={setDraft} onClose={() => setDraft(null)} onSave={() => void save()} /> : null}
    {showImport ? <div className="agent-manager-modal" role="dialog" aria-modal="true" aria-label="Agent importieren"><div className="agent-manager-import"><header><div><FileJson /><span><h3>Agent importieren</h3><p>M.I.C.A-Agent-Paket als JSON einfügen</p></span></div><button onClick={() => setShowImport(false)}><X /></button></header><textarea value={importText} onChange={(e) => setImportText(e.target.value)} rows={18} placeholder='{ "format": "mica-agent-package/v1", "manifest": { ... } }' /><footer><button onClick={() => setShowImport(false)}>Abbrechen</button><button className="agent-hub-primary" disabled={!importText.trim() || busy !== null} onClick={() => void importAgent()}><Upload />Importieren</button></footer></div></div> : null}
    {showDelete && agent ? <div className="agent-manager-modal" role="alertdialog" aria-modal="true" aria-label="Agent löschen"><div className="agent-manager-confirm"><ShieldX /><h3>{agent.name} löschen?</h3><p>Der Agent und seine Veröffentlichungen werden entfernt. Abgeschlossene Laufprotokolle bleiben für die Nachvollziehbarkeit erhalten. Aktive Läufe müssen zuerst gestoppt werden.</p><div><button onClick={() => setShowDelete(false)}>Abbrechen</button><button className="danger" disabled={busy !== null} onClick={async () => { const result = await action("delete_agent", { agent_id: agent.id }); if (result) { setShowDelete(false); const remaining = platform.agents.filter((item) => item.id !== agent.id); onSelect(remaining[0]?.id || ""); } }}><Trash2 />Endgültig löschen</button></div></div></div> : null}
  </div>;
}

function FlowsView({ pipelines, platform, busy, onAction }: { pipelines: TaskPipeline[]; platform: PlatformPayload | null; busy: string | null; onAction: (p: TaskPipeline, action: string) => void }) {
  return <div className="agent-hub-view"><ViewHeader icon={GitBranch} title="Abläufe" subtitle="Aktive Crews, Task-Pipelines und Workflow-Graphen" /><div className="agent-hub-flows-layout"><section><div className="agent-hub-section-title"><span>Task-Pipelines</span><b>{pipelines.length}</b></div>{pipelines.map((pipeline) => <PipelineRow key={pipeline.id} pipeline={pipeline} busy={busy === pipeline.id} onAction={onAction} />)}{!pipelines.length ? <Empty>Keine Pipelines vorhanden</Empty> : null}</section><section><div className="agent-hub-section-title"><span>Workflows & Crews</span><b>{platform?.workflows.length ?? 0}</b></div>{platform?.workflows.map((workflow) => <article className="agent-hub-workflow" key={workflow.id}><GitBranch /><div><strong>{workflow.name}</strong><span>{workflow.nodes.length} Knoten · Version {workflow.version}</span></div><span>{workflow.status}</span></article>)}{!platform?.workflows.length ? <Empty>Keine Workflows vorhanden</Empty> : null}</section></div></div>;
}

function ApprovalsView({ approvals, busy, onDecide }: { approvals: ApprovalsPayload; busy: string | null; onDecide: (item: ApprovalPayload, approve: boolean) => void }) { return <div className="agent-hub-view"><ViewHeader icon={ShieldCheck} title="Freigaben" subtitle="Sicherheitsrelevante Aktionen mit verständlichen Konsequenzen" /><div className="agent-hub-approval-list">{approvals.pending.map((item) => <ApprovalCard key={`${item.tool_name}:${item.action}`} item={item} busy={busy === `${item.tool_name}:${item.action}`} onDecide={onDecide} />)}{!approvals.pending.length ? <div className="agent-hub-success-empty"><CheckCircle2 /><h3>Alles geprüft</h3><p>Es warten keine sicherheitsrelevanten Aktionen auf deine Entscheidung.</p></div> : null}</div></div>; }

function ActivityTable({ actions }: { actions: ActionRecordPayload[] }) { return <div className="agent-hub-activity-table"><div className="agent-hub-activity-head"><span>Zeit</span><span>Aktion</span><span>Status</span><span>Quelle</span></div>{actions.map((action) => <div key={action.id}><time>{new Date(action.timestamp).toLocaleTimeString("de-AT")}</time><span><strong>{action.tool_name || action.action_type}</strong><small>{action.action || action.result}</small></span><span className={`agent-hub-activity-status agent-hub-activity-${action.status}`}><StatusDot status={action.status} />{statusLabel(action.status)}</span><span>{action.action_type || "M.I.C.A"}</span></div>)}{!actions.length ? <Empty>Noch keine Aktivität</Empty> : null}</div>; }
function ActivityView({ actions }: { actions: ActionRecordPayload[] }) { const [filter, setFilter] = useState("all"); const visible = filter === "all" ? actions : actions.filter((item) => item.status.toLowerCase().includes(filter)); return <div className="agent-hub-view"><ViewHeader icon={Activity} title="Aktivität" subtitle="Ergebnisse, Kostenhinweise, Warnungen und Fehler in Echtzeit" /><div className="agent-hub-filterbar">{[["all","Alle"],["success","Erfolg"],["warning","Warnungen"],["error","Fehler"]].map(([id,label]) => <button key={id} className={filter === id ? "active" : ""} onClick={() => setFilter(id)}>{label}</button>)}</div><ActivityTable actions={visible} /></div>; }
