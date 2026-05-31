import { X } from "lucide-react";
import { ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface GlassModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export function GlassModal({ isOpen, onClose, title, children }: GlassModalProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-[#395886]/20 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div 
        className="relative w-full max-w-md p-6 rounded-2xl border border-white/40 shadow-2xl z-10 animate-in fade-in zoom-in duration-200"
        style={{
          background: "rgba(255, 255, 255, 0.4)",
          backdropFilter: "blur(20px)",
          boxShadow: "0 16px 40px rgba(99, 142, 203, 0.2)",
        }}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-[#395886]">{title}</h2>
          <button 
            onClick={onClose}
            className="p-2 rounded-full hover:bg-white/40 text-[#638ECB] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="text-[#395886]">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
