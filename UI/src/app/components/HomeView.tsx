import {
  ArrowRight,
  Bell,
  CalendarDays,
  CheckCircle2,
  CloudSun,
  Database,
  FileClock,
  FileText,
  Globe2,
  Inbox,
  ListTodo,
  Loader2,
  Mic2,
  Network,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Server,
  Sparkles,
  Star,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { ElementType } from "react";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { micaApi } from "../lib/api";
import type {
  CockpitItem,
  DashboardResponse,
  ProjectStatePayload,
  ProjectSummaryPayload,
  SystemStatusPayload,
} from "../lib/types";

const serviceIcons: Record<string, ElementType> = {
  gemini: Sparkles,
  ollama: Server,
  microphone: Mic2,
  browser: Globe2,
  mcp: Network,
  database: Database,
};

const favoriteLabels: Record<string, string> = {
  "open-hub": "Agent Hub öffnen",
  "open-tasks": "Aufgaben öffnen",
  "open-agents": "Agenten öffnen",
  "open-flows": "Workflows öffnen",
  "open-approvals": "Freigaben öffnen",
  "open-activity": "Aktivität öffnen",
  "new-agent": "Neuen Agenten erstellen",
  "new-run": "Neuen Auftrag eingeben",
  refresh: "Hub aktualisieren",
  "save-view": "Aktuelle Ansicht speichern",
};

function favoriteLabel(id: string) {
  return favoriteLabels[id] || id.replace(/^(agent|pipeline|workflow|artifact|inbox)-/, "").replaceAll("-", " ");
}

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
  onOpenAgentHub,
}: {
  dashboard: DashboardResponse | null;
  onStartNewChat: () => void;
  onOpenAgentHub: (commandId?: string) => void;
}) {
  const [systemStatus, setSystemStatus] = useState<SystemStatusPayload | null>(null);
  const [projectState, setProjectState] = useState<ProjectStatePayload | null>(null);
  const [projectSummary, setProjectSummary] = useState<ProjectSummaryPayload | null>(null);
  const [checking, setChecking] = useState(false);
  const [summaryBusy, setSummaryBusy] = useState(false);
  const [panelError, setPanelError] = useState<string | null>(null);
  const cockpit = dashboard?.cockpit;
  const resume = dashboard?.resume;
  const currentSession = dashboard?.current_session ?? resume?.session ?? null;
  const nextStep = cockpit?.next_best_step;
  const weather = cockpit?.weather;

  useEffect(() => {
    let active = true;
    void Promise.all([micaApi.getSystemStatus(), micaApi.getProjectState()])
      .then(([status, state]) => {
        if (!active) return;
        setSystemStatus(status);
        setProjectState(state);
        setPanelError(null);
      })
      .catch((reason) => {
        if (active) setPanelError(reason instanceof Error ? reason.message : "Statusdaten konnten nicht geladen werden.");
      });
    return () => {
      active = false;
    };
  }, []);

  const refreshSystemStatus = async () => {
    setChecking(true);
    try {
      setSystemStatus(await micaApi.refreshSystemStatus());
      setPanelError(null);
    } catch (reason) {
      setPanelError(reason instanceof Error ? reason.message : "Systemstatus konnte nicht geprüft werden.");
    } finally {
      setChecking(false);
    }
  };

  const generateProjectSummary = async () => {
    setSummaryBusy(true);
    try {
      setProjectSummary(await micaApi.getProjectSummary());
      setPanelError(null);
    } catch (reason) {
      setPanelError(reason instanceof Error ? reason.message : "Projektzusammenfassung konnte nicht erstellt werden.");
    } finally {
      setSummaryBusy(false);
    }
  };

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
              Mach weiter, wo wir aufgehört haben
            </div>
            <div className="space-y-3">
              <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
                <div className="text-sm font-medium text-white">
                  {currentSession?.title ?? resume?.last_activity?.title ?? "Keine offene Sitzung"}
                </div>
                <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-400">
                  {resume?.summary || currentSession?.summary || currentSession?.preview || "Bereit für den nächsten Schritt."}
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

        <section className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
          <section className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-white">
                  <Server className="h-4 w-4 text-cyan-200" />
                  Systemstatus
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  {systemStatus
                    ? `${systemStatus.counts.available} bereit · ${systemStatus.counts.degraded} eingeschränkt · ${systemStatus.counts.unavailable} nicht verfügbar`
                    : "Dienste werden geprüft…"}
                </div>
              </div>
              <Button
                variant="ghost"
                disabled={checking}
                onClick={() => void refreshSystemStatus()}
                className="rounded-xl border border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/10 hover:text-white"
              >
                {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Erneut prüfen
              </Button>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {(systemStatus?.services ?? []).map((service) => {
                const Icon = serviceIcons[service.id] ?? Server;
                const tone = service.status === "available" ? "bg-emerald-400" : service.status === "degraded" ? "bg-amber-300" : "bg-rose-400";
                return (
                  <div key={service.id} className="rounded-xl border border-white/10 bg-white/[0.04] p-3" title={service.detail}>
                    <div className="flex items-center justify-between gap-2">
                      <Icon className="h-4 w-4 text-cyan-100" />
                      <span className={`h-2.5 w-2.5 rounded-full ${tone}`} />
                    </div>
                    <div className="mt-2 text-sm font-medium text-white">{service.label}</div>
                    <div className="mt-1 truncate text-xs text-slate-400">{service.summary}</div>
                  </div>
                );
              })}
              {!systemStatus ? <EmptyLine label="Prüfung läuft…" /> : null}
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
              <Star className="h-4 w-4 text-amber-200" />
              Favorisierte Befehle
            </div>
            <div className="grid gap-2">
              {(projectState?.favorite_commands ?? []).slice(0, 6).map((commandId) => (
                <button
                  key={commandId}
                  onClick={() => onOpenAgentHub(commandId)}
                  className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-left text-sm text-slate-200 transition hover:border-cyan-300/30 hover:bg-cyan-300/10 hover:text-white"
                >
                  <span className="truncate capitalize">{favoriteLabel(commandId)}</span>
                  <ArrowRight className="h-4 w-4 shrink-0 text-cyan-200" />
                </button>
              ))}
              {!(projectState?.favorite_commands ?? []).length ? (
                <div className="rounded-xl border border-dashed border-white/10 px-3 py-3 text-xs leading-5 text-slate-400">
                  Favoriten kannst du im Agent Hub über den Stern in der Befehlspalette anlegen.
                </div>
              ) : null}
            </div>
          </section>
        </section>

        <section className="rounded-2xl border border-white/10 bg-[linear-gradient(135deg,rgba(124,230,200,0.08),rgba(0,212,255,0.04))] p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-medium text-white">
                <FileText className="h-4 w-4 text-cyan-200" />
                Automatische Projektzusammenfassung
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                {projectSummary?.overview ?? "Erstellt aus Aufgaben, Agentenläufen, Artefakten, Blockern und dem aktuellen Projektfokus."}
              </p>
              {projectSummary ? (
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-white/10 bg-black/10 p-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Blocker</div>
                    <div className="mt-2 space-y-1 text-sm text-slate-200">
                      {projectSummary.blockers.length
                        ? projectSummary.blockers.slice(0, 3).map((item) => <div key={`${item.id}-${item.title}`}>• {item.title}</div>)
                        : <div>Keine bekannten Blocker</div>}
                    </div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-black/10 p-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Nächste Schritte</div>
                    <div className="mt-2 space-y-1 text-sm text-slate-200">
                      {projectSummary.next_steps.map((item) => <div key={item}>• {item}</div>)}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
            <Button
              onClick={() => void generateProjectSummary()}
              disabled={summaryBusy}
              className="shrink-0 rounded-xl bg-cyan-400/90 text-slate-950 hover:bg-cyan-300"
            >
              {summaryBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {projectSummary ? "Neu erstellen" : "Zusammenfassung erstellen"}
            </Button>
          </div>
          {panelError ? <div className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-xs text-rose-100">{panelError}</div> : null}
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
            title="Letzte Aktivitäten"
            icon={CheckCircle2}
            items={activityItems}
            emptyLabel="Noch keine Aktivität"
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
