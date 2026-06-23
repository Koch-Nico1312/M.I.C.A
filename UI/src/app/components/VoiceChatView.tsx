import { useState } from "react";
import {
  Bot,
  Mic,
  MicOff,
  Send,
  Sparkles,
  MessageSquareText,
  PlusCircle,
} from "lucide-react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { ScrollArea } from "./ui/scroll-area";
import type { DashboardResponse, ChatMessage } from "../lib/types";

export function VoiceChatView({
  dashboard,
  onSendCommand,
  onToggleMute,
  onStartNewChat,
}: {
  dashboard: DashboardResponse | null;
  onSendCommand: (text: string) => Promise<void>;
  onToggleMute: (muted: boolean) => Promise<void>;
  onStartNewChat: () => Promise<void>;
}) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const state = dashboard?.state;
  const messages = dashboard?.current_session?.messages ?? [];
  const muted = Boolean(state?.muted);
  const speaking = Boolean(state?.speaking);
  const currentLabel = state?.state ?? "LISTENING";

  const visibleMessages = messages.slice(-18);

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

  const transcriptMessage = (message: ChatMessage) => {
    const isUser = message.role === "user";
    const isTool = message.role === "tool";

    return (
      <div
        key={message.id}
        className={`flex ${isUser ? "justify-end" : "justify-start"}`}
      >
        <div
          className={`max-w-[90%] rounded-[1.5rem] border px-4 py-3 shadow-lg ${
            isUser
              ? "border-cyan-400/20 bg-cyan-400/10 text-cyan-50"
              : isTool
              ? "border-amber-400/20 bg-amber-400/10 text-amber-50"
              : "border-white/10 bg-white/5 text-slate-100"
          }`}
        >
          <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.25em] text-slate-400">
            {isUser ? (
              <>
                <MessageSquareText className="h-3.5 w-3.5" />
                You
              </>
            ) : isTool ? (
              <>
                <Sparkles className="h-3.5 w-3.5" />
                Tool
              </>
            ) : (
              <>
                <Bot className="h-3.5 w-3.5" />
                Jarvis
              </>
            )}
          </div>
          <p className="whitespace-pre-wrap text-sm leading-6">
            {message.content}
          </p>
          <div className="mt-2 text-[11px] uppercase tracking-[0.25em] text-slate-500">
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="grid flex-1 gap-4 overflow-y-auto p-5 md:grid-cols-[1.2fr_1fr] md:p-6">
        <section className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(0,212,255,0.12),rgba(255,255,255,0.04))] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.25)]">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.3em] text-slate-300">
                <Mic className="h-4 w-4 text-cyan-200" />
                Speaking first
              </div>
              <h2 className="text-3xl font-semibold tracking-tight text-white">
                Sprachmodus aktiv.
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                Das Gespräch bleibt aktiv, auch wenn du die Sidebar wechselst.
                Der aktuelle Verlauf wird als Transcript unten live mitgeführt.
              </p>
            </div>

            <div className="flex flex-col gap-2 text-right">
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                {currentLabel}
              </span>
              <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100">
                {muted ? "Mic muted" : "Mic active"}
              </span>
            </div>
          </div>

          <div className="mt-8 flex items-center justify-center">
            <button
              onClick={() => onToggleMute(!muted)}
              className={`relative flex h-56 w-56 items-center justify-center rounded-full border ${
                speaking
                  ? "border-cyan-300/50 bg-cyan-400/15 shadow-[0_0_60px_rgba(34,211,238,0.25)]"
                  : muted
                  ? "border-rose-400/30 bg-rose-400/10"
                  : "border-white/10 bg-white/5 shadow-[0_0_40px_rgba(255,255,255,0.08)]"
              }`}
            >
              <div
                className={`absolute inset-4 rounded-full border ${
                  speaking ? "border-cyan-300/40" : "border-white/10"
                }`}
              />
              <div
                className={`absolute inset-8 rounded-full border ${
                  speaking ? "border-cyan-300/20" : "border-white/10"
                }`}
              />
              {speaking ? (
                <Sparkles className="h-16 w-16 text-cyan-100" />
              ) : muted ? (
                <MicOff className="h-16 w-16 text-rose-200" />
              ) : (
                <Mic className="h-16 w-16 text-cyan-100" />
              )}
            </button>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <Button
              onClick={() => onToggleMute(!muted)}
              variant="outline"
              className="rounded-2xl border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
            >
              {muted ? "Mikrofon aktivieren" : "Mikrofon stummschalten"}
            </Button>
            <Button
              onClick={onStartNewChat}
              variant="outline"
              className="rounded-2xl border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
            >
              <PlusCircle className="h-4 w-4" />
              Neuen Chat starten
            </Button>
          </div>
        </section>

        <section className="rounded-[2rem] border border-white/10 bg-white/5 p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="text-sm uppercase tracking-[0.3em] text-slate-400">
                Transcript
              </div>
              <h3 className="mt-1 text-xl font-semibold text-white">
                Laufendes Gespräch
              </h3>
            </div>
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
              {visibleMessages.length} messages
            </div>
          </div>

          <ScrollArea className="h-[400px] pr-3">
            <div className="space-y-3 pr-1">
              {visibleMessages.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-5 text-sm text-slate-400">
                  Sobald JARVIS oder du sprechen, erscheint hier das Transcript.
                </div>
              ) : (
                visibleMessages.map(transcriptMessage)
              )}
            </div>
          </ScrollArea>
        </section>
      </div>

      <div className="border-t border-white/10 bg-[#051018]/80 p-4 backdrop-blur-xl md:p-5 shrink-0">
        <div className="flex gap-3">
          <div className="flex-1">
            <Textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Optionaler Textbefehl an JARVIS ..."
              className="min-h-[64px] rounded-2xl border-white/10 bg-white/5 px-4 py-3 text-slate-100 placeholder:text-slate-500 focus-visible:ring-cyan-400/40"
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
            />
          </div>

          <Button
            onClick={handleSend}
            disabled={sending}
            className="h-[64px] rounded-2xl bg-cyan-400/90 px-6 text-slate-950 hover:bg-cyan-300"
          >
            <Send className="h-4 w-4" />
            Senden
          </Button>
        </div>
      </div>
    </div>
  );
}

