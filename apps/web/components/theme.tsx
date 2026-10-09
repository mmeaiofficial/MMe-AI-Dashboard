"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { THEME_KEY as KEY } from "@/lib/theme-script";

export type ThemeMode = "light" | "dark" | "system";
const MODES: { mode: ThemeMode; label: string; icon: typeof Sun }[] = [
  { mode: "light", label: "Light", icon: Sun },
  { mode: "dark", label: "Dark", icon: Moon },
  { mode: "system", label: "System", icon: Monitor },
];

// Fallback for when storage is blocked (private windows), so toggles still agree during this visit.
let current: ThemeMode = "system";

function read(): ThemeMode {
  try { const m = localStorage.getItem(KEY); return m === "light" || m === "dark" ? m : "system"; } catch { return current; }
}

function apply(mode: ThemeMode) {
  const dark = mode === "dark" || (mode === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

const EVENT = "mme-theme-change";

export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>("system");
  useEffect(() => {
    // Every mounted toggle (desktop and mobile) follows the same choice.
    const sync = () => setMode(read());
    sync();
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, []);
  useEffect(() => {
    apply(mode);
    if (mode !== "system") return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const on = () => apply("system");
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [mode]);
  const set = (m: ThemeMode) => {
    setMode(m);
    current = m;
    try { localStorage.setItem(KEY, m); } catch { /* private mode: still applies for this visit */ }
    window.dispatchEvent(new Event(EVENT));
  };
  return { mode, set };
}

/** Segmented Light / Dark / System control. `compact` cycles through the modes with one button. */
export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { mode, set } = useTheme();
  if (compact) {
    const i = MODES.findIndex((m) => m.mode === mode);
    const cur = MODES[i], next = MODES[(i + 1) % MODES.length];
    const Icon = cur.icon;
    return (
      <button className="btn-icon" onClick={() => set(next.mode)} aria-label={`Theme: ${cur.label}. Switch to ${next.label}`} title={`Theme: ${cur.label}`}>
        <Icon size={16} />
      </button>
    );
  }
  return (
    <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 gap-1 rounded-full bg-canvas p-1">
      {MODES.map(({ mode: m, label, icon: Icon }) => (
        <button key={m} role="radio" aria-checked={mode === m} onClick={() => set(m)} title={label}
          className={`flex items-center justify-center gap-1.5 rounded-full py-1.5 text-xs transition ${mode === m ? "bg-surface font-medium text-ink ring-1 ring-border" : "text-ink-soft hover:text-ink"}`}>
          <Icon size={14} aria-hidden="true" />{label}
        </button>
      ))}
    </div>
  );
}
