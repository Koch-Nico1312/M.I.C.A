import { useState } from "react";
import { GlassModal } from "./GlassModal";
import { Plus, Clock, MapPin } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";

interface EventModalProps {
  isOpen: boolean;
  onClose: () => void;
  date: Date | undefined;
}

export function EventModal({ isOpen, onClose, date }: EventModalProps) {
  const [events, setEvents] = useState([
    { id: 1, title: "Team Meeting", time: "10:00 - 11:30", location: "Online" },
    { id: 2, title: "Projekt Review", time: "14:00 - 15:00", location: "Raum 3.1" },
  ]);
  const [newEventTitle, setNewEventTitle] = useState("");

  const formattedDate = date ? new Intl.DateTimeFormat('de-DE', { 
    weekday: 'long', 
    day: 'numeric', 
    month: 'long', 
    year: 'numeric' 
  }).format(date) : "";

  const handleAddEvent = () => {
    if (!newEventTitle.trim()) return;
    setEvents([...events, {
      id: Date.now(),
      title: newEventTitle,
      time: "Ganztägig",
      location: "Neu"
    }]);
    setNewEventTitle("");
  };

  return (
    <GlassModal isOpen={isOpen} onClose={onClose} title={`Termine: ${formattedDate}`}>
      <div className="space-y-4">
        {/* Events List */}
        <ScrollArea className="h-[200px] pr-3 -mr-3">
          <div className="space-y-3">
            {events.length > 0 ? events.map((event) => (
              <div 
                key={event.id}
                className="p-3 rounded-xl border border-white/30 bg-white/30 backdrop-blur-md flex flex-col gap-1"
              >
                <span className="font-semibold">{event.title}</span>
                <div className="flex items-center gap-4 text-xs text-[#638ECB]">
                  <div className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {event.time}
                  </div>
                  <div className="flex items-center gap-1">
                    <MapPin className="w-3 h-3" />
                    {event.location}
                  </div>
                </div>
              </div>
            )) : (
              <div className="text-center py-8 text-[#8AAEE0]">
                Keine Termine an diesem Tag.
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Add Event Form */}
        <div className="flex gap-2 pt-2 mt-4 border-t border-white/20">
          <Input 
            value={newEventTitle}
            onChange={(e) => setNewEventTitle(e.target.value)}
            placeholder="Neuer Termin..."
            className="backdrop-blur-md bg-white/40 border-white/40 text-[#395886] placeholder:text-[#8AAEE0]"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAddEvent();
            }}
          />
          <Button 
            onClick={handleAddEvent}
            size="icon"
            className="bg-[#638ECB]/80 hover:bg-[#638ECB] text-white border border-white/40 shadow-sm"
          >
            <Plus className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </GlassModal>
  );
}
