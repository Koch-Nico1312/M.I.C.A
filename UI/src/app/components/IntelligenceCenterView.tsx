import { memo, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { BookOpenCheck, BrainCircuit, CircleDollarSign, GitBranch, Radio, Save, Square, WandSparkles } from "lucide-react";
import { micaApi } from "../lib/api";
import type { DashboardResponse, EvidencePayload, FeatureHubPayload } from "../lib/types";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";
import { Textarea } from "./ui/textarea";

const DEFAULT_GRAPH = JSON.stringify(
  [
    { id: "research", tool: "web_search", args: { query: "M.I.C.A" }, parallel_safe: true },
    { id: "summary", tool: "advanced_knowledge", args: { action: "summary" }, depends_on: ["research"] },
  ],
  null,
  2,
);

function Card({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
      <div className="mb-4 flex items-center gap-2 text-sm font-medium text-white">{icon}{title}</div>
      {children}
    </section>
  );
}

export const IntelligenceCenterView = memo(function IntelligenceCenterView({
  dashboard,
}: {
  dashboard: DashboardResponse | null;
}) {
  const [features, setFeatures] = useState<FeatureHubPayload | null>(dashboard?.features ?? null);
  const [lessonName, setLessonName] = useState("Mein Ablauf");
  const [toolName, setToolName] = useState("web_search");
  const [toolArgs, setToolArgs] = useState('{"query":""}');
  const [evidenceQuery, setEvidenceQuery] = useState("");
  const [evidence, setEvidence] = useState<EvidencePayload | null>(null);
  const [graphJson, setGraphJson] = useState(DEFAULT_GRAPH);
  const [budget, setBudget] = useState(String(dashboard?.features?.governor.daily_budget_usd ?? 2));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (dashboard?.features) setFeatures(dashboard.features);
  }, [dashboard?.features]);

  useEffect(() => {
    if (features) return;
    micaApi.getFeatures().then(setFeatures).catch((reason) => setError(String(reason)));
  }, [features]);

  const run = async (key: string, operation: () => Promise<void>) => {
    setBusy(key);
    setError(null);
    try {
      await operation();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const refresh = async () => setFeatures(await micaApi.getFeatures());
  const teach = features?.teach_mode;
  const governor = features?.governor;
  const graphs = features?.task_graphs.items ?? [];
  const events = features?.live_events.events ?? [];

  return (
    <div className="h-full overflow-auto p-4 lg:p-6">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.28em] text-cyan-200/60">M.I.C.A Intelligence</div>
          <h2 className="mt-1 text-xl font-semibold text-white">Lernen, belegen und ausführen</h2>
        </div>
        <span className="flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-100">
          <Radio className="h-3.5 w-3.5" /> Live
        </span>
      </div>

      {error ? <div className="mb-4 rounded-xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-100">{error}</div> : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Teach Mode" icon={<WandSparkles className="h-4 w-4 text-cyan-200" />}>
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input value={lessonName} onChange={(event) => setLessonName(event.target.value)} disabled={teach?.recording} />
              {!teach?.recording ? (
                <Button onClick={() => run("teach", async () => setFeatures({ ...(await micaApi.getFeatures()), teach_mode: await micaApi.teachAction({ action: "start", name: lessonName }) }))}>Aufnehmen</Button>
              ) : (
                <Button variant="outline" onClick={() => run("teach", async () => { await micaApi.teachAction({ action: "finish" }); await refresh(); })}><Square className="mr-2 h-3.5 w-3.5" />Speichern</Button>
              )}
            </div>
            {teach?.recording ? (
              <div className="space-y-2 rounded-xl border border-cyan-400/15 bg-cyan-400/[0.06] p-3">
                <Input value={toolName} onChange={(event) => setToolName(event.target.value)} placeholder="Tool" />
                <Textarea value={toolArgs} onChange={(event) => setToolArgs(event.target.value)} className="min-h-20 font-mono text-xs" />
                <Button size="sm" disabled={busy === "teach"} onClick={() => run("teach", async () => { await micaApi.teachAction({ action: "record", tool: toolName, args: JSON.parse(toolArgs) }); await refresh(); })}>Schritt hinzufügen</Button>
                <div className="text-xs text-slate-400">{teach.active?.steps.length ?? 0} Schritt(e) aufgenommen</div>
              </div>
            ) : null}
            <div className="text-xs text-slate-400">{teach?.items.length ?? 0} gelernte Abläufe gespeichert</div>
          </div>
        </Card>

        <Card title="Evidence Mode" icon={<BookOpenCheck className="h-4 w-4 text-emerald-200" />}>
          <div className="flex gap-2">
            <Input value={evidenceQuery} onChange={(event) => setEvidenceQuery(event.target.value)} placeholder="Wofür brauchst du Belege?" />
            <Button disabled={!evidenceQuery.trim() || busy === "evidence"} onClick={() => run("evidence", async () => setEvidence(await micaApi.buildEvidence(evidenceQuery)))}>Suchen</Button>
          </div>
          <ScrollArea className="mt-3 h-40 pr-2">
            <div className="space-y-2">
              {evidence?.citations.map((citation) => (
                <div key={citation.id} className="rounded-xl border border-white/10 bg-white/[0.04] p-3 text-xs">
                  <div className="font-medium text-white">[{citation.id}] {citation.title}</div>
                  <div className="mt-1 line-clamp-3 text-slate-400">{citation.excerpt}</div>
                  <div className="mt-1 text-cyan-200/70">{citation.source} · {citation.uri}</div>
                </div>
              ))}
              {!evidence ? <div className="text-xs text-slate-500">Noch keine Belegsuche ausgeführt.</div> : null}
            </div>
          </ScrollArea>
        </Card>

        <Card title="Task Graph" icon={<GitBranch className="h-4 w-4 text-violet-200" />}>
          <Textarea value={graphJson} onChange={(event) => setGraphJson(event.target.value)} className="min-h-36 font-mono text-xs" />
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="text-xs text-slate-400">{graphs.length} Graph(en), mit Retry und Abbruch</span>
            <Button size="sm" onClick={() => run("graph", async () => { await micaApi.taskGraphAction({ action: "create", name: "UI Task Graph", steps: JSON.parse(graphJson) }); await refresh(); })}>Graph erstellen</Button>
          </div>
          <div className="mt-3 space-y-2">
            {graphs.slice(0, 3).map((graph) => (
              <div key={graph.id} className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.04] p-3 text-xs">
                <div><div className="text-white">{graph.name}</div><div className="text-slate-400">{graph.status} · {graph.steps.length} Schritte</div></div>
                <Button size="sm" variant="outline" onClick={() => run("graph", async () => { await micaApi.taskGraphAction({ action: graph.status === "failed" ? "retry" : "run", graph_id: graph.id }); await refresh(); })}>{graph.status === "failed" ? "Retry" : "Start"}</Button>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Kosten- und Datenschutz-Governor" icon={<CircleDollarSign className="h-4 w-4 text-amber-200" />}>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-xl bg-white/[0.04] p-3"><div className="text-lg text-white">${governor?.daily_cost_usd_estimate ?? 0}</div><div className="text-slate-400">Heute</div></div>
            <div className="rounded-xl bg-white/[0.04] p-3"><div className="text-lg text-white">{governor?.daily_tokens_estimate ?? 0}</div><div className="text-slate-400">Tokens</div></div>
            <div className="rounded-xl bg-white/[0.04] p-3"><div className="text-lg text-white">{governor?.budget_used_percent ?? 0}%</div><div className="text-slate-400">Budget</div></div>
          </div>
          <div className="mt-3 flex gap-2">
            <Input type="number" min="0" step="0.25" value={budget} onChange={(event) => setBudget(event.target.value)} />
            <Button variant="outline" onClick={() => run("budget", async () => { await micaApi.saveGovernor(Number(budget)); await refresh(); })}><Save className="mr-2 h-3.5 w-3.5" />Tagesbudget</Button>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-400"><BrainCircuit className="h-4 w-4" />{governor?.local_first ? "Local-first aktiv" : "Cloud-Routing erlaubt"}</div>
        </Card>

        <Card title="Live-Ereignisse" icon={<Radio className="h-4 w-4 text-rose-200" />}>
          <ScrollArea className="h-48 pr-2">
            <div className="space-y-2">
              {[...events].reverse().slice(0, 12).map((event) => (
                <div key={event.id} className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs">
                  <span className="text-cyan-200">#{event.id} {event.type}</span>
                  <span className="ml-2 text-slate-500">{new Date(event.timestamp).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          </ScrollArea>
        </Card>
      </div>
    </div>
  );
});
