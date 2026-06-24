import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Database,
  FileUp,
  Gauge,
  History,
  Laptop,
  ShieldCheck,
  Sparkles,
  Undo2,
} from "lucide-react";
import { ScrollArea } from "./ui/scroll-area";
import { Button } from "./ui/button";
import { jarvisApi } from "../lib/api";
import type { DashboardResponse } from "../lib/types";

export function ResourcesView({
  dashboard,
}: {
  dashboard: DashboardResponse | null;
}) {
  const resources = dashboard?.resources;
  const performance = resources?.performance ?? {};
  const recentLogs = dashboard?.state.logs ?? [];
  const devices = dashboard?.devices;
  const actionHistory = dashboard?.action_history;
  const approvals = dashboard?.approvals;
  const permissions = dashboard?.permissions;
  const documents = dashboard?.documents?.files ?? [];
  const sessions = dashboard?.recent_sessions ?? [];

  const setPermissionLevel = (level: string) => {
    jarvisApi.setPermissionLevel(level).catch((error) => {
      console.warn("Could not set permission level", error);
    });
  };

  const decideApproval = (approval: { tool_name: string; action: string }, approved: boolean) => {
    const request = { tool_name: approval.tool_name, action: approval.action };
    const call = approved ? jarvisApi.approveAction(request) : jarvisApi.denyAction(request);
    call.catch((error) => {
      console.warn("Could not update approval", error);
    });
  };

  const metrics = [
    {
      label: "CPU",
      value: `${resources?.cpu_percent?.toFixed?.(1) ?? "0.0"}%`,
      icon: Cpu,
      tone: "from-cyan-400/20 to-cyan-400/5",
    },
    {
      label: "Memory",
      value: `${resources?.memory_percent?.toFixed?.(1) ?? "0.0"}%`,
      icon: Database,
      tone: "from-emerald-400/20 to-emerald-400/5",
    },
    {
      label: "Disk",
      value: `${resources?.disk_percent?.toFixed?.(1) ?? "0.0"}%`,
      icon: Gauge,
      tone: "from-amber-400/20 to-amber-400/5",
    },
    {
      label: "Network",
      value: "↓ 0 KB/s ↑ 0 KB/s",
      icon: Activity,
      tone: "from-violet-400/20 to-violet-400/5",
    },
  ];

  return (
    <ScrollArea className="h-full">
      <div className="space-y-6 p-5 md:p-7">
        <section className="rounded-[2rem] border border-white/10 bg-white/5 p-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs uppercase tracking-[0.3em] text-cyan-100">
                <Activity className="h-4 w-4" />
                System health
              </div>
              <h2 className="text-3xl font-semibold tracking-tight text-white">
                Ressourcen und Performance
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                Hier siehst du die aktuelle Auslastung von System, Prozess und
                Live-Performance. Das hilft beim Feintuning, ohne die Sprach-UX
                aus dem Fokus zu nehmen.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
              <div className="text-xs uppercase tracking-[0.25em] text-slate-400">
                Active tasks
              </div>
              <div className="mt-1 text-lg font-semibold text-white">
                {performance.active_tasks ?? 0}
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => (
            <div
              key={metric.label}
              className={`rounded-[1.75rem] border border-white/10 bg-gradient-to-br ${metric.tone} p-5`}
            >
              <div className="mb-4 flex items-center justify-between">
                <metric.icon className="h-5 w-5 text-white/90" />
                <span className="text-xs uppercase tracking-[0.25em] text-slate-300">
                  Live
                </span>
              </div>
              <div className="text-xs uppercase tracking-[0.3em] text-slate-300">
                {metric.label}
              </div>
              <div className="mt-2 text-3xl font-semibold text-white">
                {metric.value}
              </div>
            </div>
          ))}
        </section>

        <section className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium text-white">
              <Sparkles className="h-4 w-4 text-cyan-200" />
              Performance summary
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs uppercase tracking-[0.25em] text-slate-400">
                  Current activity
                </div>
                <div className="mt-2 text-lg font-semibold text-white">
                  {performance.current_activity ?? "Idle"}
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs uppercase tracking-[0.25em] text-slate-400">
                  Waiting for input
                </div>
                <div className="mt-2 text-lg font-semibold text-white">
                  {performance.waiting_for_input ? "Yes" : "No"}
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs uppercase tracking-[0.25em] text-slate-400">
                  Model active
                </div>
                <div className="mt-2 text-lg font-semibold text-white">
                  {performance.model_active ? "Yes" : "No"}
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs uppercase tracking-[0.25em] text-slate-400">
                  Tool active
                </div>
                <div className="mt-2 text-lg font-semibold text-white">
                  {performance.tool_active ? "Yes" : "No"}
                </div>
              </div>
            </div>

            <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
              <div className="flex items-center gap-2 text-white">
                <Activity className="h-4 w-4 text-cyan-200" />
                History size
              </div>
              <p className="mt-2 text-slate-400">
                {performance.history_size ?? 0} activity entries are kept in the
                live performance tracker.
              </p>
            </div>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium text-white">
              <AlertTriangle className="h-4 w-4 text-amber-300" />
              Recent logs
            </div>
            <div className="space-y-3">
              {recentLogs.slice(-6).reverse().length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
                  No recent logs.
                </div>
              ) : (
                recentLogs
                  .slice(-6)
                  .reverse()
                  .map((log, index) => (
                    <div
                      key={`${log.timestamp}-${index}`}
                      className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300"
                    >
                      <div className="text-[11px] uppercase tracking-[0.25em] text-slate-500">
                        {new Date(log.timestamp * 1000).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        })}
                      </div>
                      <div className="mt-2 whitespace-pre-wrap leading-6">
                        {log.text}
                      </div>
                    </div>
                  ))
              )}
            </div>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-3">
          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium text-white">
              <Laptop className="h-4 w-4 text-cyan-200" />
              Geräte
            </div>
            <div className="space-y-3">
              {(devices?.items ?? []).length ? (
                devices?.items.map((device) => (
                  <div key={device.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate text-sm font-medium text-white">{device.name}</span>
                      <span className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-2 py-1 text-xs text-emerald-200">
                        {device.status}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-slate-400">
                      {devices?.current?.os ?? device.kind ?? "desktop"}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
                  Keine Geräte registriert.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium text-white">
              <History className="h-4 w-4 text-cyan-200" />
              Sitzungsverlauf
            </div>
            <div className="space-y-3">
              {sessions.slice(0, 4).map((session) => (
                <div key={session.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="truncate text-sm font-medium text-white">{session.title}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {session.message_count ?? 0} Nachrichten · {session.status ?? "active"}
                  </div>
                </div>
              ))}
              {!sessions.length ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
                  Keine Sitzungen.
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium text-white">
              <FileUp className="h-4 w-4 text-cyan-200" />
              Datei-Transfers
            </div>
            <div className="space-y-3">
              {documents.slice(0, 4).map((file) => (
                <div key={file.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="truncate text-sm font-medium text-white">{file.name}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {file.size_label} · {file.status ?? "uploaded"}
                  </div>
                </div>
              ))}
              {!documents.length ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
                  Keine Uploads.
                </div>
              ) : null}
            </div>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm font-medium text-white">
                <Undo2 className="h-4 w-4 text-cyan-200" />
                Tool-Verlauf
              </div>
              <span className="text-xs text-slate-400">
                {actionHistory?.stats?.total_actions ? String(actionHistory.stats.total_actions) : "0"} gesamt
              </span>
            </div>
            <div className="space-y-3">
              {(actionHistory?.records ?? []).slice(0, 6).map((record) => (
                <div key={record.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate text-sm font-medium text-white">
                      {record.tool_name}/{record.action}
                    </span>
                    <span className={record.status === "success" ? "text-emerald-300" : "text-amber-300"}>
                      {record.status}
                    </span>
                  </div>
                  <div className="mt-1 line-clamp-2 text-xs text-slate-400">{record.result}</div>
                  {record.can_undo ? (
                    <div className="mt-2 inline-flex items-center gap-1 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100">
                      <Undo2 className="h-3 w-3" />
                      Undo-Plan
                    </div>
                  ) : null}
                </div>
              ))}
              {!(actionHistory?.records ?? []).length ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
                  Noch keine Tool-Aktionen.
                </div>
              ) : null}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5">
              <div className="mb-4 flex items-center gap-2 text-sm font-medium text-white">
                <ShieldCheck className="h-4 w-4 text-cyan-200" />
                Berechtigungen
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {["safe", "normal", "admin"].map((level) => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setPermissionLevel(level)}
                    className={`rounded-2xl border px-4 py-3 text-center text-sm ${
                      approvals?.permission_level === level
                        ? "border-cyan-300/40 bg-cyan-300/10 text-cyan-100"
                        : "border-white/10 bg-white/5 text-slate-300"
                    }`}
                  >
                    {level}
                  </button>
                ))}
              </div>
              <div className="mt-4 space-y-2">
                {(permissions?.tools ?? []).filter((tool) => tool.risk_level === "high").slice(0, 5).map((tool) => (
                  <div key={tool.name} className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm">
                    <span className="truncate text-white">{tool.name}</span>
                    <span className={tool.enabled ? "text-emerald-300" : "text-slate-500"}>
                      {tool.enabled ? "aktiv" : "aus"}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5">
              <div className="mb-4 flex items-center gap-2 text-sm font-medium text-white">
                <CheckCircle2 className="h-4 w-4 text-cyan-200" />
                Status & Freigaben
              </div>
              {(approvals?.pending ?? []).length ? (
                <div className="space-y-3">
                  {approvals?.pending.slice(0, 4).map((approval) => (
                    <div key={`${approval.tool_name}-${approval.action}-${approval.timestamp}`} className="rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4">
                      <div className="text-sm font-medium text-amber-100">
                        {approval.tool_name}/{approval.action}
                      </div>
                      <div className="mt-1 line-clamp-3 text-xs text-amber-100/70">{approval.summary}</div>
                      <div className="mt-3 flex gap-2">
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => decideApproval(approval, true)}
                          className="h-8 bg-emerald-300 text-slate-950 hover:bg-emerald-200"
                        >
                          Freigeben
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => decideApproval(approval, false)}
                          className="h-8 border-white/10 bg-white/5 text-amber-50 hover:bg-white/10"
                        >
                          Ablehnen
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
                  Keine offenen Freigaben.
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </ScrollArea>
  );
}

