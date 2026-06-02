import { useEffect, useState } from "react";
import { GlassModal } from "./GlassModal";
import { CalendarRange, CheckCircle2, Key, RefreshCw, Sparkles } from "lucide-react";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Switch } from "./ui/switch";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { jarvisApi } from "../lib/api";
import type { DashboardSettings, CalendarStatus } from "../lib/types";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
}

const DEFAULT_SETTINGS: DashboardSettings = {
  ui: {
    default_view: "voice-chat",
    voice_first: true,
  },
  calendar: {
    enabled: true,
    credentials_path: "./config/gmail_credentials.json",
    token_path: "./config/calendar_token.json",
  },
};

export function SettingsModal({ isOpen, onClose, onSaved }: SettingsModalProps) {
  const [settings, setSettings] = useState<DashboardSettings>(DEFAULT_SETTINGS);
  const [calendar, setCalendar] = useState<CalendarStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    let cancelled = false;
    setLoading(true);
    setError(null);
    setMessage(null);

    Promise.all([jarvisApi.getSettings(), jarvisApi.getCalendarStatus()])
      .then(([nextSettings, nextCalendar]) => {
        if (cancelled) return;
        const settingsData = nextSettings as DashboardSettings | null;
        setSettings({
          ui: {
            default_view: settingsData?.ui?.default_view ?? DEFAULT_SETTINGS.ui.default_view,
            voice_first: Boolean(settingsData?.ui?.voice_first ?? DEFAULT_SETTINGS.ui.voice_first),
          },
          calendar: {
            enabled: Boolean(settingsData?.calendar?.enabled ?? DEFAULT_SETTINGS.calendar.enabled),
            credentials_path: settingsData?.calendar?.credentials_path ?? DEFAULT_SETTINGS.calendar.credentials_path,
            token_path: settingsData?.calendar?.token_path ?? DEFAULT_SETTINGS.calendar.token_path,
          },
        });
        setCalendar(nextCalendar as CalendarStatus);
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

  const updateCalendar = (patch: Partial<DashboardSettings["calendar"]>) => {
    setSettings((current) => ({ ...current, calendar: { ...current.calendar, ...patch } }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      await jarvisApi.saveSettings(settings as unknown as Record<string, unknown>);
      if (settings.calendar.enabled) {
        const result = await jarvisApi.connectCalendar(settings.calendar) as { message?: string } | null;
        setMessage(
          result?.message
            ? String(result.message)
            : "Einstellungen gespeichert und Kalenderstatus aktualisiert."
        );
        const updated = await jarvisApi.getCalendarStatus();
        setCalendar(updated as CalendarStatus);
      } else {
        setMessage("Einstellungen gespeichert.");
        const updated = await jarvisApi.getCalendarStatus();
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
          Jarvis ist voice-first. Textchat bleibt optional. Google Calendar wird hier verbunden.
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
                <SelectItem value="resources">Ressourcen</SelectItem>
              </SelectContent>
            </Select>
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
