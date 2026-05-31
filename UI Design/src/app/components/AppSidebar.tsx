import {
  Calendar,
  Home,
  MessageSquare,
  Settings,
  Sparkles,
  FileText,
  BarChart3,
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
  SidebarFooter,
} from "./ui/sidebar";
import { Calendar as CalendarComponent } from "./ui/calendar";
import { useState } from "react";
import { EventModal } from "./EventModal";
import { SettingsModal } from "./SettingsModal";

const menuItems = [
  { title: "Startseite", icon: Home, id: "home" },
  { title: "KI Chat", icon: MessageSquare, id: "chat" },
  { title: "Dokumente", icon: FileText, id: "documents" },
  { title: "Analysen", icon: BarChart3, id: "analytics" },
];

export function AppSidebar({ activeView, onViewChange }: { activeView: string, onViewChange: (view: string) => void }) {
  const [date, setDate] = useState<Date | undefined>(new Date());
  const [isEventModalOpen, setIsEventModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

  const handleDateSelect = (newDate: Date | undefined) => {
    setDate(newDate);
    if (newDate) {
      setIsEventModalOpen(true);
    }
  };

  return (
    <>
      <Sidebar variant="floating" className="backdrop-blur-xl flex flex-col h-full">
        <div
          className="h-full rounded-xl border border-white/30 flex flex-col relative"
          style={{
            background: "rgba(255, 255, 255, 0.25)",
            boxShadow: "0 8px 32px rgba(99, 142, 203, 0.15)",
          }}
        >
          <SidebarHeader className="p-6">
            <div className="flex items-center gap-3">
              <div
                className="p-2 rounded-xl backdrop-blur-md bg-[#638ECB]/20 border border-white/40"
                style={{
                  boxShadow: "0 4px 16px rgba(99, 142, 203, 0.2)",
                }}
              >
                <Sparkles className="w-6 h-6 text-[#638ECB]" />
              </div>
              <div>
                <h2 className="font-semibold text-[#395886]">KI Assistent</h2>
                <p className="text-xs text-[#8AAEE0]">Ihr digitaler Begleiter</p>
              </div>
            </div>
          </SidebarHeader>

          <SidebarContent className="flex-1 overflow-y-auto overflow-x-hidden">
            <SidebarGroup>
              <SidebarGroupLabel className="text-[#638ECB] px-4">Hauptmenü</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {menuItems.map((item) => (
                    <SidebarMenuItem key={item.id}>
                      <SidebarMenuButton
                        onClick={() => onViewChange(item.id)}
                        isActive={activeView === item.id}
                        className="hover:bg-white/40 data-[active=true]:bg-[#638ECB]/20 data-[active=true]:text-[#395886] transition-all duration-200 cursor-pointer"
                      >
                        <item.icon className="w-4 h-4" />
                        <span>{item.title}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>

            <SidebarSeparator className="bg-white/30 mx-4" />

            <SidebarGroup>
              <SidebarGroupLabel className="text-[#638ECB] px-4">
                <Calendar className="w-4 h-4 mr-2" />
                Kalender
              </SidebarGroupLabel>
              <SidebarGroupContent className="px-2">
                <div
                  className="rounded-xl p-2 backdrop-blur-md bg-white/20 border border-white/30"
                  style={{
                    boxShadow: "0 4px 16px rgba(99, 142, 203, 0.1)",
                  }}
                >
                  <CalendarComponent
                    mode="single"
                    selected={date}
                    onSelect={handleDateSelect}
                    className="rounded-lg [&_.rdp-day_button]:text-[#395886] [&_.rdp-day_button.rdp-day_selected]:bg-[#638ECB]/30 [&_.rdp-day_button.rdp-day_selected]:text-[#395886] [&_.rdp-day_button:hover]:bg-white/40"
                  />
                </div>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>

          {/* Settings gear at bottom right */}
          <div className="absolute bottom-4 right-4 z-20">
            <button
              onClick={() => setIsSettingsModalOpen(true)}
              className="p-3 rounded-full backdrop-blur-md bg-white/40 border border-white/40 text-[#638ECB] hover:bg-white/60 hover:scale-110 transition-all duration-200 shadow-md"
              title="Einstellungen"
            >
              <Settings className="w-5 h-5" />
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
      />
    </>
  );
}
