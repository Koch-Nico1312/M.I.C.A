import { useEffect, useMemo, useState } from "react";

type Viseme = "rest" | "open" | "wide" | "round" | "closed" | "teeth";

const fallbackSequence: Viseme[] = [
  "closed",
  "open",
  "wide",
  "round",
  "open",
  "teeth",
  "closed",
  "open",
];

function visemeForChar(char: string): Viseme {
  const value = char.toLowerCase();
  if ("bmp".includes(value)) return "closed";
  if ("ouqw".includes(value)) return "round";
  if ("eiy".includes(value)) return "wide";
  if ("fvsztd".includes(value)) return "teeth";
  if ("aähh".includes(value)) return "open";
  if (value.trim() === "") return "closed";
  return "open";
}

function mouthClass(viseme: Viseme) {
  const base =
    "absolute left-1/2 top-[66%] -translate-x-1/2 border border-rose-950/70 bg-[#3a1017] shadow-inner transition-all duration-100";

  switch (viseme) {
    case "open":
      return `${base} h-8 w-14 rounded-[45%]`;
    case "wide":
      return `${base} h-4 w-20 rounded-[55%]`;
    case "round":
      return `${base} h-9 w-9 rounded-full`;
    case "closed":
      return `${base} h-1.5 w-16 rounded-full bg-[#4b1820]`;
    case "teeth":
      return `${base} h-5 w-16 rounded-[45%] bg-[#f5e8dd]`;
    default:
      return `${base} h-2 w-14 rounded-full bg-[#4b1820]`;
  }
}

export function SpeakingFaceAvatar({
  speaking,
  muted,
  status,
  transcript,
  onToggleMute,
}: {
  speaking: boolean;
  muted: boolean;
  status: string;
  transcript?: string;
  onToggleMute: () => void;
}) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!speaking) {
      setTick(0);
      return;
    }

    const timer = window.setInterval(() => {
      setTick((value) => value + 1);
    }, 115);

    return () => window.clearInterval(timer);
  }, [speaking]);

  const visemes = useMemo(() => {
    const cleanText = (transcript ?? "").replace(/\s+/g, " ").trim();
    if (!cleanText) return fallbackSequence;
    return cleanText.split("").map(visemeForChar);
  }, [transcript]);

  const activeViseme = speaking ? visemes[tick % visemes.length] : "rest";
  const gazeOffset = speaking ? Math.sin(tick / 6) * 3 : 0;
  const headTilt = speaking ? Math.sin(tick / 10) * 1.6 : 0;

  return (
    <button
      onClick={onToggleMute}
      className={`group relative flex min-h-[420px] w-full items-center justify-center overflow-hidden rounded-[2rem] border p-6 transition ${
        speaking
          ? "border-cyan-300/40 bg-cyan-300/10 shadow-[0_0_70px_rgba(34,211,238,0.16)]"
          : muted
            ? "border-rose-300/25 bg-rose-300/10"
            : "border-white/10 bg-white/5"
      }`}
      aria-label={muted ? "Mikrofon aktivieren" : "Mikrofon stummschalten"}
    >
      <style>{`
        @keyframes micaBlink {
          0%, 88%, 100% { transform: scaleY(1); }
          91%, 94% { transform: scaleY(0.12); }
        }
        @keyframes micaBreath {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-4px); }
        }
      `}</style>

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_15%,rgba(125,211,252,0.18),transparent_42%),linear-gradient(180deg,rgba(255,255,255,0.06),transparent)]" />

      <div className="relative z-10 flex w-full max-w-[360px] flex-col items-center">
        <div className="mb-4 flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs uppercase tracking-[0.24em] text-slate-300">
          <span className={`h-2 w-2 rounded-full ${speaking ? "bg-cyan-300" : muted ? "bg-rose-300" : "bg-emerald-300"}`} />
          {speaking ? "M.I.C.A spricht" : muted ? "Mic muted" : status}
        </div>

        <div
          className="relative h-[310px] w-[248px]"
          style={{
            animation: "micaBreath 4.8s ease-in-out infinite",
            transform: `rotate(${headTilt}deg)`,
          }}
        >
          <div className="absolute left-1/2 top-2 h-24 w-36 -translate-x-1/2 rounded-t-full bg-[#1b2838]" />
          <div className="absolute left-1/2 top-10 h-[238px] w-[196px] -translate-x-1/2 rounded-[48%_48%_44%_44%] border border-white/15 bg-[linear-gradient(145deg,#d8a989,#b8765f_62%,#8d5248)] shadow-[inset_18px_0_35px_rgba(255,255,255,0.18),inset_-22px_-12px_42px_rgba(49,22,20,0.28),0_30px_80px_rgba(0,0,0,0.38)]" />
          <div className="absolute left-1/2 top-5 h-28 w-[214px] -translate-x-1/2 rounded-[48%_48%_28%_28%] bg-[linear-gradient(180deg,#172334,#26384a)] shadow-[0_18px_22px_rgba(0,0,0,0.22)]" />
          <div className="absolute left-[22px] top-[118px] h-20 w-8 rounded-full bg-[#b8765f]" />
          <div className="absolute right-[22px] top-[118px] h-20 w-8 rounded-full bg-[#9f604f]" />

          <div className="absolute left-1/2 top-[96px] h-[118px] w-[156px] -translate-x-1/2">
            <div className="absolute left-[18px] top-0 h-8 w-12 rounded-full border border-slate-950/20 bg-white/85 shadow-inner">
              <div
                className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#1f2937]"
                style={{
                  transform: `translate(calc(-50% + ${gazeOffset}px), -50%)`,
                  animation: "micaBlink 5.6s infinite",
                }}
              />
            </div>
            <div className="absolute right-[18px] top-0 h-8 w-12 rounded-full border border-slate-950/20 bg-white/85 shadow-inner">
              <div
                className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#1f2937]"
                style={{
                  transform: `translate(calc(-50% + ${gazeOffset}px), -50%)`,
                  animation: "micaBlink 5.6s infinite",
                }}
              />
            </div>

            <div className="absolute left-1/2 top-[48px] h-12 w-7 -translate-x-1/2 rounded-[45%] border-l border-r border-amber-950/25" />
            <div className="absolute left-1/2 top-[87px] h-2 w-9 -translate-x-1/2 rounded-full bg-rose-900/20" />
            <div className={mouthClass(activeViseme)}>
              {activeViseme === "teeth" && (
                <div className="absolute left-1/2 top-1/2 h-px w-12 -translate-x-1/2 bg-rose-950/30" />
              )}
            </div>
          </div>

          <div className="absolute bottom-0 left-1/2 h-16 w-28 -translate-x-1/2 rounded-t-[3rem] bg-[#182433]" />
          <div className="absolute bottom-0 left-1/2 h-12 w-44 -translate-x-1/2 rounded-t-[4rem] bg-[linear-gradient(120deg,#0f766e,#164e63)]" />
        </div>

        <div className="mt-4 grid w-full grid-cols-3 gap-2 text-center text-[11px] uppercase tracking-[0.18em] text-slate-400">
          <div className="rounded-lg border border-white/10 bg-white/5 px-2 py-2">Blink</div>
          <div className="rounded-lg border border-white/10 bg-white/5 px-2 py-2">Mouth</div>
          <div className="rounded-lg border border-white/10 bg-white/5 px-2 py-2">Voice</div>
        </div>
      </div>
    </button>
  );
}
