import { SidebarProvider, SidebarTrigger, SidebarInset } from "./components/ui/sidebar";
import { AppSidebar } from "./components/AppSidebar";
import { AIChat } from "./components/AIChat";
import { DocumentsView } from "./components/DocumentsView";
import { HomeView } from "./components/HomeView";
import { Sparkles } from "lucide-react";
import { useState } from "react";

export default function App() {
  const [activeView, setActiveView] = useState("home");

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex min-h-screen w-full">
        <AppSidebar activeView={activeView} onViewChange={setActiveView} />
        <SidebarInset className="flex-1">
          <div className="flex flex-col h-screen">
            <header
              className="sticky top-0 z-10 border-b border-white/20 backdrop-blur-xl p-4"
              style={{
                background: "rgba(255, 255, 255, 0.3)",
                boxShadow: "0 4px 24px rgba(99, 142, 203, 0.1)",
              }}
            >
              <div className="flex items-center gap-4">
                <SidebarTrigger className="text-[#638ECB] hover:bg-white/40" />
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-[#638ECB]" />
                  <h1 className="font-semibold text-[#395886]">
                    {activeView === "home" && "Dashboard"}
                    {activeView === "chat" && "KI Chat"}
                    {activeView === "documents" && "Dokumente"}
                    {activeView === "analytics" && "Analysen"}
                  </h1>
                </div>
              </div>
            </header>

            <main className="flex-1 overflow-hidden">
              <div
                className="h-full m-4 rounded-2xl border border-white/30 overflow-hidden"
                style={{
                  background: "rgba(255, 255, 255, 0.25)",
                  boxShadow: "0 8px 32px rgba(99, 142, 203, 0.15)",
                }}
              >
                {activeView === "home" && <HomeView />}
                {activeView === "chat" && <AIChat />}
                {activeView === "documents" && <DocumentsView />}
                {activeView === "analytics" && (
                  <div className="flex items-center justify-center h-full text-[#8AAEE0]">
                    Analysen-Bereich in Entwicklung...
                  </div>
                )}
              </div>
            </main>
          </div>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}