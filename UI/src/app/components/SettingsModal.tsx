import { useEffect, useState } from "react";
import { GlassModal } from "./GlassModal";
import { Bot, CalendarRange, CheckCircle2, Image as ImageIcon, Key, Link2, RefreshCw, Sparkles, Upload } from "lucide-react";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Switch } from "./ui/switch";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { CUSTOM_BACKGROUND_STORAGE_KEY, MICA_BACKGROUND_PRESETS } from "../lib/backgrounds";
import { micaApi } from "../lib/api";
import type { DashboardSettings, CalendarStatus, ModelsPayload, SetupPayload } from "../lib/types";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
}

const DEFAULT_SETTINGS: DashboardSettings = {
  ui: {
    default_view: "voice-chat",
    voice_first: true,
    background_id: "lake",
    background_url: "/backgrounds/mica-lake.jpg",
  },
  calendar: {
    enabled: true,
    credentials_path: "./config/gmail_credentials.json",
    token_path: "./config/calendar_token.json",
  },
  model_router: {
    preferred_profile: "fast",
    model_scope: "linked",
    cost_mode: "balanced",
  },
};

export function SettingsModal({ isOpen, onClose, onSaved }: SettingsModalProps) {
  const [settings, setSettings] = useState<DashboardSettings>(DEFAULT_SETTINGS);
  const [calendar, setCalendar] = useState<CalendarStatus | null>(null);
  const [setup, setSetup] = useState<SetupPayload | null>(null);
  const [models, setModels] = useState<ModelsPayload | null>(null);
  const [geminiKey, setGeminiKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [ollamaEnabled, setOllamaEnabled] = useState(false);
  const [ollamaModel, setOllamaModel] = useState("llama3.1");
  const [ollamaBaseUrl, setOllamaBaseUrl] = useState("http://localhost:11434");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [customBackgroundPreview, setCustomBackgroundPreview] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    let cancelled = false;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      setCustomBackgroundPreview(window.localStorage.getItem(CUSTOM_BACKGROUND_STORAGE_KEY));
    } catch {
      setCustomBackgroundPreview(null);
    }

    Promise.all([
      micaApi.getSettings(),
      micaApi.getCalendarStatus(),
      micaApi.getSetup(),
      micaApi.getModels(),
    ])
      .then(([nextSettings, nextCalendar, nextSetup, nextModels]) => {
        if (cancelled) return;
        const settingsData = nextSettings as DashboardSettings | null;
        const setupData = nextSetup as SetupPayload;
        const modelData = nextModels as ModelsPayload;
        setSettings({
          ui: {
            default_view: settingsData?.ui?.default_view ?? DEFAULT_SETTINGS.ui.default_view,
            voice_first: Boolean(settingsData?.ui?.voice_first ?? DEFAULT_SETTINGS.ui.voice_first),
            background_id: settingsData?.ui?.background_id ?? DEFAULT_SETTINGS.ui.background_id,
            background_url: settingsData?.ui?.background_url ?? DEFAULT_SETTINGS.ui.background_url,
          },
          calendar: {
            enabled: Boolean(settingsData?.calendar?.enabled ?? DEFAULT_SETTINGS.calendar.enabled),
            credentials_path: settingsData?.calendar?.credentials_path ?? DEFAULT_SETTINGS.calendar.credentials_path,
            token_path: settingsData?.calendar?.token_path ?? DEFAULT_SETTINGS.calendar.token_path,
          },
          model_router: {
            preferred_profile:
              settingsData?.model_router?.preferred_profile
              ?? modelData?.preferred_profile
              ?? DEFAULT_SETTINGS.model_router?.preferred_profile
              ?? "fast",
            model_scope:
              settingsData?.model_router?.model_scope
              ?? modelData?.scope
              ?? DEFAULT_SETTINGS.model_router?.model_scope
              ?? "linked",
            cost_mode:
              settingsData?.model_router?.cost_mode
              ?? DEFAULT_SETTINGS.model_router?.cost_mode
              ?? "balanced",
          },
        });
        setCalendar(nextCalendar as CalendarStatus);
        setSetup(setupData);
        setModels(modelData);
        setOllamaBaseUrl(setupData?.ollama_base_url || "http://localhost:11434");
        setOllamaEnabled(Boolean(modelData?.all_models?.some((model) => model.provider === "ollama" && model.enabled)));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Einstellungen konnten nicht geladen werden.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  const updateUi = (patch: Partial<DashboardSettings["ui"]>) => {
    setSettings((current) => ({ ...current, ui: { ...current.ui, ...patch } }));
  };

  const handleBackgroundPreset = (id: string, url: string) => {
    updateUi({ background_id: id, background_url: url });
  };

  const handleCustomBackground = (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Bitte ein Bild auswählen.");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      if (!result) {
        setError("Bild konnte nicht gelesen werden.");
        return;
      }
      try {
        window.localStorage.setItem(CUSTOM_BACKGROUND_STORAGE_KEY, result);
      } catch {
        setError("Das Bild ist zu groß für den lokalen Browserspeicher.");
        return;
      }
      setCustomBackgroundPreview(result);
      updateUi({ background_id: "custom", background_url: "custom" });
      setMessage("Eigenes Hintergrundbild ausgewählt. Speichern übernimmt es dauerhaft.");
    };
    reader.onerror = () => setError("Bild konnte nicht gelesen werden.");
    reader.readAsDataURL(file);
  };

  const updateCalendar = (patch: Partial<DashboardSettings["calendar"]>) => {
    setSettings((current) => ({ ...current, calendar: { ...current.calendar, ...patch } }));
  };

  const updateModelRouter = (patch: Partial<NonNullable<DashboardSettings["model_router"]>>) => {
    setSettings((current) => ({
      ...current,
      model_router: {
        preferred_profile: current.model_router?.preferred_profile ?? "fast",
        model_scope: current.model_router?.model_scope ?? "linked",
        cost_mode: current.model_router?.cost_mode ?? "balanced",
        ...patch,
      },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      await micaApi.saveSetup({
        gemini_api_key: geminiKey,
        openai_api_key: openaiKey,
        ollama_base_url: ollamaBaseUrl,
        ollama_enabled: ollamaEnabled,
        ollama_model: ollamaModel,
        model_router: settings.model_router,
      });
      await micaApi.saveSettings(settings as unknown as Record<string, unknown>);
      if (settings.calendar.enabled) {
        const result = await micaApi.connectCalendar(settings.calendar) as { message?: string } | null;
        setMessage(
          result?.message
            ? String(result.message)
            : "Einstellungen gespeichert und Kalenderstatus aktualisiert."
        );
        const updated = await micaApi.getCalendarStatus();
        setCalendar(updated as CalendarStatus);
      } else {
        setMessage("Einstellungen gespeichert.");
        const updated = await micaApi.getCalendarStatus();
        setCalendar(updated as CalendarStatus);
      }
      onSaved();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <GlassModal isOpen={isOpen} onClose={onClose} title="Einstellungen">
      <div className="space-y-6 text-slate-100">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
          M.I.C.A ist voice-first. Textchat bleibt optional. Modelle, API-Keys und Google Calendar werden hier verbunden.
        </div>

        <div className="space-y-3 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-white">
            <Key className="h-4 w-4 text-cyan-300" />
            Erststart & API-Keys
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-sm text-white">Gemini API-Key</Label>
              <Input
                type="password"
                value={geminiKey}
                onChange={(event) => setGeminiKey(event.target.value)}
                className="border-white/10 bg-black/20 text-white placeholder:text-slate-500"
                placeholder={setup?.has_gemini_key ? "Bereits gespeichert" : "AIza..."}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-white">OpenAI-kompatibler Key</Label>
              <Input
                type="password"
                value={openaiKey}
                onChange={(event) => setOpenaiKey(event.target.value)}
                className="border-white/10 bg-black/20 text-white placeholder:text-slate-500"
                placeholder={setup?.has_openai_key ? "Bereits gespeichert" : "Optional"}
              />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
            <div className="space-y-2">
              <Label className="text-sm text-white">Ollama URL</Label>
              <Input
                value={ollamaBaseUrl}
                onChange={(event) => setOllamaBaseUrl(event.target.value)}
                className="border-white/10 bg-black/20 text-white placeholder:text-slate-500"
                placeholder="http://localhost:11434"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-white">Lokales Modell</Label>
              <Input
                value={ollamaModel}
                onChange={(event) => setOllamaModel(event.target.value)}
                className="border-white/10 bg-black/20 text-white placeholder:text-slate-500"
                placeholder="llama3.1"
              />
            </div>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/10 px-4 py-3">
              <Link2 className="h-4 w-4 text-cyan-300" />
              <Switch checked={ollamaEnabled} onCheckedChange={setOllamaEnabled} />
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/10 px-4 py-3 text-xs text-slate-300">
            <div className="flex items-center justify-between gap-3">
              <span>Setup</span>
              <span className={setup?.configured ? "text-emerald-300" : "text-amber-300"}>
                {setup?.configured ? "Konfiguriert" : "Offen"}
              </span>
            </div>
            <div className="mt-2 truncate text-slate-400">{setup?.api_keys_path ?? "config/api_keys.json"}</div>
          </div>
        </div>

        <div className="space-y-3 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-white">
            <Sparkles className="h-4 w-4 text-cyan-300" />
            UI Verhalten
          </div>

          <div className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-black/10 px-4 py-3">
            <div>
              <Label className="text-sm text-white">Voice-first Standard</Label>
              <p className="text-xs text-slate-400">
                Wenn die UI startet, soll Sprechen der Hauptmodus sein.
              </p>
            </div>
            <Switch
              checked={settings.ui.voice_first}
              onCheckedChange={(checked) => updateUi({ voice_first: checked })}
            />
          </div>

          <div className="space-y-2">
            <Label className="text-sm text-white">Startansicht</Label>
            <Select
              value={settings.ui.default_view}
              onValueChange={(value) => updateUi({ default_view: value })}
            >
              <SelectTrigger className="border-white/10 bg-black/20 text-white">
                <SelectValue placeholder="Ansicht auswählen" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="voice-chat">Sprechen</SelectItem>
                <SelectItem value="home">Startseite</SelectItem>
                <SelectItem value="chats">Chats</SelectItem>
                <SelectItem value="command-center">Command</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <ImageIcon className="h-4 w-4 text-cyan-300" />
              Hintergrund
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {MICA_BACKGROUND_PRESETS.map((preset) => {
                const active = settings.ui.background_id === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => handleBackgroundPreset(preset.id, preset.url)}
                    className={`group overflow-hidden rounded-xl border text-left transition ${
                      active
                        ? "border-cyan-300/70 bg-cyan-300/10 shadow-[0_0_0_1px_rgba(103,232,249,0.22)]"
                        : "border-white/10 bg-black/10 hover:border-white/25 hover:bg-white/10"
                    }`}
                  >
                    <div
                      className="h-24 bg-cover bg-center"
                      style={{ backgroundImage: `url("${preset.url}")` }}
                    />
                    <div className="px-3 py-2">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-white">{preset.label}</span>
                        {active ? <CheckCircle2 className="h-4 w-4 text-cyan-300" /> : null}
                      </div>
                      <p className="mt-1 text-xs text-slate-400">{preset.description}</p>
                    </div>
                  </button>
                );
              })}
            </div>

            <label
              className={`flex cursor-pointer items-center justify-between gap-4 rounded-xl border px-4 py-3 transition ${
                settings.ui.background_id === "custom"
                  ? "border-cyan-300/70 bg-cyan-300/10"
                  : "border-white/10 bg-black/10 hover:border-white/25 hover:bg-white/10"
              }`}
            >
              <div className="flex min-w-0 items-center gap-3">
                <div
                  className="h-12 w-16 shrink-0 rounded-lg border border-white/10 bg-cover bg-center bg-black/20"
                  style={{
                    backgroundImage: customBackgroundPreview
                      ? `url("${customBackgroundPreview}")`
                      : "linear-gradient(135deg, rgba(125,211,252,0.22), rgba(15,23,42,0.8))",
                  }}
                />
                <div className="min-w-0">
                  <div className="text-sm font-medium text-white">Eigenes Bild</div>
                  <div className="truncate text-xs text-slate-400">Lokal auswählen und als Hintergrund verwenden</div>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-cyan-100">
                <Upload className="h-4 w-4" />
                Auswählen
              </div>
              <input
                type="file"
                accept="image/*"
                className="sr-only"
                onChange={(event) => {
                  handleCustomBackground(event.target.files?.[0] ?? null);
                  event.currentTarget.value = "";
                }}
              />
            </label>
          </div>
        </div>

        <div className="space-y-3 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-white">
            <Bot className="h-4 w-4 text-cyan-300" />
            Modellwahl
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="space-y-2">
              <Label className="text-sm text-white">Sichtbare Modelle</Label>
              <Select
                value={settings.model_router?.model_scope ?? "linked"}
                onValueChange={(value) => updateModelRouter({ model_scope: value })}
              >
                <SelectTrigger className="border-white/10 bg-black/20 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="linked">Verknüpfte Modelle</SelectItem>
                  <SelectItem value="all">Alle möglichen Modelle</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-white">Standardprofil</Label>
              <Select
                value={settings.model_router?.preferred_profile ?? "fast"}
                onValueChange={(value) => updateModelRouter({ preferred_profile: value })}
              >
                <SelectTrigger className="border-white/10 bg-black/20 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(models?.all_models?.length ? models.all_models : models?.models ?? []).map((model) => (
                    <SelectItem key={model.name} value={model.name}>
                      {model.name} · {model.provider}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-white">Kostenmodus</Label>
              <Select
                value={settings.model_router?.cost_mode ?? "balanced"}
                onValueChange={(value) => updateModelRouter({ cost_mode: value })}
              >
                <SelectTrigger className="border-white/10 bg-black/20 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="balanced">Ausgewogen</SelectItem>
                  <SelectItem value="economy">Sparsam</SelectItem>
                  <SelectItem value="quality">Qualität</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-2 md:grid-cols-2">
            {(models?.models ?? []).slice(0, 6).map((model) => (
              <div key={`${model.provider}-${model.name}`} className="rounded-xl border border-white/10 bg-black/10 px-4 py-3 text-xs text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-white">{model.name}</span>
                  <span className={model.linked ? "text-emerald-300" : "text-slate-400"}>
                    {model.linked ? "verknüpft" : "nicht verknüpft"}
                  </span>
                </div>
                <div className="mt-1 truncate text-slate-400">{model.model_id}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-white">
            <CalendarRange className="h-4 w-4 text-cyan-300" />
            Google Calendar
          </div>

          <div className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-black/10 px-4 py-3">
            <div>
              <Label className="text-sm text-white">Integration aktiv</Label>
              <p className="text-xs text-slate-400">
                Nur aktivieren, wenn du Kalenderzugriff erlauben willst.
              </p>
            </div>
            <Switch
              checked={settings.calendar.enabled}
              onCheckedChange={(checked) => updateCalendar({ enabled: checked })}
            />
          </div>

          <div className="space-y-2">
            <Label className="text-sm text-white">Credentials Datei</Label>
            <Input
              value={settings.calendar.credentials_path}
              onChange={(e) => updateCalendar({ credentials_path: e.target.value })}
              className="border-white/10 bg-black/20 text-white placeholder:text-slate-500"
              placeholder="./config/gmail_credentials.json"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-sm text-white">Token Datei</Label>
            <Input
              value={settings.calendar.token_path}
              onChange={(e) => updateCalendar({ token_path: e.target.value })}
              className="border-white/10 bg-black/20 text-white placeholder:text-slate-500"
              placeholder="./config/calendar_token.json"
            />
          </div>

          <div className="rounded-xl border border-white/10 bg-black/10 px-4 py-3 text-xs text-slate-300">
            <div className="flex items-center justify-between gap-3">
              <span>Status</span>
              <span className={calendar?.authenticated ? "text-emerald-300" : "text-amber-300"}>
                {calendar?.authenticated ? "Verbunden" : "Nicht verbunden"}
              </span>
            </div>
            <div className="mt-2 flex items-center justify-between gap-3">
              <span>Konfiguriert</span>
              <span className={calendar?.configured ? "text-cyan-200" : "text-slate-400"}>
                {calendar?.configured ? "Ja" : "Nein"}
              </span>
            </div>
          </div>
        </div>

        {error ? (
          <div className="rounded-2xl border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
            {error}
          </div>
        ) : null}

        {message ? (
          <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-100">
            {message}
          </div>
        ) : null}

        <div className="flex items-center justify-between gap-3">
          <div className="text-xs text-slate-400">
            {loading ? "Lade Einstellungen..." : "Änderungen werden lokal gespeichert."}
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
            >
              Schließen
            </Button>
            <Button
              type="button"
              onClick={handleSave}
              disabled={saving || loading}
              className="gap-2 bg-cyan-400 text-slate-950 hover:bg-cyan-300"
            >
              {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              Speichern
            </Button>
          </div>
        </div>
      </div>
    </GlassModal>
  );
}
