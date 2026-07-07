import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  FileClock,
  History,
  LayoutDashboard,
  ListTodo,
  MessageSquareText,
  PlayCircle,
  Send,
  ShieldAlert,
  Sunrise,
  Zap,
} from "lucide-react";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { Textarea } from "./ui/textarea";
import { micaApi } from "../lib/api";
import type { ChatMessage, CockpitItem, CommandCenterPayload, DashboardResponse } from "../lib/types";

function formatTime(value?: string | number | null) {
  if (!value) return "";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function toneFor(status?: string) {
  if (status === "ok" || status === "ready" || status === "online") {
    return "border-emerald-400/20 bg-emerald-400/10 text-emerald-100";
  }
  if (status === "blocked" || status === "error") {
    return "border-rose-400/25 bg-rose-400/10 text-rose-100";
  }
  return "border-amber-400/20 bg-amber-400/10 text-amber-100";
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3 text-sm text-slate-500">
      {label}
    </div>
  );
}

function CompactItem({ item }: { item: CockpitItem }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-white">{item.title}</div>
          {item.subtitle ? (
            <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-400">{item.subtitle}</div>
          ) : null}
        </div>
        {item.time || item.status ? (
          <span className="shrink-0 rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] text-slate-300">
            {item.time ?? item.status}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isTool = message.role === "tool";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[92%] rounded-2xl border px-4 py-3 ${
          isUser
            ? "border-cyan-400/20 bg-cyan-400/10 text-cyan-50"
            : isTool
              ? "border-amber-400/20 bg-amber-400/10 text-amber-50"
              : "border-white/10 bg-white/5 text-slate-100"
        }`}
      >
        <div className="mb-1 text-[11px] uppercase tracking-[0.22em] text-slate-500">
          {isUser ? "You" : isTool ? "Tool" : "M.I.C.A"} - {formatTime(message.timestamp)}
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        {!isUser && !isTool ? (
          <div className="mt-3 flex gap-2">
            {["positive", "negative"].map((rating) => (
              <button
                key={rating}
                onClick={() =>
                  micaApi.submitFeedback({
                    rating,
                    target: message.id,
                    comment: message.content.slice(0, 240),
                    category: "response",
                    context: { timestamp: message.timestamp },
                  })
                }
                className="rounded-lg border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] text-slate-300 hover:bg-white/10"
              >
                {rating === "positive" ? "Gut" : "Korrigieren"}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function CommandCenterView({
  dashboard,
  onSendCommand,
  onStartNewChat,
  onViewChange,
}: {
  dashboard: DashboardResponse | null;
  onSendCommand: (text: string) => Promise<void>;
  onStartNewChat: () => Promise<void>;
  onViewChange: (view: string) => void;
}) {
  const [payload, setPayload] = useState<CommandCenterPayload | null>(dashboard?.command_center ?? null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    setPayload(dashboard?.command_center ?? null);
  }, [dashboard?.command_center]);

  useEffect(() => {
    let alive = true;
    micaApi.getCommandCenter().then((next) => {
      if (alive) setPayload(next);
    });
    return () => {
      alive = false;
    };
  }, []);

  const messages = dashboard?.current_session?.messages?.slice(-8) ?? [];
  const resources = dashboard?.resources;
  const actionRecords = payload?.recent_actions ?? dashboard?.action_history?.records?.slice(0, 5) ?? [];
  const openQuestions = payload?.open_questions ?? dashboard?.resume?.open_ends ?? [];
  const activeTasks = payload?.active_tasks ?? dashboard?.cockpit?.tasks ?? [];
  const recentFiles = payload?.recent_files ?? dashboard?.resume?.recent_files ?? [];
  const warnings = payload?.warnings ?? [];
  const quickActions = payload?.quick_actions ?? dashboard?.quick_actions?.items ?? [];
  const dayOverview = payload?.day_overview;
  const briefing = dayOverview?.briefing;
  const taskPipelines = payload?.task_pipelines?.active ?? [];
  const automations = payload?.automations?.items ?? [];
  const activeProject = payload?.project_workspaces?.active;
  const pluginTools = payload?.plugins?.tools ?? [];
  const osActions = payload?.os_integrations?.actions ?? {};

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    try {
      await onSendCommand(text);
      setInput("");
    } finally {
      setSending(false);
    }
  };

  const advancePipeline = async (pipelineId: string) => {
    const result = await micaApi.taskPipelineAction({
      action: "advance",
      pipeline_id: pipelineId,
      note: "Advanced from Command Center.",
    });
    setPayload((current) =>
      current
        ? {
            ...current,
            task_pipelines: result.task_pipelines,
          }
        : current,
    );
  };

  return (
    <div className="grid h-full gap-4 overflow-hidden p-4 lg:grid-cols-[minmax(360px,1.1fr)_minmax(360px,1fr)] xl:grid-cols-[minmax(380px,1fr)_minmax(420px,1.1fr)_320px]">
      <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.045]">
        <div className="border-b border-white/10 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-cyan-100/75">
                <LayoutDashboard className="h-4 w-4" />
                Command Center
              </div>
              <h2 className="mt-1 text-xl font-semibold text-white">Arbeitszentrale</h2>
            </div>
            <Button
              onClick={onStartNewChat}
              size="icon"
              className="rounded-xl bg-cyan-400/90 text-slate-950 hover:bg-cyan-300"
              title="Neue Sitzung"
            >
              <PlayCircle className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="space-y-4 p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              {(payload?.status_cards ?? []).map((card) => (
                <div key={card.id} className={`rounded-xl border p-3 ${toneFor(card.status)}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs uppercase tracking-[0.22em] opacity-75">{card.label}</span>
                    {card.status === "ok" ? <CheckCircle2 className="h-4 w-4" /> : <CircleDashed className="h-4 w-4" />}
                  </div>
                  <div className="mt-2 text-lg font-semibold">{card.value}</div>
                  {card.detail ? <div className="mt-1 line-clamp-2 text-xs opacity-75">{card.detail}</div> : null}
                </div>
              ))}
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-white/[0.035] p-3">
                <div className="text-xs uppercase tracking-[0.22em] text-slate-500">CPU</div>
                <div className="mt-2 text-lg font-semibold text-cyan-100">{resources?.cpu_percent?.toFixed?.(1) ?? "0.0"}%</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.035] p-3">
                <div className="text-xs uppercase tracking-[0.22em] text-slate-500">RAM</div>
                <div className="mt-2 text-lg font-semibold text-emerald-100">{resources?.memory_percent?.toFixed?.(1) ?? "0.0"}%</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.035] p-3">
                <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Aktiv</div>
                <div className="mt-2 text-lg font-semibold text-amber-100">{resources?.performance?.active_tasks ?? activeTasks.length}</div>
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-white">
                <ListTodo className="h-4 w-4 text-cyan-200" />
                Aktive Tasks und Rückfragen
              </div>
              <div className="space-y-2">
                {[...activeTasks, ...openQuestions].slice(0, 5).map((item) => <CompactItem key={item.id} item={item} />)}
                {!activeTasks.length && !openQuestions.length ? <EmptyState label="Keine offenen Tasks oder Rückfragen" /> : null}
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-white">
                <PlayCircle className="h-4 w-4 text-emerald-200" />
                Task Pipelines
              </div>
              <div className="space-y-2">
                {taskPipelines.slice(0, 3).map((pipeline) => {
                  const completed = pipeline.steps.filter((step) => step.status === "completed").length;
                  return (
                    <div key={pipeline.id} className="rounded-xl border border-white/10 bg-white/[0.04] p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-white">{pipeline.goal}</div>
                          <div className="mt-1 text-xs text-slate-400">
                            {completed}/{pipeline.steps.length} Schritte · {pipeline.status}
                          </div>
                        </div>
                        <Button
                          size="icon"
                          onClick={() => advancePipeline(pipeline.id)}
                          className="h-9 w-9 rounded-xl bg-emerald-300 text-slate-950 hover:bg-emerald-200"
                          title="Nächsten Schritt abschließen"
                        >
                          <CheckCircle2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  );
                })}
                {!taskPipelines.length ? <EmptyState label="Keine aktiven Pipelines" /> : null}
              </div>
            </div>
          </div>
        </ScrollArea>
      </section>

      <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.045]">
        <div className="border-b border-white/10 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-slate-400">
                <MessageSquareText className="h-4 w-4" />
                Chat und Aktionen
              </div>
              <h3 className="mt-1 text-xl font-semibold text-white">
                {dashboard?.current_session?.title ?? "Keine aktive Sitzung"}
              </h3>
            </div>
            <Button
              onClick={() => onViewChange("chats")}
              variant="outline"
              className="rounded-xl border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
            >
              <History className="h-4 w-4" />
              Verlauf
            </Button>
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="space-y-3 p-4">
            {messages.length ? messages.map((message) => <MessageBubble key={message.id} message={message} />) : <EmptyState label="Noch kein laufendes Transcript" />}
          </div>
        </ScrollArea>

        <div className="border-t border-white/10 p-4">
          <div className="flex gap-3">
            <Textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Befehl an M.I.C.A ..."
              className="min-h-[60px] flex-1 rounded-xl border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500 focus-visible:ring-cyan-400/40"
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
            />
            <Button
              onClick={handleSend}
              disabled={sending}
              size="icon"
              className="h-[60px] w-[60px] rounded-xl bg-cyan-400/90 text-slate-950 hover:bg-cyan-300"
              title="Senden"
            >
              <Send className="h-5 w-5" />
            </Button>
          </div>

          {quickActions.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {quickActions.slice(0, 4).map((action) => (
                <button
                  key={action.id}
                  onClick={() => setInput(action.command)}
                  className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-200 transition hover:bg-white/10"
                >
                  {action.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </section>

      <section className="flex min-h-0 flex-col gap-4 overflow-hidden">
        <div className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
            <ShieldAlert className="h-4 w-4 text-amber-200" />
            Warnungen
          </div>
          <div className="space-y-2">
            {warnings.slice(0, 4).map((item) => <CompactItem key={item.id} item={item} />)}
            {!warnings.length ? <EmptyState label="Keine Systemwarnungen" /> : null}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
            <CircleDashed className="h-4 w-4 text-cyan-200" />
            Systeme
          </div>
          <div className="space-y-2">
            <CompactItem
              item={{
                id: "privacy-mode",
                title: `Privacy: ${payload?.privacy?.mode ?? "balanced"}`,
                subtitle: "Routing- und Tool-Grenzen",
                status: payload?.privacy?.rules?.external_models ? "cloud" : "local",
              }}
            />
            <CompactItem
              item={{
                id: "project-workspace",
                title: activeProject?.name ?? "Kein Projekt aktiv",
                subtitle: activeProject?.paths?.join(", ") || "Workspace-Kontext",
                status: activeProject ? "active" : "idle",
              }}
            />
            <CompactItem
              item={{
                id: "automations",
                title: `${automations.length} Automation(en)`,
                subtitle: automations.slice(0, 2).map((item) => item.name).join(", "),
                status: "local",
              }}
            />
            <CompactItem
              item={{
                id: "plugins-os",
                title: `${pluginTools.length} Plugin-Tool(s), ${Object.keys(osActions).length} OS-Aktionen`,
                subtitle: "Manifest-Plugins und sichere OS-Auditliste",
                status: "ready",
              }}
            />
          </div>
        </div>

        <div className="min-h-0 flex-1 rounded-2xl border border-white/10 bg-white/[0.045] p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
            <Zap className="h-4 w-4 text-cyan-200" />
            Letzte Aktionen
          </div>
          <ScrollArea className="h-[180px] pr-2 xl:h-[240px]">
            <div className="space-y-2">
              {actionRecords.slice(0, 6).map((record) => (
                <div key={record.id} className="rounded-xl border border-white/10 bg-white/[0.04] p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-white">{record.tool_name || record.action_type}</div>
                      <div className="mt-1 line-clamp-2 text-xs text-slate-400">{record.action || record.result}</div>
                    </div>
                    <span className={`rounded-full border px-2 py-1 text-[11px] ${toneFor(record.status)}`}>{record.status}</span>
                  </div>
                </div>
              ))}
              {!actionRecords.length ? <EmptyState label="Noch keine Aktionen" /> : null}
            </div>
          </ScrollArea>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
            <Sunrise className="h-4 w-4 text-amber-200" />
            Daily Briefing
          </div>
          {briefing ? (
            <div className="space-y-2">
              <div className={`rounded-xl border p-3 ${toneFor(briefing.status)}`}>
                <div className="text-xs uppercase tracking-[0.22em] opacity-75">
                  {briefing.kind} · {briefing.time_budget_minutes} min
                </div>
                <div className="mt-2 line-clamp-3 text-sm leading-5">{briefing.summary}</div>
              </div>
              {briefing.focus.slice(0, 2).map((item, index) => (
                <CompactItem
                  key={`${item.source}-${index}`}
                  item={{
                    id: `${item.source}-${index}`,
                    title: item.content,
                    subtitle: item.category,
                    status: item.priority,
                    source: item.source,
                  }}
                />
              ))}
            </div>
          ) : (
            <EmptyState label="Kein Briefing verfügbar" />
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
            <FileClock className="h-4 w-4 text-cyan-200" />
            Tagesüberblick
          </div>
          <div className="space-y-2">
            {dayOverview?.next_best_step ? (
              <CompactItem item={{ id: "next", title: dayOverview.next_best_step.title, subtitle: dayOverview.next_best_step.reason, status: dayOverview.next_best_step.action }} />
            ) : null}
            {[...(dayOverview?.calendar ?? []), ...(dayOverview?.reminders ?? []), ...(dayOverview?.tasks ?? [])].slice(0, 3).map((item) => <CompactItem key={item.id} item={item} />)}
            {recentFiles.slice(0, 2).map((item) => <CompactItem key={item.id} item={item} />)}
            {!dayOverview?.next_best_step && !(dayOverview?.calendar ?? []).length && !recentFiles.length ? (
              <EmptyState label="Keine Tagesdaten" />
            ) : null}
          </div>
        </div>

        {warnings.length ? (
          <div className="flex items-center gap-2 rounded-xl border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {warnings.length} Hinweis(e) brauchen Aufmerksamkeit.
          </div>
        ) : null}
      </section>
    </div>
  );
}
