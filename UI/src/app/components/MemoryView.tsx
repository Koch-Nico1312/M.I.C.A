import { useEffect, useMemo, useState } from "react";
import { Download, Eraser, RefreshCw, Save, Search } from "lucide-react";
import { jarvisApi } from "../lib/api";
import type { MemoryEntry, MemoryPayload } from "../lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { ScrollArea } from "./ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Textarea } from "./ui/textarea";

const emptyEntry = {
  category: "notes",
  key: "",
  value: "",
  tags: "",
};

export function MemoryView() {
  const [memory, setMemory] = useState<MemoryPayload | null>(null);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState(emptyEntry);
  const [selectedEntry, setSelectedEntry] = useState<MemoryEntry | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadMemory = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await jarvisApi.getMemory();
      setMemory(payload);
      if (!payload.categories.includes(draft.category) && payload.categories[0]) {
        setDraft((current) => ({ ...current, category: payload.categories[0] }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Memory konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMemory();
  }, []);

  const entries = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return (memory?.entries ?? []).filter((entry) => {
      const categoryMatch = selectedCategory === "all" || entry.category === selectedCategory;
      const queryMatch =
        !normalizedQuery ||
        entry.key.toLowerCase().includes(normalizedQuery) ||
        String(entry.value).toLowerCase().includes(normalizedQuery) ||
        entry.category.toLowerCase().includes(normalizedQuery);
      return categoryMatch && queryMatch;
    });
  }, [memory, query, selectedCategory]);

  const startEdit = (entry: MemoryEntry) => {
    setSelectedEntry(entry);
    setDraft({
      category: entry.category,
      key: entry.key,
      value: String(entry.value ?? ""),
      tags: (entry.tags ?? []).join(", "),
    });
    setMessage(null);
    setError(null);
  };

  const resetDraft = () => {
    setSelectedEntry(null);
    setDraft({
      ...emptyEntry,
      category: memory?.categories?.[0] ?? "notes",
    });
  };

  const saveDraft = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const result = await jarvisApi.upsertMemory({
        category: draft.category,
        key: draft.key,
        value: draft.value,
        tags: draft.tags,
      });
      setMemory(result.memory);
      setMessage("Memory gespeichert.");
      resetDraft();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen.");
    } finally {
      setSaving(false);
    }
  };

  const forgetEntry = async (entry: MemoryEntry) => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const result = await jarvisApi.forgetMemory({ category: entry.category, key: entry.key });
      setMemory(result.memory);
      setMessage(result.status);
      if (selectedEntry?.id === entry.id) {
        resetDraft();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vergessen fehlgeschlagen.");
    } finally {
      setSaving(false);
    }
  };

  const exportMemory = async () => {
    const payload = await jarvisApi.exportMemory();
    const blob = new Blob([JSON.stringify(payload.raw ?? payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "jarvis-memory-export.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-full flex-col bg-[#071823]">
      <div className="border-b border-white/10 px-5 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">Memory</h2>
            <p className="text-sm text-slate-400">
              {memory?.entries?.length ?? 0} Einträge · {memory?.path ?? "memory/long_term.json"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={loadMemory}
              disabled={loading}
              className="gap-2 border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              Aktualisieren
            </Button>
            <Button
              type="button"
              onClick={exportMemory}
              className="gap-2 bg-cyan-400 text-slate-950 hover:bg-cyan-300"
            >
              <Download className="h-4 w-4" />
              Export
            </Button>
          </div>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[360px_1fr]">
        <section className="min-h-0 border-r border-white/10 p-4">
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              <div className="space-y-2">
                <Label className="text-sm text-white">Kategorie</Label>
                <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                  <SelectTrigger className="border-white/10 bg-black/20 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Alle Kategorien</SelectItem>
                    {(memory?.categories ?? []).map((category) => (
                      <SelectItem key={category} value={category}>
                        {category}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-white">Suche</Label>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                  <Input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    className="border-white/10 bg-black/20 pl-9 text-white placeholder:text-slate-500"
                    placeholder="Name, Wert, Kategorie"
                  />
                </div>
              </div>
            </div>

            <ScrollArea className="h-[calc(100vh-310px)] min-h-[280px]">
              <div className="space-y-2 pr-3">
                {entries.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => startEdit(entry)}
                    className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                      selectedEntry?.id === entry.id
                        ? "border-cyan-300/50 bg-cyan-300/10"
                        : "border-white/10 bg-white/5 hover:bg-white/8"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-white">{entry.key}</span>
                      <Badge variant="outline" className="border-white/10 text-slate-300">
                        {entry.category}
                      </Badge>
                    </div>
                    <p className="mt-2 line-clamp-2 text-xs text-slate-400">{entry.value}</p>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </div>
        </section>

        <section className="min-h-0 p-5">
          <div className="mx-auto flex h-full max-w-3xl flex-col gap-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-white">
                  {selectedEntry ? "Eintrag bearbeiten" : "Neuer Eintrag"}
                </h3>
                <p className="text-sm text-slate-400">Einträge werden direkt in der Langzeit-Memory gespeichert.</p>
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={resetDraft}
                className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
              >
                Neu
              </Button>
            </div>

            <div className="grid gap-4 md:grid-cols-[180px_1fr]">
              <div className="space-y-2">
                <Label className="text-sm text-white">Kategorie</Label>
                <Select
                  value={draft.category}
                  onValueChange={(category) => setDraft((current) => ({ ...current, category }))}
                >
                  <SelectTrigger className="border-white/10 bg-black/20 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(memory?.categories ?? ["notes"]).map((category) => (
                      <SelectItem key={category} value={category}>
                        {category}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-white">Schlüssel</Label>
                <Input
                  value={draft.key}
                  onChange={(event) => setDraft((current) => ({ ...current, key: event.target.value }))}
                  className="border-white/10 bg-black/20 text-white placeholder:text-slate-500"
                  placeholder="z.B. bevorzugte_ansprache"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm text-white">Wert</Label>
              <Textarea
                value={draft.value}
                onChange={(event) => setDraft((current) => ({ ...current, value: event.target.value }))}
                className="min-h-[180px] border-white/10 bg-black/20 text-white placeholder:text-slate-500"
                placeholder="Was soll Jarvis wissen?"
              />
            </div>

            <div className="space-y-2">
              <Label className="text-sm text-white">Tags</Label>
              <Input
                value={draft.tags}
                onChange={(event) => setDraft((current) => ({ ...current, tags: event.target.value }))}
                className="border-white/10 bg-black/20 text-white placeholder:text-slate-500"
                placeholder="optional, komma-getrennt"
              />
            </div>

            {error ? (
              <div className="rounded-lg border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                {error}
              </div>
            ) : null}
            {message ? (
              <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-100">
                {message}
              </div>
            ) : null}

            <div className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => selectedEntry && forgetEntry(selectedEntry)}
                disabled={!selectedEntry || saving}
                className="gap-2 border-rose-300/20 bg-rose-300/10 text-rose-100 hover:bg-rose-300/15"
              >
                <Eraser className="h-4 w-4" />
                Vergessen
              </Button>
              <Button
                type="button"
                onClick={saveDraft}
                disabled={saving || !draft.key.trim() || !draft.value.trim()}
                className="gap-2 bg-cyan-400 text-slate-950 hover:bg-cyan-300"
              >
                {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Speichern
              </Button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
