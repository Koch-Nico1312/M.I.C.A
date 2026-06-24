import {
  ArrowRight,
  Bell,
  CalendarDays,
  CheckCircle2,
  CloudSun,
  FileClock,
  Inbox,
  ListTodo,
  PlayCircle,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import type { ElementType } from "react";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import type { CockpitItem, DashboardResponse } from "../lib/types";

function EmptyLine({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3 text-sm text-slate-500">
      {label}
    </div>
  );
}

function ItemRow({ item }: { item: CockpitItem }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-white">{item.title}</div>
        {item.subtitle ? (
          <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-400">{item.subtitle}</div>
        ) : null}
      </div>
      {item.time || item.status ? (
        <div className="shrink-0 rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] text-slate-300">
          {item.time ?? item.status}
        </div>
      ) : null}
    </div>
  );
}

function CockpitPanel({
  title,
  icon: Icon,
  items,
  emptyLabel,
}: {
  title: string;
  icon: ElementType;
  items: CockpitItem[];
  emptyLabel: string;
}) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
        <Icon className="h-4 w-4 text-cyan-200" />
        {title}
      </div>
      <div className="space-y-2">
        {items.length ? items.slice(0, 4).map((item) => <ItemRow key={item.id} item={item} />) : <EmptyLine label={emptyLabel} />}
      </div>
    </section>
  );
}

export function HomeView({
  dashboard,
  onStartNewChat,
}: {
  dashboard: DashboardResponse | null;
  onStartNewChat: () => void;
}) {
  const cockpit = dashboard?.cockpit;
  const resume = dashboard?.resume;
  const currentSession = dashboard?.current_session ?? resume?.session ?? null;
  const nextStep = cockpit?.next_best_step;
  const weather = cockpit?.weather;

  const activityItems =
    cockpit?.recent_activities?.length
      ? cockpit.recent_activities
      : dashboard?.recent_sessions?.slice(0, 4).map((session) => ({
          id: session.id,
          title: session.title,
          subtitle: session.preview,
          status: session.status,
        })) ?? [];

  return (
    <ScrollArea className="h-full">
      <div className="space-y-5 p-5 md:p-7">
        <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-white/10 bg-[linear-gradient(135deg,rgba(0,212,255,0.11),rgba(124,230,200,0.05),rgba(255,255,255,0.035))] p-5">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-cyan-100/80">
                  <Sparkles className="h-4 w-4" />
                  Daily Cockpit
                </div>
                <h2 className="text-2xl font-semibold tracking-tight text-white md:text-3xl">
                  {nextStep?.title ?? "Heute ist offen."}
                </h2>
                {nextStep?.reason ? (
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">{nextStep.reason}</p>
                ) : null}
              </div>

              <div className="grid min-w-[220px] gap-2 sm:grid-cols-2 lg:grid-cols-1">
                <div className="rounded-2xl border border-white/10 bg-white/[0.05] p-4">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-slate-400">
                    <CloudSun className="h-4 w-4 text-amber-200" />
                    Wetter
                  </div>
                  <div className="mt-2 text-lg font-semibold text-white">{weather?.summary ?? "Keine Wetterdaten"}</div>
                  <div className="mt-1 text-xs text-slate-400">{weather?.location ?? weather?.condition ?? ""}</div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.05] p-4">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-slate-400">
                    <Inbox className="h-4 w-4 text-cyan-200" />
                    Offen
                  </div>
                  <div className="mt-2 text-lg font-semibold text-white">
                    {cockpit?.mail?.open_count ?? 0} Mails
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    {(cockpit?.tasks?.length ?? 0) + (cockpit?.reminders?.length ?? 0)} Aufgaben
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-3">
              <Button
                onClick={onStartNewChat}
                className="rounded-xl bg-cyan-400/90 text-slate-950 hover:bg-cyan-300"
              >
                <PlayCircle className="h-4 w-4" />
                Neuer Fokus
              </Button>
              {nextStep?.action ? (
                <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/10 px-4 py-2 text-sm text-cyan-50">
                  {nextStep.action}
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.045] p-5">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium text-white">
              <RotateCcw className="h-4 w-4 text-cyan-200" />
              Mach weiter, wo wir aufgehoert haben
            </div>
            <div className="space-y-3">
              <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
                <div className="text-sm font-medium text-white">
                  {currentSession?.title ?? resume?.last_activity?.title ?? "Keine offene Sitzung"}
                </div>
                <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-400">
                  {resume?.summary || currentSession?.summary || currentSession?.preview || "Bereit fuer den naechsten Schritt."}
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {(resume?.open_ends ?? []).slice(0, 2).map((item) => (
                  <ItemRow key={item.id} item={item} />
                ))}
                {!(resume?.open_ends ?? []).length ? <EmptyLine label="Keine offenen Enden" /> : null}
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-3">
          <CockpitPanel
            title="Kalender"
            icon={CalendarDays}
            items={cockpit?.calendar?.items ?? []}
            emptyLabel="Keine Termine"
          />
          <CockpitPanel
            title="Mails"
            icon={Inbox}
            items={cockpit?.mail?.items ?? []}
            emptyLabel="Keine offenen Mails"
          />
          <CockpitPanel
            title="Erinnerungen"
            icon={Bell}
            items={cockpit?.reminders ?? []}
            emptyLabel="Keine Erinnerungen"
          />
        </section>

        <section className="grid gap-4 xl:grid-cols-[1fr_1fr_1fr]">
          <CockpitPanel
            title="Aufgaben"
            icon={ListTodo}
            items={cockpit?.tasks ?? []}
            emptyLabel="Keine Aufgaben"
          />
          <CockpitPanel
            title="Letzte Aktivitaeten"
            icon={CheckCircle2}
            items={activityItems}
            emptyLabel="Noch keine Aktivitaet"
          />
          <section className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
              <FileClock className="h-4 w-4 text-cyan-200" />
              Zuletzt genutzte Dateien
            </div>
            <div className="space-y-2">
              {(resume?.recent_files ?? []).length ? (
                resume?.recent_files.slice(0, 4).map((item) => <ItemRow key={item.id} item={item} />)
              ) : (
                <EmptyLine label="Keine Dateien" />
              )}
            </div>
          </section>
        </section>

        {currentSession?.id ? (
          <Button
            onClick={onStartNewChat}
            variant="ghost"
            className="rounded-xl border border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/10 hover:text-white"
          >
            Sitzung wechseln
            <ArrowRight className="h-4 w-4" />
          </Button>
        ) : null}
      </div>
    </ScrollArea>
  );
}
