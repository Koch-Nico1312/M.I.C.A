import { useState, useRef, useEffect } from "react";
import { Send, Sparkles, ChevronUp, BrainCircuit, Paperclip, Image as ImageIcon } from "lucide-react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { ScrollArea } from "./ui/scroll-area";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export function AIChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: "Hallo! Ich bin M.I.C.A. Wie kann ich dir heute helfen?",
    },
  ]);
  const [input, setInput] = useState("");
  const [showOptions, setShowOptions] = useState(false);
  const [selectedMode, setSelectedMode] = useState("Standard");
  const optionsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (optionsRef.current && !optionsRef.current.contains(event.target as Node)) {
        setShowOptions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSend = () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Ich habe deine Nachricht erhalten (Modus: ${selectedMode}) und verarbeite sie...`,
      };
      setMessages((prev) => [...prev, aiMessage]);
    }, 500);
  };

  const handleModeSelect = (mode: string) => {
    setSelectedMode(mode);
    setShowOptions(false);
  };

  return (
    <div className="flex flex-col h-full relative">
      <ScrollArea className="flex-1 p-6">
        <div className="space-y-4 max-w-3xl mx-auto pb-6">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl p-4 backdrop-blur-md border ${
                  message.role === "user"
                    ? "bg-[#638ECB]/20 border-[#638ECB]/30 text-[#395886]"
                    : "bg-white/30 border-white/40 text-[#395886]"
                }`}
                style={{
                  boxShadow: "0 8px 32px rgba(99, 142, 203, 0.1)",
                }}
              >
                {message.role === "assistant" && (
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4 text-[#638ECB]" />
                    <span className="text-xs font-medium text-[#638ECB]">AI Assistent</span>
                  </div>
                )}
                <p className="text-sm leading-relaxed">{message.content}</p>
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>

      <div className="border-t border-white/20 p-4 backdrop-blur-md bg-white/20 relative z-20">
        <div className="max-w-3xl mx-auto relative flex gap-3 items-end">
          
          <div className="relative flex-1" ref={optionsRef}>
            {/* Context Menu Popup */}
            {showOptions && (
              <div className="absolute bottom-full mb-3 left-0 w-64 p-2 rounded-xl backdrop-blur-xl bg-white/60 border border-white/50 shadow-xl animate-in slide-in-from-bottom-2">
                <div className="text-xs font-semibold text-[#8AAEE0] mb-2 px-2 uppercase tracking-wider">Aktionen & Modi</div>
                <div className="space-y-1">
                  <button 
                    onClick={() => handleModeSelect("Thinking-Mode")}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/50 text-[#395886] transition-colors text-sm text-left"
                  >
                    <BrainCircuit className="w-4 h-4 text-[#638ECB]" />
                    <div>
                      <div className="font-medium">Thinking-Mode</div>
                      <div className="text-xs text-[#8AAEE0]">Tiefgründige Analyse</div>
                    </div>
                  </button>
                  <button 
                    onClick={() => handleModeSelect("Datei Upload")}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/50 text-[#395886] transition-colors text-sm text-left"
                  >
                    <Paperclip className="w-4 h-4 text-[#638ECB]" />
                    <div>
                      <div className="font-medium">Datei Upload</div>
                    <div className="text-xs text-[#8AAEE0]">Dokumente analysieren</div>
                    </div>
                  </button>
                  <button 
                    onClick={() => handleModeSelect("Bild generieren")}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/50 text-[#395886] transition-colors text-sm text-left"
                  >
                    <ImageIcon className="w-4 h-4 text-[#638ECB]" />
                    <div>
                      <div className="font-medium">Bild generieren</div>
                    <div className="text-xs text-[#8AAEE0]">KI-Bilder erstellen</div>
                    </div>
                  </button>
                </div>
              </div>
            )}

            <div className="relative bg-white/40 backdrop-blur-md rounded-2xl border border-white/40 flex items-end">
              <button
                onClick={() => setShowOptions(!showOptions)}
                className="p-3 ml-1 mb-1 rounded-xl hover:bg-white/40 text-[#638ECB] transition-colors flex items-center justify-center"
              >
                <ChevronUp className={`w-5 h-5 transition-transform duration-200 ${showOptions ? 'rotate-180' : ''}`} />
              </button>
              
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder={`Anweisung an M.I.C.A (${selectedMode})...`}
                className="min-h-[60px] py-4 bg-transparent border-0 resize-none text-[#395886] placeholder:text-[#8AAEE0] focus-visible:ring-0 px-2"
              />
            </div>
          </div>

          <Button
            onClick={handleSend}
            size="icon"
            className="h-[60px] w-[60px] shrink-0 rounded-2xl backdrop-blur-md bg-[#638ECB]/80 hover:bg-[#638ECB] border border-white/40 shadow-sm transition-all"
            style={{
              boxShadow: "0 8px 32px rgba(99, 142, 203, 0.2)",
            }}
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
