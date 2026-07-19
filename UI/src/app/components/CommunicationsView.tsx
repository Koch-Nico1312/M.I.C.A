import { useEffect, useMemo, useState } from "react";
import { BellRing, Bot, CheckCircle2, Home, Link2, Loader2, MessageCircle, Phone, RefreshCw, Send, ShieldCheck, Smartphone } from "lucide-react";

import { micaApi } from "../lib/api";
import type { CommunicationsPayload } from "../lib/types";

type Notice = { tone: "ok" | "error"; text: string } | null;

const emptyPayload: CommunicationsPayload = {
  channels: {},
  smart_home: {},
  telegram_offset: 0,
  paired_identities: {},
  events: [],
};

function StatusCard({ icon: Icon, title, ready, detail }: { icon: typeof Bot; title: string; ready: boolean; detail: string }) {
  return (
    <article className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
      <div className="flex items-start justify-between gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-lg bg-cyan-300/10 text-cyan-200"><Icon className="h-4 w-4" /></span>
        <span className={`rounded-full px-2 py-1 text-[10px] ${ready ? "bg-emerald-300/10 text-emerald-200" : "bg-amber-300/10 text-amber-100"}`}>{ready ? "Bereit" : "Einrichtung nötig"}</span>
      </div>
      <strong className="mt-4 block text-sm text-white/90">{title}</strong>
      <small className="mt-1 block text-xs text-white/45">{detail}</small>
    </article>
  );
}

export function CommunicationsView() {
  const [data, setData] = useState<CommunicationsPayload>(emptyPayload);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState<Notice>(null);
  const [telegram, setTelegram] = useState({ token: "", chatId: "", senderId: "" });
  const [message, setMessage] = useState("");
  const [call, setCall] = useState({ number: "", message: "Hallo, hier ist M.I.C.A." });
  const [telephony, setTelephony] = useState({ sid: "", token: "", from: "", webhook: "" });
  const [home, setHome] = useState({ url: "", token: "" });

  const reload = async () => {
    setLoading(true);
    try {
      setData(await micaApi.getCommunications());
    } catch (error) {
      setNotice({ tone: "error", text: error instanceof Error ? error.message : "Kommunikationsstatus konnte nicht geladen werden." });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void reload(); }, []);

  const act = async (key: string, payload: Record<string, unknown>, success: string) => {
    setBusy(key);
    setNotice(null);
    try {
      const result = await micaApi.communicationAction(payload);
      if (result.error && !result.approval_required) throw new Error(String(result.error));
      setNotice({ tone: result.ok === false ? "error" : "ok", text: result.error ? String(result.error) : success });
      if (result.communications) setData(result.communications as CommunicationsPayload);
      else if (result.snapshot) setData(result.snapshot as CommunicationsPayload);
      else await reload();
    } catch (error) {
      setNotice({ tone: "error", text: error instanceof Error ? error.message : "Aktion fehlgeschlagen." });
    } finally {
      setBusy("");
    }
  };

  const cards = useMemo(() => [
    { icon: Bot, title: "Telegram", ready: Boolean(data.channels.telegram?.configured), detail: `${data.channels.telegram?.paired ?? 0} freigegebene Identität(en)` },
    { icon: Phone, title: "Telefon", ready: Boolean(data.channels.telephony?.enabled && data.channels.telephony?.credentials_ready), detail: data.channels.telephony?.provider || "Twilio oder SIP" },
    { icon: Smartphone, title: "Companion", ready: Boolean(data.channels.companion?.configured), detail: `${data.channels.companion?.paired ?? 0} gekoppelte Geräte` },
    { icon: Home, title: "Home Assistant", ready: Boolean(data.smart_home?.connected), detail: `${data.smart_home?.total_devices ?? 0} Geräte verbunden` },
  ], [data]);

  return (
    <div className="h-full overflow-auto rounded-2xl border border-white/10 bg-[#06121b]/92 p-4 shadow-2xl backdrop-blur-xl lg:p-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <div className="flex items-center gap-2 text-cyan-200"><Link2 className="h-5 w-5" /><span className="text-xs uppercase tracking-[0.25em]">Verbindungen</span></div>
          <h2 className="mt-2 text-xl font-semibold text-white/95">M.I.C.A Kommunikationszentrale</h2>
          <p className="mt-1 text-xs text-white/50">Telegram, Anrufe, Companion, proaktive Hinweise und Smart Home mit gemeinsamer Freigabelogik.</p>
        </div>
        <button onClick={() => void reload()} className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/70 hover:bg-white/10"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Aktualisieren</button>
      </header>

      {notice ? <div className={`mt-4 rounded-lg border px-3 py-2 text-xs ${notice.tone === "ok" ? "border-emerald-300/20 bg-emerald-300/10 text-emerald-100" : "border-rose-300/20 bg-rose-300/10 text-rose-100"}`}>{notice.text}</div> : null}

      <section className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map((card) => <StatusCard key={card.title} {...card} />)}</section>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <section className="rounded-xl border border-white/10 bg-black/10 p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-white/90"><MessageCircle className="h-4 w-4 text-cyan-200" />Telegram einrichten</h3>
          <p className="mt-1 text-[11px] text-white/45">Der Bot akzeptiert nur die hier freigegebene Chat-ID oder später bestätigte Pairings.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-[10px] text-white/50">Bot-Token<input type="password" value={telegram.token} onChange={(event) => setTelegram({ ...telegram, token: event.target.value })} className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white outline-none focus:border-cyan-300/30" /></label>
            <label className="grid gap-1 text-[10px] text-white/50">Chat-ID<input value={telegram.chatId} onChange={(event) => setTelegram({ ...telegram, chatId: event.target.value })} className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white outline-none focus:border-cyan-300/30" /></label>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button disabled={busy === "telegram" || !telegram.token || !telegram.chatId} onClick={() => void act("telegram", { action: "configure", telegram: { enabled: true, bot_token: telegram.token, chat_id: telegram.chatId, allowed_sender_ids: [telegram.chatId], mode: "polling" }, proactive: { enabled: true, channels: ["telegram"] } }, "Telegram und proaktive Hinweise wurden gespeichert.")} className="flex items-center gap-2 rounded-lg bg-cyan-200 px-3 py-2 text-xs font-medium text-slate-950 disabled:opacity-40">{busy === "telegram" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}Sicher verbinden</button>
            <button disabled={busy === "poll" || !data.channels.telegram?.configured} onClick={() => void act("poll", { action: "poll" }, "Telegram wurde abgefragt.")} className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/70 disabled:opacity-40">Nachrichten abrufen</button>
          </div>
          <div className="mt-4 border-t border-white/10 pt-4">
            <label className="grid gap-1 text-[10px] text-white/50">Weitere Telegram-ID koppeln<input value={telegram.senderId} onChange={(event) => setTelegram({ ...telegram, senderId: event.target.value })} className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white outline-none" /></label>
            <button disabled={!telegram.senderId || busy === "pair"} onClick={() => void act("pair", { action: "pair", channel: "telegram", sender_id: telegram.senderId, label: "Telegram", confirmed: true }, "Telegram-ID wurde gekoppelt.")} className="mt-2 flex items-center gap-2 rounded-lg border border-cyan-200/20 bg-cyan-200/5 px-3 py-2 text-xs text-cyan-100 disabled:opacity-40"><Link2 className="h-4 w-4" />Koppeln</button>
          </div>
        </section>

        <section className="rounded-xl border border-white/10 bg-black/10 p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-white/90"><Send className="h-4 w-4 text-cyan-200" />Nachricht senden</h3>
          <textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={5} placeholder="Nachricht, Zusammenfassung oder Erinnerung…" className="mt-4 w-full resize-none rounded-lg border border-white/10 bg-[#081923] p-3 text-xs text-white outline-none focus:border-cyan-300/30" />
          <button disabled={!message || busy === "send" || !data.channels.telegram?.configured} onClick={() => { if (window.confirm("Diese Nachricht wirklich über Telegram senden?")) void act("send", { action: "send", channel: "telegram", text: message, confirmed: true }, "Nachricht wurde gesendet."); }} className="mt-3 flex items-center gap-2 rounded-lg bg-cyan-200 px-3 py-2 text-xs font-medium text-slate-950 disabled:opacity-40"><Send className="h-4 w-4" />Mit Bestätigung senden</button>
        </section>

        <section className="rounded-xl border border-white/10 bg-black/10 p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-white/90"><Phone className="h-4 w-4 text-cyan-200" />Telefonie</h3>
          <p className="mt-1 text-[11px] text-white/45">Twilio-Zugangsdaten werden lokal gespeichert. Jeder Anruf benötigt erneut deine Bestätigung.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-[10px] text-white/50">Account SID<input value={telephony.sid} onChange={(event) => setTelephony({ ...telephony, sid: event.target.value })} className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white" /></label>
            <label className="grid gap-1 text-[10px] text-white/50">Auth Token<input type="password" value={telephony.token} onChange={(event) => setTelephony({ ...telephony, token: event.target.value })} className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white" /></label>
            <label className="grid gap-1 text-[10px] text-white/50">M.I.C.A Rufnummer<input value={telephony.from} onChange={(event) => setTelephony({ ...telephony, from: event.target.value })} className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white" /></label>
            <label className="grid gap-1 text-[10px] text-white/50">Öffentliche Webhook-URL<input value={telephony.webhook} onChange={(event) => setTelephony({ ...telephony, webhook: event.target.value })} className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white" /></label>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-[10px] text-white/50">Erlaubte Zielnummer<input value={call.number} onChange={(event) => setCall({ ...call, number: event.target.value })} className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white" /></label>
            <label className="grid gap-1 text-[10px] text-white/50">Gesprochene Nachricht<input value={call.message} onChange={(event) => setCall({ ...call, message: event.target.value })} className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white" /></label>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button disabled={!telephony.sid || !telephony.token || !telephony.from || !call.number || busy === "phone-config"} onClick={() => void act("phone-config", { action: "configure", telephony: { enabled: true, provider: "twilio", account_sid: telephony.sid, auth_token: telephony.token, from_number: telephony.from, webhook_url: telephony.webhook, allowed_numbers: [call.number], allow_inbound: true } }, "Telefonie wurde gespeichert.")} className="rounded-lg border border-cyan-200/20 bg-cyan-200/5 px-3 py-2 text-xs text-cyan-100 disabled:opacity-40">Telefonie speichern</button>
            <button disabled={!call.number || !call.message || busy === "call" || !data.channels.telephony?.credentials_ready} onClick={() => { if (window.confirm(`M.I.C.A soll ${call.number} jetzt anrufen?`)) void act("call", { action: "call", number: call.number, message: call.message, confirmed: true }, "Anruf wurde gestartet."); }} className="flex items-center gap-2 rounded-lg bg-cyan-200 px-3 py-2 text-xs font-medium text-slate-950 disabled:opacity-40"><Phone className="h-4 w-4" />Jetzt anrufen</button>
          </div>
        </section>

        <section className="rounded-xl border border-white/10 bg-black/10 p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-white/90"><Home className="h-4 w-4 text-cyan-200" />Home Assistant</h3>
          <p className="mt-1 text-[11px] text-white/45">Verwendet die bereits vorhandene lokale Geräte- und Szenensteuerung.</p>
          <div className="mt-4 grid gap-3">
            <label className="grid gap-1 text-[10px] text-white/50">Home-Assistant URL<input value={home.url} onChange={(event) => setHome({ ...home, url: event.target.value })} placeholder="http://homeassistant.local:8123" className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white" /></label>
            <label className="grid gap-1 text-[10px] text-white/50">Long-Lived Access Token<input type="password" value={home.token} onChange={(event) => setHome({ ...home, token: event.target.value })} className="rounded-lg border border-white/10 bg-[#081923] px-3 py-2 text-xs text-white" /></label>
          </div>
          <button disabled={!home.url || !home.token || busy === "home"} onClick={() => void act("home", { action: "home_configure", url: home.url, token: home.token, enabled: true }, "Home Assistant wurde verbunden.")} className="mt-3 flex items-center gap-2 rounded-lg bg-cyan-200 px-3 py-2 text-xs font-medium text-slate-950 disabled:opacity-40"><Home className="h-4 w-4" />Verbinden</button>
        </section>
      </div>

      <section className="mt-5 rounded-xl border border-white/10 bg-black/10 p-4">
        <div className="flex items-center justify-between"><h3 className="flex items-center gap-2 text-sm font-medium text-white/90"><BellRing className="h-4 w-4 text-cyan-200" />Kommunikationsverlauf</h3><span className="text-[10px] text-white/40">{data.events.length} Ereignisse</span></div>
        <div className="mt-3 grid max-h-72 gap-2 overflow-auto">
          {data.events.slice(0, 50).map((event) => <article key={event.id} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-lg border border-white/[0.07] bg-white/[0.025] p-3"><span className={`h-2 w-2 rounded-full ${event.status === "failed" || event.status === "rejected" ? "bg-rose-300" : event.status === "delivered" ? "bg-emerald-300" : "bg-cyan-200"}`} /><span className="min-w-0"><strong className="block truncate text-xs text-white/80">{event.text || event.kind}</strong><small className="block truncate text-[10px] text-white/40">{event.channel} · {event.direction} · {event.sender_id || "M.I.C.A"}</small></span><time className="text-[9px] text-white/35">{new Date(event.created_at).toLocaleString("de-AT")}</time></article>)}
          {!data.events.length ? <div className="py-8 text-center text-xs text-white/35"><CheckCircle2 className="mx-auto mb-2 h-5 w-5" />Noch keine Kommunikation protokolliert.</div> : null}
        </div>
      </section>
    </div>
  );
}
