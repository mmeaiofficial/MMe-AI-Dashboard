"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export interface DayPoint { day: Date; signIns: number; changes: number; }

const SERIES = [
  { key: "signIns", label: "Sign-ins and MFA", color: "rgb(var(--series-1))", dash: undefined },
  { key: "changes", label: "Access and org changes", color: "rgb(var(--series-2))", dash: "6 4" },
] as const;

const H = 240;
const PAD = { top: 16, right: 12, bottom: 28, left: 32 };
const dayFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });
const longFmt = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" });

// Monotone cubic (Fritsch–Carlson): smooth like the reference design, but never overshoots below zero.
function smoothPath(pts: [number, number][]): string {
  const n = pts.length;
  if (n === 0) return "";
  if (n === 1) return `M${pts[0][0]},${pts[0][1]}`;
  const dx = pts.slice(1).map((p, i) => p[0] - pts[i][0]);
  const sl = pts.slice(1).map((p, i) => (p[1] - pts[i][1]) / dx[i]);
  const m = pts.map((_, i) => (i === 0 ? sl[0] : i === n - 1 ? sl[n - 2] : sl[i - 1] * sl[i] <= 0 ? 0 : (sl[i - 1] + sl[i]) / 2));
  for (let i = 0; i < n - 1; i++) {
    if (sl[i] === 0) { m[i] = 0; m[i + 1] = 0; continue; }
    const a = m[i] / sl[i], b = m[i + 1] / sl[i], h = a * a + b * b;
    if (h > 9) { const t = 3 / Math.sqrt(h); m[i] = t * a * sl[i]; m[i + 1] = t * b * sl[i]; }
  }
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], k = dx[i] / 3;
    d += ` C${x0 + k},${y0 + m[i] * k} ${x1 - k},${y1 - m[i + 1] * k} ${x1},${y1}`;
  }
  return d;
}

function Swatch({ s }: { s: (typeof SERIES)[number] }) {
  return (
    <svg width="18" height="8" aria-hidden="true" className="shrink-0">
      <line x1="1" x2="17" y1="4" y2="4" style={{ stroke: s.color }} strokeWidth={3} strokeLinecap="round" strokeDasharray={s.dash ? "4 3" : undefined} />
    </svg>
  );
}

export function ActivityChart({ data, aside }: { data: DayPoint[]; aside?: React.ReactNode }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(640);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const geo = useMemo(() => {
    const max = Math.max(4, ...data.flatMap((d) => [d.signIns, d.changes]));
    const top = Math.ceil(max / 4) * 4;
    const iw = w - PAD.left - PAD.right, ih = H - PAD.top - PAD.bottom;
    const x = (i: number) => PAD.left + (data.length <= 1 ? iw / 2 : (i * iw) / (data.length - 1));
    const y = (v: number) => PAD.top + ih - (v / top) * ih;
    const lines = SERIES.map((s) => smoothPath(data.map((d, i) => [x(i), y(d[s.key])])));
    const ticks = [0, top / 2, top];
    const labelEvery = Math.max(1, Math.ceil(data.length / Math.max(2, Math.floor(iw / 72))));
    return { x, y, lines, ticks, labelEvery, iw, ih };
  }, [data, w]);

  const pick = (clientX: number) => {
    const r = wrap.current?.getBoundingClientRect();
    if (!r || data.length === 0) return;
    const rel = (clientX - r.left - PAD.left) / geo.iw;
    setHover(Math.min(data.length - 1, Math.max(0, Math.round(rel * (data.length - 1)))));
  };

  const h = hover !== null ? data[hover] : null;
  const tipLeft = hover !== null ? Math.min(Math.max(geo.x(hover), 90), w - 90) : 0;

  return (
    <div>
      <div ref={wrap} className="relative select-none"
        onPointerMove={(e) => pick(e.clientX)} onPointerLeave={() => setHover(null)}>
        <svg width={w} height={H} role="img" aria-label="Audit activity per day" tabIndex={0} className="block outline-none focus-visible:rounded-xl focus-visible:ring-2 focus-visible:ring-brand"
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") setHover((i) => Math.min(data.length - 1, (i ?? -1) + 1));
            else if (e.key === "ArrowLeft") setHover((i) => Math.max(0, (i ?? data.length) - 1));
            else if (e.key === "Escape") setHover(null);
          }}
          onBlur={() => setHover(null)}>
          {geo.ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={w - PAD.right} y1={geo.y(t)} y2={geo.y(t)} className={t === 0 ? "stroke-ink-faint" : "stroke-border"} />
              <text x={PAD.left - 10} y={geo.y(t)} dy="0.32em" textAnchor="end" className="fill-ink-faint text-[11px] tabular-nums">{t}</text>
            </g>
          ))}
          {data.map((d, i) => (data.length - 1 - i) % geo.labelEvery === 0 && (
            <text key={i} x={geo.x(i)} y={H - 8} textAnchor={i === 0 ? "start" : i === data.length - 1 ? "end" : "middle"} className="fill-ink-faint text-[11px]">{dayFmt.format(d.day)}</text>
          ))}
          {SERIES.map((s, si) => (
            <path key={s.key} d={geo.lines[si]} fill="none" style={{ stroke: s.color }} strokeDasharray={s.dash} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
          ))}
          {hover !== null && h && (
            <g>
              <line x1={geo.x(hover)} x2={geo.x(hover)} y1={PAD.top} y2={PAD.top + geo.ih} className="stroke-ink-faint" strokeDasharray="3 3" />
              {SERIES.map((s) => <circle key={s.key} cx={geo.x(hover)} cy={geo.y(h[s.key])} r={5} className="stroke-surface" style={{ fill: s.color }} strokeWidth={2} />)}
            </g>
          )}
        </svg>
        {h && (
          <div className="pointer-events-none absolute top-0 -translate-x-1/2 -translate-y-3 rounded-2xl bg-surface px-4 py-2.5 text-sm ring-1 ring-border" style={{ left: tipLeft }}>
            <div className="font-medium">{longFmt.format(h.day)}</div>
            {SERIES.map((s) => (
              <div key={s.key} className="mt-1 flex items-center gap-2 whitespace-nowrap text-xs text-ink-soft">
                <Swatch s={s} />{s.label}
                <span className="ml-auto pl-3 font-medium tabular-nums text-ink">{h[s.key]}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
        <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-soft">
          {SERIES.map((s) => <li key={s.key} className="flex items-center gap-2"><Swatch s={s} />{s.label}</li>)}
        </ul>
        {aside}
      </div>
      <div className="sr-only"><table>
        <caption>Audit events per day</caption>
        <thead><tr><th>Day</th>{SERIES.map((s) => <th key={s.key}>{s.label}</th>)}</tr></thead>
        <tbody>{data.map((d) => <tr key={d.day.toISOString()}><td>{longFmt.format(d.day)}</td><td>{d.signIns}</td><td>{d.changes}</td></tr>)}</tbody>
      </table></div>
    </div>
  );
}
