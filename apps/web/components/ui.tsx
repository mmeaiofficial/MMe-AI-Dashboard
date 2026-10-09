import type { ReactNode } from "react";

// The MME logo's letterforms (public/brand/mme-mark.png, cut from the original navy artwork) used as a
// mask, so the logo is drawn in the active theme's solid colors instead of the artwork's navy.
const MARK = { WebkitMaskImage: "url(/brand/mme-mark.png)", maskImage: "url(/brand/mme-mark.png)",
  WebkitMaskSize: "contain", maskSize: "contain", WebkitMaskRepeat: "no-repeat", maskRepeat: "no-repeat",
  WebkitMaskPosition: "center", maskPosition: "center" } as const;

export function LogoMark({ size = 44 }: { size?: number }) {
  return (
    <span role="img" aria-label="MME" className="grid shrink-0 place-items-center rounded-[28%] bg-brand-fill" style={{ width: size, height: size }}>
      <span className="block bg-on-brand" style={{ ...MARK, width: size * 0.78, height: size * 0.78 / 1.847 }} />
    </span>
  );
}

const initials = (name: string) => name.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("");

export function Avatar({ name, src, size = 40, className = "" }: { name: string; src?: string | null; size?: number; className?: string }) {
  const style = { width: size, height: size };
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element -- Google avatars; CSP already allows lh3.googleusercontent.com
    return <img src={src} alt="" referrerPolicy="no-referrer" style={style} className={`shrink-0 rounded-full object-cover ${className}`} />;
  }
  return (
    <span style={{ ...style, fontSize: size * 0.38 }} className={`grid shrink-0 place-items-center rounded-full bg-brand-fill font-semibold text-on-brand ${className}`}>
      {initials(name) || "?"}
    </span>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-ink-soft">{subtitle}</p>}
      </div>
      {actions}
    </header>
  );
}

export function Notice({ children }: { children: ReactNode }) {
  return <p role="status" className="rounded-2xl bg-surface px-4 py-3 text-sm ring-1 ring-border">{children}</p>;
}

/** A simple dialog on a solid backdrop. Closes on Escape and on the backdrop. */
export function Modal({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-canvas p-4" role="dialog" aria-modal="true" aria-label={title}
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={`card w-full space-y-4 ${wide ? "max-w-2xl" : "max-w-md"}`}>
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button className="text-sm text-ink-soft hover:text-ink" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** Small summary tile used at the top of pipeline pages. */
export function Stat({ label, value, strong = false }: { label: string; value: ReactNode; strong?: boolean }) {
  return (
    <div className={`rounded-3xl px-5 py-4 ${strong ? "bg-brand-fill text-on-brand" : "bg-surface ring-1 ring-border"}`}>
      <div className="text-3xl font-medium tabular-nums">{value}</div>
      <div className={`text-xs ${strong ? "text-on-brand" : "text-ink-soft"}`}>{label}</div>
    </div>
  );
}
