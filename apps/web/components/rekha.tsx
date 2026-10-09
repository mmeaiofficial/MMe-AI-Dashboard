"use client";

import { createContext, Fragment, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUp, RotateCcw, Sparkles, X } from "lucide-react";
import { useSession } from "@/components/session";
import { api, ApiError, can } from "@/lib/api";

interface Turn { role: "user" | "assistant"; content: string; }
interface Status { enabled: boolean; model: string; }

const Ctx = createContext<{ open: boolean; setOpen: (v: boolean) => void }>({ open: false, setOpen: () => {} });
export const useRekha = () => useContext(Ctx);
const STORE = "mme-rekha-chat";

export function RekhaProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <Ctx.Provider value={{ open, setOpen }}>
      {children}
      <RekhaPanel />
      {!open && (
        <button onClick={() => setOpen(true)} aria-label="Ask Rekha"
          className="fixed bottom-5 right-5 z-30 flex items-center gap-2 rounded-full bg-brand-fill py-3 pl-3 pr-4 text-sm font-medium text-on-brand ring-1 ring-border transition hover:bg-brand-ink">
          <RekhaMark size={28} /> Ask Rekha
        </button>
      )}
    </Ctx.Provider>
  );
}

export function RekhaMark({ size = 36 }: { size?: number }) {
  return (
    <span className="grid shrink-0 place-items-center rounded-full bg-brand-fill text-on-brand" style={{ width: size, height: size }} aria-hidden="true">
      <Sparkles size={size * 0.5} strokeWidth={2} />
    </span>
  );
}

/** Renders Rekha's plain-text replies: paragraphs, "- " lists and **bold**. React escapes everything. */
function Rich({ text }: { text: string }) {
  const bullet = /^\s*[-•*]\s+/;
  const inline = (s: string) => s.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>);
  // Group each paragraph's lines into runs of plain lines and runs of list items.
  const runs = text.split(/\n{2,}/).flatMap((block) => block.split("\n").reduce<{ list: boolean; lines: string[] }[]>((acc, line) => {
    const list = bullet.test(line), last = acc[acc.length - 1];
    if (last && last.list === list) last.lines.push(line); else acc.push({ list, lines: [line] });
    return acc;
  }, []));
  return (
    <div className="space-y-2">
      {runs.map((r, i) => r.list
        ? <ul key={i} className="list-disc space-y-1 pl-5">{r.lines.map((l, j) => <li key={j}>{inline(l.replace(bullet, ""))}</li>)}</ul>
        : <p key={i}>{r.lines.map((l, j) => <Fragment key={j}>{j > 0 && <br />}{inline(l)}</Fragment>)}</p>)}
    </div>
  );
}

function RekhaPanel() {
  const { me } = useSession();
  const { open, setOpen } = useRekha();
  const [status, setStatus] = useState<Status | null>(null);
  // Read synchronously: the panel only renders client-side (after the session loads), and an effect-based
  // restore would race the save effect below and wipe the stored chat.
  const [turns, setTurns] = useState<Turn[]>(() => {
    try { return JSON.parse(sessionStorage.getItem(STORE) || "[]"); } catch { return []; }
  });
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);

  // The conversation survives page changes in this tab only (a convenience, not a record).
  useEffect(() => { try { sessionStorage.setItem(STORE, JSON.stringify(turns.slice(-40))); } catch { /* storage blocked */ } }, [turns]);
  useEffect(() => { if (open && !status) api.get<Status>("/assistant/status").then(setStatus).catch(() => setStatus({ enabled: false, model: "" })); }, [open, status]);
  useEffect(() => { if (open) input.current?.focus(); }, [open]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns, busy]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  const send = useCallback(async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    const next = [...turns, { role: "user" as const, content: q }];
    setTurns(next); setDraft(""); setError(null); setBusy(true);
    try {
      const r = await api.post<{ reply: string }>("/assistant/chat", { messages: next.slice(-40) });
      setTurns([...next, { role: "assistant", content: r.reply }]);
    } catch (e) {
      setError((e as ApiError).message);
      setTurns(turns); setDraft(q); // give the question back so it can be re-sent
    } finally {
      setBusy(false);
      input.current?.focus();
    }
  }, [busy, turns]);

  if (!me) return null;
  const first = me.full_name.split(" ")[0] || "there";
  const suggestions = [
    "What can I access in MME OS?",
    can(me, "org.employees.view") && "List the interns I can see",
    can(me, "org.teams.view") && "Who is on each team?",
    can(me, "audit.events.view") && "What changed in access this week?",
  ].filter(Boolean) as string[];

  return (
    <>
      <div onClick={() => setOpen(false)} aria-hidden="true"
        className={`fixed inset-0 z-40 bg-canvas transition-opacity md:hidden ${open ? "opacity-100" : "pointer-events-none opacity-0"}`} />
      <section role="dialog" aria-label="Ask Rekha" inert={!open}
        className={`fixed inset-y-0 right-0 z-50 flex w-full flex-col bg-surface ring-1 ring-border transition-transform duration-300 sm:inset-y-3 sm:right-3 sm:w-[420px] sm:rounded-4xl ${open ? "translate-x-0" : "pointer-events-none translate-x-[110%]"}`}>
        <header className="flex items-center gap-3 border-b border-well px-5 py-4">
          <RekhaMark />
          <div className="min-w-0 flex-1 leading-tight">
            <div className="font-semibold">Rekha</div>
            <div className="truncate text-xs text-ink-faint">MME-AI operations assistant · read-only</div>
          </div>
          {turns.length > 0 && (
            <button className="grid h-9 w-9 place-items-center rounded-full text-ink-soft hover:bg-canvas hover:text-ink" onClick={() => { setTurns([]); setError(null); }} aria-label="New chat" title="New chat">
              <RotateCcw size={16} />
            </button>
          )}
          <button className="grid h-9 w-9 place-items-center rounded-full text-ink-soft hover:bg-canvas hover:text-ink" onClick={() => setOpen(false)} aria-label="Close Rekha">
            <X size={18} />
          </button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5 text-sm" aria-live="polite">
          {turns.length === 0 && (
            <div className="space-y-4">
              <div className="rounded-3xl bg-well p-5 ring-1 ring-border">
                <div className="text-lg font-medium">Hi {first}, I'm Rekha.</div>
                <p className="mt-1 text-ink-soft">Ask me about people, teams, access and recent activity in MME OS. I only see what you can see.</p>
              </div>
              {status && !status.enabled && (
                <p className="rounded-2xl bg-well px-4 py-3 text-ink-soft">
                  Rekha isn't switched on yet. An admin needs to add <code className="font-mono text-xs">ANTHROPIC_API_KEY</code> to the API's settings.
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => send(s)} disabled={busy || status?.enabled === false}
                    className="rounded-full bg-canvas px-3.5 py-2 text-left text-ink-soft ring-1 ring-border transition hover:text-ink hover:ring-brand disabled:opacity-50">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {turns.map((t, i) => t.role === "user" ? (
            <div key={i} className="ml-auto w-fit max-w-[85%] whitespace-pre-wrap rounded-3xl rounded-br-lg bg-brand-fill px-4 py-2.5 text-on-brand">{t.content}</div>
          ) : (
            <div key={i} className="flex gap-2.5">
              <RekhaMark size={26} />
              <div className="min-w-0 flex-1 rounded-3xl rounded-tl-lg bg-canvas px-4 py-3 leading-relaxed"><Rich text={t.content} /></div>
            </div>
          ))}
          {busy && (
            <div className="flex items-center gap-2.5" role="status" aria-label="Rekha is thinking">
              <RekhaMark size={26} />
              <span className="flex gap-1 rounded-3xl bg-canvas px-4 py-3.5">
                {[0, 150, 300].map((d) => <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-faint" style={{ animationDelay: `${d}ms` }} />)}
              </span>
            </div>
          )}
          {error && <p role="alert" className="alert-error">{error}</p>}
          <div ref={end} />
        </div>

        <form className="border-t border-well p-3" onSubmit={(e) => { e.preventDefault(); void send(draft); }}>
          <div className="flex items-end gap-2 rounded-3xl bg-canvas p-2 ring-1 ring-transparent focus-within:ring-brand">
            <textarea ref={input} rows={1} value={draft} maxLength={4000} aria-label="Message Rekha"
              placeholder={status?.enabled === false ? "Rekha is switched off" : "Ask Rekha…"} disabled={status?.enabled === false}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(draft); } }}
              className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:outline-none" />
            <button type="submit" disabled={busy || !draft.trim()} aria-label="Send"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand-fill text-on-brand transition hover:bg-brand-ink disabled:opacity-40">
              <ArrowUp size={18} />
            </button>
          </div>
          <p className="mt-2 px-2 text-[11px] text-ink-faint">Rekha can make mistakes. Check important details.</p>
        </form>
      </section>
    </>
  );
}
