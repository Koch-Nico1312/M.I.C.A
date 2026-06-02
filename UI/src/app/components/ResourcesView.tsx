import {
  Activity,
  AlertTriangle,
  Cpu,
  Database,
  Gauge,
  Sparkles,
} from "lucide-react";
import { ScrollArea } from "./ui/scroll-area";
import type { DashboardResponse } from "../lib/types";

export function ResourcesView({
  dashboard,
}: {
  dashboard: DashboardResponse | null;
}) {
  const resources = dashboard?.resources;
  const performance = resources?.performance ?? {};
  const recentLogs = dashboard?.state.logs ?? [];

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
      </div>
    </ScrollArea>
  );
}

