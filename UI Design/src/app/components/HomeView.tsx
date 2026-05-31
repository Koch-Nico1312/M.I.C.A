import { Activity, Bell, Calendar as CalendarIcon, CheckCircle2, Server } from "lucide-react";

export function HomeView() {
  const events = {
    today: [{ id: 1, title: "Team Meeting", time: "10:00" }, { id: 2, title: "Client Call", time: "14:30" }],
    week: 8,
    month: 24
  };

  return (
    <div className="h-full p-8 overflow-y-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-[#395886] mb-1">Willkommen zurück!</h2>
        <p className="text-sm text-[#8AAEE0]">Hier ist eine Übersicht Ihrer Aktivitäten.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Calendar Summary Widget */}
        <div className="lg:col-span-2 space-y-6">
          <div className="p-6 rounded-2xl backdrop-blur-md bg-white/30 border border-white/40 shadow-sm">
            <div className="flex items-center gap-2 mb-6">
              <CalendarIcon className="w-5 h-5 text-[#638ECB]" />
              <h3 className="font-semibold text-[#395886]">Terminübersicht</h3>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="p-4 rounded-xl bg-white/40 border border-white/20">
                <p className="text-sm text-[#8AAEE0] mb-1">Heute</p>
                <p className="text-2xl font-semibold text-[#395886]">{events.today.length}</p>
              </div>
              <div className="p-4 rounded-xl bg-white/30 border border-white/20">
                <p className="text-sm text-[#8AAEE0] mb-1">Diese Woche</p>
                <p className="text-2xl font-semibold text-[#395886]">{events.week}</p>
              </div>
              <div className="p-4 rounded-xl bg-white/30 border border-white/20">
                <p className="text-sm text-[#8AAEE0] mb-1">Dieser Monat</p>
                <p className="text-2xl font-semibold text-[#395886]">{events.month}</p>
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-medium text-[#395886]">Anstehend für Heute</h4>
              {events.today.map(ev => (
                <div key={ev.id} className="flex items-center justify-between p-3 rounded-lg bg-white/20 hover:bg-white/30 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-[#638ECB]" />
                    <span className="font-medium text-[#395886] text-sm">{ev.title}</span>
                  </div>
                  <span className="text-sm text-[#638ECB]">{ev.time}</span>
                </div>
              ))}
            </div>
          </div>

          {/* System Status Widget */}
          <div className="p-6 rounded-2xl backdrop-blur-md bg-white/30 border border-white/40 shadow-sm flex gap-6 items-center">
             <div className="p-4 rounded-full bg-[#638ECB]/20">
               <Server className="w-8 h-8 text-[#638ECB]" />
             </div>
             <div>
               <h3 className="font-semibold text-[#395886] mb-1">Systemstatus</h3>
               <p className="text-sm text-[#8AAEE0] flex items-center gap-2">
                 <span className="flex w-2 h-2 rounded-full bg-green-500"></span>
                 Alle Systeme laufen normal
               </p>
             </div>
          </div>
        </div>

        {/* Sidebar Column Widgets */}
        <div className="space-y-6">
          
          {/* Notifications / Activity */}
          <div className="p-6 rounded-2xl backdrop-blur-md bg-white/30 border border-white/40 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-[#638ECB]" />
              <h3 className="font-semibold text-[#395886]">Letzte Aktivitäten</h3>
            </div>
            <div className="space-y-4">
              {[1, 2, 3].map((_, i) => (
                <div key={i} className="flex gap-3">
                  <div className="mt-1">
                    <CheckCircle2 className="w-4 h-4 text-[#8AAEE0]" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[#395886]">Dokument analysiert</p>
                    <p className="text-xs text-[#8AAEE0]">vor 2 Stunden</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Info */}
          <div className="p-6 rounded-2xl backdrop-blur-md bg-gradient-to-br from-[#638ECB]/20 to-[#8AAEE0]/10 border border-white/40 shadow-sm relative overflow-hidden">
            <Bell className="absolute -right-4 -top-4 w-24 h-24 text-[#638ECB] opacity-10" />
            <h3 className="font-semibold text-[#395886] mb-2 relative z-10">Tipp des Tages</h3>
            <p className="text-sm text-[#395886]/80 relative z-10">
              Nutzen Sie den "Thinking-Mode" im KI Chat, um komplexere Analysen und Schritt-für-Schritt-Lösungen zu generieren.
            </p>
          </div>

        </div>

      </div>
    </div>
  );
}
