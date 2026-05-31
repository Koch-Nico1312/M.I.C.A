import { useState } from "react";
import { GlassModal } from "./GlassModal";
import { Key, Moon, Sun } from "lucide-react";
import { Input } from "./ui/input";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [apiKey, setApiKey] = useState("");
  const [isDarkMode, setIsDarkMode] = useState(false);

  return (
    <GlassModal isOpen={isOpen} onClose={onClose} title="Einstellungen">
      <div className="space-y-6">
        {/* API Key */}
        <div className="space-y-2">
          <label className="text-sm font-medium flex items-center gap-2">
            <Key className="w-4 h-4 text-[#638ECB]" />
            Gemini API-Key
          </label>
          <Input 
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="AIzaSy..."
            className="backdrop-blur-md bg-white/40 border-white/40 text-[#395886] placeholder:text-[#8AAEE0] focus-visible:ring-[#638ECB]"
          />
        </div>

        {/* Dark Mode Toggle */}
        <div className="flex items-center justify-between p-4 rounded-xl border border-white/30 bg-white/20">
          <div className="flex items-center gap-3">
            <div className="relative w-6 h-6">
              <Sun className={`absolute inset-0 w-6 h-6 text-[#638ECB] transition-transform duration-500 ${isDarkMode ? 'rotate-90 opacity-0' : 'rotate-0 opacity-100'}`} />
              <Moon className={`absolute inset-0 w-6 h-6 text-[#395886] transition-transform duration-500 ${isDarkMode ? 'rotate-0 opacity-100' : '-rotate-90 opacity-0'}`} />
            </div>
            <span className="font-medium">
              {isDarkMode ? 'Dark Mode' : 'Light Mode'}
            </span>
          </div>
          
          <button
            onClick={() => setIsDarkMode(!isDarkMode)}
            className={`relative w-14 h-8 rounded-full transition-colors duration-300 ${isDarkMode ? 'bg-[#395886]' : 'bg-[#D5DEEF]'} border border-white/40 shadow-inner`}
          >
            <div 
              className={`absolute top-1 w-6 h-6 rounded-full bg-white shadow-md transition-transform duration-300 ${isDarkMode ? 'left-7' : 'left-1'}`}
            />
          </button>
        </div>
      </div>
    </GlassModal>
  );
}
