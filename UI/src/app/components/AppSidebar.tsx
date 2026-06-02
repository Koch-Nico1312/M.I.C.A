import {
  Calendar,
  Cpu,
  HardDrive,
  Home,
  MessageSquareText,
  Mic,
  Settings,
  Sparkles,
  FileText,
  Waves,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  SidebarTrigger,
} from "./ui/sidebar";
import { Calendar as CalendarComponent } from "./ui/calendar";
import { useState } from "react";
import { EventModal } from "./EventModal";
import { SettingsModal } from "./SettingsModal";
import type { DashboardResponse } from "../lib/types";

const menuItems = [
  { title: "Startseite", icon: Home, id: "home" },
  { title: "Sprechen", icon: Mic, id: "voice-chat" },
  { title: "Chats", icon: MessageSquareText, id: "chats" },
  { title: "Dokumente", icon: FileText, id: "documents" },
  { title: "Ressourcen", icon: Waves, id: "resources" },
];

export function AppSidebar({
  activeView,
  onViewChange,
  dashboard,
  onSettingsSaved,
}: {
  activeView: string;
  onViewChange: (view: string) => void;
  dashboard: DashboardResponse | null;
  onSettingsSaved: () => void;
}) {
  const [date, setDate] = useState<Date | undefined>(new Date());
  const [isEventModalOpen, setIsEventModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

  const resources = dashboard?.resources;
  const calendar = dashboard?.calendar;

  const handleDateSelect = (newDate: Date | undefined) => {
    setDate(newDate);
    if (newDate) {
      setIsEventModalOpen(true);
    }
  };

  const resourceRows = [
    {
      label: "CPU",
      value: resources?.cpu_percent ?? 0,
      icon: Cpu,
      tone: "text-cyan-300",
      bar: "bg-cyan-400",
    },
    {
      label: "RAM",
      value: resources?.memory_percent ?? 0,
      icon: HardDrive,
      tone: "text-emerald-300",
      bar: "bg-emerald-400",
    },
    {
      label: "Disk",
      value: resources?.disk_percent ?? 0,
      icon: FileText,
      tone: "text-amber-300",
      bar: "bg-amber-400",
    },
  ];

  return (
    <>
      <Sidebar
        variant="floating"
        className="backdrop-blur-xl flex h-full flex-col"
      >
        <div
          className="relative flex h-full flex-col rounded-2xl border border-white/10 bg-[#06131d]/90 shadow-[0_20px_60px_rgba(0,0,0,0.35)]"
        >
          <SidebarHeader className="p-5 pb-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-3 shadow-[0_0_30px_rgba(34,211,238,0.18)]">
                  <Sparkles className="h-6 w-6 text-cyan-200" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold uppercase tracking-[0.35em] text-white">
                    Jarvis
                  </h2>
                  <p className="text-xs text-slate-400">
                    Voice-first assistant
                  </p>
                </div>
              </div>
              <SidebarTrigger className="rounded-lg border border-white/10 bg-white/5 p-2 text-slate-300 hover:bg-white/10">
                <PanelLeftClose className="h-4 w-4" />
              </SidebarTrigger>
            </div>
          </SidebarHeader>

          <SidebarContent className="flex-1 overflow-y-auto overflow-x-hidden px-2 pb-4">
            <SidebarGroup>
              <SidebarGroupLabel className="px-4 text-slate-400">
                Hauptmenü
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {menuItems.map((item) => (
                    <SidebarMenuItem key={item.id}>
                      <SidebarMenuButton
                        onClick={() => onViewChange(item.id)}
                        isActive={activeView === item.id}
                        className="cursor-pointer rounded-xl transition-all duration-200 hover:bg-white/8 data-[active=true]:bg-cyan-400/15 data-[active=true]:text-cyan-100"
                      >
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>

            <SidebarSeparator className="mx-3 my-4 bg-white/10" />

            <SidebarGroup>
              <SidebarGroupLabel className="px-4 text-slate-400">
                Systemressourcen
              </SidebarGroupLabel>
              <SidebarGroupContent className="space-y-3 px-3">
                {resourceRows.map((row) => (
                  <div
                    key={row.label}
                    className="rounded-2xl border border-white/8 bg-white/5 p-3"
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <row.icon className={`h-4 w-4 ${row.tone}`} />
                        <span className="text-xs uppercase tracking-[0.25em] text-slate-400">
                          {row.label}
                        </span>
                      </div>
                      <span className={`text-sm font-semibold ${row.tone}`}>
                        {row.value.toFixed(1)}%
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-white/10">
                      <div
                        className={`h-2 rounded-full ${row.bar}`}
                        style={{ width: `${Math.min(100, row.value)}%` }}
                      />
                    </div>
                  </div>
                ))}
                <div className="rounded-2xl border border-white/8 bg-white/5 p-3 text-xs text-slate-300">
                  <div className="mb-1 flex items-center justify-between">
                    <span>Threads</span>
                    <span className="text-cyan-200">
                      {resources?.threads ?? 0}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Uptime</span>
                    <span>
                      {Math.floor((resources?.uptime_seconds ?? 0) / 3600)}h
                      {" "}
                      {Math.floor(((resources?.uptime_seconds ?? 0) % 3600) / 60)}m
                    </span>
                  </div>
                </div>
              </SidebarGroupContent>
            </SidebarGroup>

            <SidebarSeparator className="mx-3 my-4 bg-white/10" />

            <SidebarGroup>
              <SidebarGroupLabel className="px-4 text-slate-400">
                <Calendar className="mr-2 h-4 w-4" />
                Kalender
              </SidebarGroupLabel>
              <SidebarGroupContent className="px-3">
                <div className="mb-3 rounded-2xl border border-white/10 bg-white/5 p-3 text-xs text-slate-300">
                  <div className="flex items-center justify-between">
                    <span>Google Calendar</span>
                    <span
                      className={
                        calendar?.authenticated
                          ? "text-emerald-300"
                          : "text-amber-300"
                      }
                    >
                      {calendar?.authenticated ? "Verbunden" : "Nicht verbunden"}
                    </span>
                  </div>
                  <p className="mt-2 text-slate-400">
                    Konfiguration und Verknüpfung laufen über die Einstellungen.
                  </p>
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-2">
                  <CalendarComponent
                    mode="single"
                    selected={date}
                    onSelect={handleDateSelect}
                    weekStartsOn={1}
                    className="rounded-xl bg-transparent text-slate-100 [&_.rdp-day_button]:text-slate-200 [&_.rdp-day_button:hover]:bg-white/10 [&_.rdp-day_button.rdp-day_selected]:bg-cyan-400/20 [&_.rdp-day_button.rdp-day_selected]:text-cyan-100"
                  />
                </div>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>

          <div className="border-t border-white/10 p-4">
            <div className="mb-3 flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-slate-300">
              <span>Voice first</span>
              <span className="text-cyan-200">Default</span>
            </div>
            <button
              onClick={() => setIsSettingsModalOpen(true)}
              className="flex w-full items-center justify-center gap-2 rounded-2xl border border-cyan-400/20 bg-cyan-400/10 px-4 py-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/15"
            >
              <Settings className="h-4 w-4" />
              Einstellungen
            </button>
          </div>
        </div>
      </Sidebar>

      <EventModal
        isOpen={isEventModalOpen}
        onClose={() => setIsEventModalOpen(false)}
        date={date}
      />
      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        onSaved={() => {
          onSettingsSaved();
        }}
      />
    </>
  );
}

