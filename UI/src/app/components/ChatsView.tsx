import { memo, useEffect, useMemo, useState } from "react";
import {
  Bot,
  ChevronRight,
  Clock3,
  History,
  MessageSquareText,
  PlusCircle,
  RefreshCw,
  Search,
} from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";
import { micaApi } from "../lib/api";
import type { ChatSession, DashboardResponse } from "../lib/types";

const SESSION_RENDER_LIMIT = 80;
const TRANSCRIPT_RENDER_LIMIT = 200;

export const ChatsView = memo(function ChatsView({
  dashboard,
  selectedChatId,
  onSelectChat,
  onStartNewChat,
  onRefresh,
}: {
  dashboard: DashboardResponse | null;
  selectedChatId: string | null;
  onSelectChat: (id: string) => void;
  onStartNewChat: () => Promise<void>;
  onRefresh: () => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [loadingSession, setLoadingSession] = useState(false);

  const sessions = dashboard?.recent_sessions ?? [];
  const currentSessionId = dashboard?.current_session?.id ?? null;

  useEffect(() => {
    const fetchSession = async () => {
      const id = selectedChatId ?? currentSessionId;
      if (!id) {
        setSelectedSession(null);
        return;
      }

      if (dashboard?.current_session?.id === id && dashboard.current_session) {
        setSelectedSession(dashboard.current_session);
        return;
      }

      const local = sessions.find((session) => session.id === id);
      if (local?.messages) {
        setSelectedSession(local);
        return;
      }

      setLoadingSession(true);
      try {
        const response = await micaApi.getChatSession(id);
        setSelectedSession(response.session);
      } finally {
        setLoadingSession(false);
      }
    };

    fetchSession();
  }, [selectedChatId, currentSessionId, dashboard, sessions]);

  const filteredSessions = useMemo(() => sessions.filter((session) => {
    if (!search.trim()) return true;
    const query = search.toLowerCase();
    return (
      session.title.toLowerCase().includes(query) ||
      (session.preview ?? "").toLowerCase().includes(query)
    );
  }), [search, sessions]);
  const visibleSessions = useMemo(
    () => filteredSessions.slice(0, SESSION_RENDER_LIMIT),
    [filteredSessions],
  );

  const transcript = selectedSession?.messages ?? [];
  const visibleTranscript = useMemo(
    () => transcript.slice(-TRANSCRIPT_RENDER_LIMIT),
    [transcript],
  );
  const hiddenTranscriptCount = Math.max(0, transcript.length - visibleTranscript.length);

  const formatDate = (value?: string | null) => {
    if (!value) return "";
    return new Date(value).toLocaleString([], {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="grid h-full gap-4 p-5 md:grid-cols-[320px_1fr] md:p-6">
      <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/5">
        <div className="border-b border-white/10 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm uppercase tracking-[0.3em] text-slate-400">
                <History className="h-4 w-4" />
                Chats
              </div>
              <h2 className="mt-1 text-2xl font-semibold text-white">
                Alte Gespräche
              </h2>
            </div>
            <Button
              onClick={onStartNewChat}
              size="icon"
              className="rounded-2xl bg-cyan-400/90 text-slate-950 hover:bg-cyan-300"
              title="Neuen Chat starten"
            >
              <PlusCircle className="h-4 w-4" />
            </Button>
          </div>

          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Chats durchsuchen..."
              className="border-white/10 bg-white/5 pl-9 text-slate-100 placeholder:text-slate-500"
            />
          </div>
        </div>

        <ScrollArea className="h-[calc(100%-121px)]">
          <div className="space-y-2 p-3">
            {filteredSessions.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
                Keine passenden Chats gefunden.
              </div>
            ) : (
              visibleSessions.map((session) => {
                const active = session.id === (selectedChatId ?? currentSessionId);
                return (
                  <button
                    key={session.id}
                    onClick={() => onSelectChat(session.id)}
                    className={`w-full rounded-2xl border p-4 text-left transition ${
                      active
                        ? "border-cyan-400/30 bg-cyan-400/10"
                        : "border-white/10 bg-white/5 hover:bg-white/8"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-white">
                          {session.title}
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-xs uppercase tracking-[0.25em] text-slate-400">
                          <Clock3 className="h-3.5 w-3.5" />
                          {formatDate(session.updated_at)}
                        </div>
                      </div>
                      <ChevronRight className="mt-1 h-4 w-4 text-slate-500" />
                    </div>

                    <p className="mt-3 line-clamp-2 text-sm leading-6 text-slate-300">
                      {session.preview ?? "No preview available."}
                    </p>

                    <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                      <span>{session.message_count ?? 0} messages</span>
                      <span
                        className={
                          session.status === "active"
                            ? "text-cyan-200"
                            : "text-slate-400"
                        }
                      >
                        {session.status ?? "archived"}
                      </span>
                    </div>
                  </button>
                );
              })
            )}
            {filteredSessions.length > visibleSessions.length ? (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-xs text-slate-400">
                {filteredSessions.length - visibleSessions.length} weitere Chats ausgeblendet. Suche nutzen, um enger zu filtern.
              </div>
            ) : null}
          </div>
        </ScrollArea>
      </section>

      <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/5">
        <div className="border-b border-white/10 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-sm uppercase tracking-[0.3em] text-slate-400">
                <MessageSquareText className="h-4 w-4" />
                Transcript
              </div>
              <h3 className="mt-1 text-2xl font-semibold text-white">
                {selectedSession?.title ?? "Wähle einen Chat"}
              </h3>
              <p className="mt-2 text-sm text-slate-400">
                {selectedSession?.summary ??
                  "Hier erscheinen die gesprochenen Zeilen und Aktionen des ausgewählten Chats."}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button
                onClick={onRefresh}
                variant="outline"
                className="rounded-2xl border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
              >
                <RefreshCw className="h-4 w-4" />
                Aktualisieren
              </Button>
              <Button
                onClick={onStartNewChat}
                className="rounded-2xl bg-cyan-400/90 text-slate-950 hover:bg-cyan-300"
              >
                Neuen Chat
              </Button>
            </div>
          </div>
        </div>

        <ScrollArea className="h-[calc(100%-172px)]">
          <div className="space-y-4 p-5">
            {loadingSession ? (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 text-sm text-slate-400">
                Laden...
              </div>
            ) : transcript.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 text-sm text-slate-400">
                Noch kein Transcript verfügbar.
              </div>
            ) : (
              <>
              {hiddenTranscriptCount ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-xs text-slate-400">
                  {hiddenTranscriptCount} ältere Nachrichten ausgeblendet, damit der Transcript flüssig bleibt.
                </div>
              ) : null}
              {visibleTranscript.map((message) => {
                const isUser = message.role === "user";
                const isTool = message.role === "tool";
                return (
                  <div
                    key={message.id}
                    className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[92%] rounded-[1.5rem] border px-4 py-3 ${
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
                            <Bot className="h-3.5 w-3.5" />
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
                        {formatDate(message.timestamp)}
                      </div>
                    </div>
                  </div>
                );
              })}
              </>
            )}
          </div>
        </ScrollArea>
      </section>
    </div>
  );
});
