import { useEffect, useRef, useState } from "react";
import {
  Bot,
  Mic2,
  Mic,
  MicOff,
  Radio,
  Send,
  Sparkles,
  MessageSquareText,
  PlusCircle,
  Square,
} from "lucide-react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { ScrollArea } from "./ui/scroll-area";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "./ui/resizable";
import type { DashboardResponse, ChatMessage, VoiceConversationState } from "../lib/types";

type BrowserSpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: any) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

declare global {
  interface Window {
    SpeechRecognition?: new () => BrowserSpeechRecognition;
    webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
  }
}

export function VoiceChatView({
  dashboard,
  onSendCommand,
  onToggleMute,
  onSetVoiceMode,
  onInterruptVoice,
  onStartNewChat,
}: {
  dashboard: DashboardResponse | null;
  onSendCommand: (text: string) => Promise<void>;
  onToggleMute: (muted: boolean) => Promise<void>;
  onSetVoiceMode: (settings: Partial<VoiceConversationState>) => Promise<void>;
  onInterruptVoice: () => Promise<void>;
  onStartNewChat: () => Promise<void>;
}) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [speechHint, setSpeechHint] = useState("");
  const [browserListening, setBrowserListening] = useState(false);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const sentTranscriptRef = useRef("");
  const state = dashboard?.state;
  const messages = dashboard?.current_session?.messages ?? [];
  const muted = Boolean(state?.muted);
  const speaking = Boolean(state?.speaking);
  const currentLabel = state?.state ?? "LISTENING";
  const voice = state?.voice;
  const inputMode = voice?.input_mode ?? "open_mic";
  const pushActive = Boolean(voice?.push_to_talk_active);
  const wakewordEnabled = Boolean(voice?.wakeword_enabled);

  const visibleMessages = messages.slice(-18);
  const latestMicaMessage =
    [...messages].reverse().find((message) => message.role === "assistant")?.content ?? "";
  const lastTranscript = voice?.last_transcript || "";
  const lastResponse = voice?.last_response || latestMicaMessage;

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

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

  const startBrowserTranscription = (mode: "open_mic" | "push_to_talk" = "open_mic") => {
    const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Recognition) {
      setSpeechHint("Browser-STT ist in diesem Browser nicht verfügbar. M.I.C.A bleibt im Open-Mic-Modus.");
      return;
    }

    recognitionRef.current?.stop();
    const recognition = new Recognition();
    recognition.continuous = mode === "open_mic";
    recognition.interimResults = true;
    recognition.lang = "de-DE";
    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results)
        .map((result: any) => result[0]?.transcript ?? "")
        .join(" ")
        .trim();
      if (transcript) setSpeechHint(transcript);

      const finalTranscript = Array.from(event.results)
        .filter((result: any) => Boolean(result.isFinal))
        .map((result: any) => result[0]?.transcript ?? "")
        .join(" ")
        .trim();

      if (finalTranscript && finalTranscript !== sentTranscriptRef.current) {
        sentTranscriptRef.current = finalTranscript;
        onSendCommand(finalTranscript).catch(() => {
          setSpeechHint("Transkript erkannt, aber Senden an M.I.C.A ist fehlgeschlagen.");
        });
      }
    };
    recognition.onerror = () => {
      setBrowserListening(false);
      setSpeechHint("Browser-STT konnte nicht gestartet werden.");
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setBrowserListening(false);
    };
    recognitionRef.current = recognition;
    sentTranscriptRef.current = "";
    setBrowserListening(true);
    recognition.start();
  };

  const startPushToTalk = async () => {
    setSpeechHint("");
    await onSetVoiceMode({ input_mode: "push_to_talk", push_to_talk_active: true });
    startBrowserTranscription("push_to_talk");
  };

  const stopPushToTalk = async () => {
    recognitionRef.current?.stop();
    setBrowserListening(false);
    await onSetVoiceMode({ input_mode: "push_to_talk", push_to_talk_active: false });
  };

  const setMode = async (mode: "open_mic" | "push_to_talk" | "wakeword") => {
    await onSetVoiceMode({
      input_mode: mode,
      push_to_talk_active: mode === "open_mic",
      wakeword_enabled: mode === "wakeword",
    });
    if (mode === "open_mic") {
      startBrowserTranscription("open_mic");
    } else {
      recognitionRef.current?.stop();
      setBrowserListening(false);
    }
  };

  const toggleOpenMic = async () => {
    if (browserListening) {
      recognitionRef.current?.stop();
      setBrowserListening(false);
      return;
    }
    setSpeechHint("");
    await onSetVoiceMode({ input_mode: "open_mic", push_to_talk_active: true, wakeword_enabled: false });
    await onToggleMute(false);
    startBrowserTranscription("open_mic");
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
                M.I.C.A
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
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <div className="min-w-0 flex-1 overflow-hidden p-5 md:p-6">
        <ResizablePanelGroup direction="horizontal" className="min-h-0 gap-4">
          <ResizablePanel id="voice-controls" order={1} defaultSize={45} minSize={28}>
        <section className="h-full min-w-0 overflow-y-auto rounded-[1.5rem] border border-white/10 bg-white/[0.045] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.25)] backdrop-blur-2xl sm:p-6">
          <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.3em] text-slate-300">
                <Mic className="h-4 w-4 text-cyan-200" />
                Voice
              </div>
              <p className="mt-2 max-w-xl text-sm leading-6 text-slate-300">
                Open Mic ist der Standard. Starte den Listener, wenn du direkt mit M.I.C.A sprechen willst.
              </p>
            </div>

            <div className="flex flex-row flex-wrap gap-2 text-left sm:flex-col sm:text-right">
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                {currentLabel}
              </span>
              <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100">
                {browserListening ? "Open mic hört zu" : muted ? "Mic muted" : "Open mic bereit"}
              </span>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <Button
              onClick={toggleOpenMic}
              className={`h-12 rounded-2xl px-5 ${
                browserListening
                  ? "bg-cyan-300 text-slate-950 hover:bg-cyan-200"
                  : "bg-cyan-400/90 text-slate-950 hover:bg-cyan-300"
              }`}
            >
              <Mic2 className="h-4 w-4" />
              {browserListening ? "Zuhören läuft" : "Sprechen starten"}
            </Button>
            <Button
              onClick={onInterruptVoice}
              disabled={!speaking}
              variant="outline"
              className="rounded-2xl border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
            >
              <Square className="h-4 w-4" />
              Antwort stoppen
            </Button>
            <Button
              onClick={() => onToggleMute(!muted)}
              variant="outline"
              className="rounded-2xl border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
            >
              {muted ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
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

          <div className="mt-5 flex flex-wrap gap-2">
            {[
              ["open_mic", "Open mic"],
              ["push_to_talk", "Push-to-talk"],
              ["wakeword", "Wakeword"],
            ].map(([mode, label]) => (
              <Button
                key={mode}
                onClick={() => setMode(mode as "open_mic" | "push_to_talk" | "wakeword")}
                variant="outline"
                className={`rounded-2xl border-white/10 ${
                  inputMode === mode
                    ? "bg-cyan-400/15 text-cyan-100"
                    : "bg-white/5 text-slate-200 hover:bg-white/10"
                }`}
              >
                {mode === "wakeword" ? <Radio className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                {label}
              </Button>
            ))}
          </div>

          {inputMode === "push_to_talk" ? (
            <div className="mt-3">
              <Button
                onPointerDown={startPushToTalk}
                onPointerUp={stopPushToTalk}
                onPointerCancel={stopPushToTalk}
                onPointerLeave={() => {
                  if (pushActive) stopPushToTalk();
                }}
                variant="outline"
                className="rounded-2xl border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
              >
                <Mic2 className="h-4 w-4" />
                {pushActive ? "Push-to-talk aktiv" : "Nur für Push-to-talk gedrückt halten"}
              </Button>
            </div>
          ) : null}

          <div className="mt-5 grid gap-3">
            <div className="rounded-2xl border border-white/10 bg-black/15 p-4">
              <div className="text-xs uppercase tracking-[0.25em] text-slate-400">
                Live-Transkription
              </div>
              <p className="mt-2 min-h-12 text-sm leading-6 text-slate-100">
                {speechHint || lastTranscript || "Open mic ist bereit für deine Stimme."}
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/15 p-4">
              <div className="text-xs uppercase tracking-[0.25em] text-slate-400">
                Antwortstil
              </div>
              <p className="mt-2 min-h-12 text-sm leading-6 text-slate-100">
                {wakewordEnabled
                  ? `Wakeword: ${voice?.wakeword ?? "mica"}`
                  : speaking
                    ? "M.I.C.A spricht gerade und kann gestoppt werden."
                    : lastResponse || "Kontextsensitiv, kurz und direkt."}
              </p>
            </div>
          </div>
        </section>
          </ResizablePanel>
          <ResizableHandle
            withHandle
            className="mica-resize-handle hidden md:flex"
          />

          <ResizablePanel id="voice-transcript" order={2} defaultSize={55} minSize={28}>
        <section className="h-full min-w-0 rounded-[1.5rem] border border-white/10 bg-white/[0.045] p-5 backdrop-blur-2xl">
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
                  Sobald M.I.C.A oder du sprechen, erscheint hier das Transcript.
                </div>
              ) : (
                visibleMessages.map(transcriptMessage)
              )}
            </div>
          </ScrollArea>
        </section>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      <div className="border-t border-white/10 bg-[#051018]/80 p-4 backdrop-blur-xl md:p-5 shrink-0">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="flex-1">
            <Textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Optionaler Textbefehl an M.I.C.A ..."
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
            className="h-[56px] rounded-2xl bg-cyan-400/90 px-6 text-slate-950 hover:bg-cyan-300 sm:h-[64px]"
          >
            <Send className="h-4 w-4" />
            Senden
          </Button>
        </div>
      </div>
    </div>
  );
}

