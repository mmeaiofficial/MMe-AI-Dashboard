"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Phone, Mail, Globe, CalendarCheck } from "lucide-react";
import { useSession } from "@/components/session";
import { PageHeader, Stat } from "@/components/ui";
import { api, ApiError, can } from "@/lib/api";
import {
  CALL_OUTCOMES, fmtDateTime, fromLocalInput, LEAD_STATUS, MODES, OUTCOME_LABEL, relative, tomorrowAt, type CallEntry, type Lead,
} from "@/lib/pipeline";

interface Queue { items: Lead[]; stats: { calls_today: number; meetings_booked_7d: number; due_now: number }; }
type Detail = Lead & { calls: CallEntry[] };

const blankLog = () => ({ outcome: "", notes: "", callback_at: tomorrowAt(11), scheduled_at: tomorrowAt(15), duration: "30", mode: "google_meet", link: "", agenda: "" });

export default function CallsPage() {
  const { me } = useSession();
  const [queue, setQueue] = useState<Queue | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [log, setLog] = useState(blankLog);
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (keep?: string | null) => {
    try {
      const q = await api.get<Queue>("/calls/queue");
      setQueue(q);
      setSelected((cur) => {
        const want = keep !== undefined ? keep : cur;
        return want && q.items.some((l) => l.id === want) ? want : q.items[0]?.id ?? null;
      });
    } catch (e) { setMsg({ text: (e as ApiError).message, error: true }); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    setDetail(null); setLog(blankLog());
    if (selected) api.get<Detail>(`/calls/leads/${selected}`).then(setDetail).catch((e) => setMsg({ text: (e as ApiError).message, error: true }));
  }, [selected]);

  const ordered = useMemo(() => queue?.items ?? [], [queue]);
  if (!me) return null;
  const canLog = can(me, "sales.calls.create");

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!detail || !log.outcome) return;
    const body: Record<string, unknown> = { outcome: log.outcome, notes: log.notes || null };
    if (log.outcome === "callback" || log.outcome === "interested") body.callback_at = fromLocalInput(log.callback_at);
    if (log.outcome === "meeting_booked") {
      body.meeting = { scheduled_at: fromLocalInput(log.scheduled_at), duration_minutes: Number(log.duration), mode: log.mode,
        link_or_location: log.link || null, agenda: log.agenda || null };
    }
    setSaving(true); setMsg(null);
    try {
      const r = await api.post<Lead>(`/calls/leads/${detail.id}/log`, body);
      const next = ordered.find((l) => l.id !== detail.id)?.id ?? null;
      setMsg({ text: log.outcome === "meeting_booked"
        ? `Meeting booked with ${detail.contact_name}${r.closer ? ` and handed to ${r.closer.name}` : ". No Sales L2 team yet, so it waits for anyone in L2 to pick it up"}.`
        : `Call logged: ${OUTCOME_LABEL[log.outcome]}.` });
      setSelected(null); // forces the details to reload even if the same lead stays first in the queue
      await load(next);
    } catch (err) { setMsg({ text: (err as ApiError).message, error: true }); } finally { setSaving(false); }
  }

  return (
    <div className="max-w-6xl space-y-6">
      <PageHeader title="Cold calls" subtitle="Your call queue. Log every call; a booked meeting goes straight to Sales L2." />
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Due now" value={queue?.stats.due_now ?? "—"} strong />
        <Stat label="Calls today" value={queue?.stats.calls_today ?? "—"} />
        <Stat label="Meetings booked, 7 days" value={queue?.stats.meetings_booked_7d ?? "—"} />
      </div>
      {msg && <p role="status" className={msg.error ? "alert-error" : "rounded-2xl bg-surface px-4 py-3 text-sm ring-1 ring-border"}>{msg.text}</p>}

      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        {/* Queue */}
        <section className="card h-fit p-2" aria-label="Call queue">
          <div className="px-3 py-2 text-xs font-medium text-ink-faint">{ordered.length} in queue</div>
          {ordered.length === 0 && <p className="px-3 pb-4 text-sm text-ink-soft">Nothing to call right now. New leads appear here when the lead team qualifies them.</p>}
          <ul className="space-y-1">
            {ordered.map((l) => (
              <li key={l.id}>
                <button onClick={() => setSelected(l.id)} aria-current={selected === l.id}
                  className={`w-full rounded-2xl px-3 py-2.5 text-left transition ${selected === l.id ? "bg-brand-soft ring-1 ring-brand" : "hover:bg-well"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium">{l.contact_name}</span>
                    <span className={`shrink-0 text-xs ${l.due ? "font-medium text-brand-text" : "text-ink-faint"}`}>{l.due ? "Due now" : relative(l.next_call_at)}</span>
                  </div>
                  <div className="mt-0.5 flex items-center justify-between gap-2 text-xs text-ink-soft">
                    <span className="truncate">{l.company || l.city || "—"}</span>
                    <span className="shrink-0">{l.unassigned ? "Open pool" : l.last_call ? OUTCOME_LABEL[l.last_call.outcome] : LEAD_STATUS[l.status]}{l.call_attempts ? ` · ${l.call_attempts}×` : ""}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </section>

        {/* Selected lead */}
        {detail ? (
          <section className="space-y-4" aria-label={`Call ${detail.contact_name}`}>
            <div className="card space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-semibold tracking-tight">{detail.contact_name}</h2>
                  <p className="text-sm text-ink-soft">{[detail.company, detail.industry, detail.city].filter(Boolean).join(" · ") || "No company details"}</p>
                </div>
                {detail.phone && <a href={`tel:${detail.phone.replace(/[^\d+]/g, "")}`} className="btn-primary px-5 py-2.5 text-base"><Phone size={18} />{detail.phone}</a>}
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-soft">
                {detail.email && <a className="flex items-center gap-1.5 hover:text-ink" href={`mailto:${detail.email}`}><Mail size={14} />{detail.email}</a>}
                {detail.website && <a className="flex items-center gap-1.5 hover:text-ink" href={/^https?:/.test(detail.website) ? detail.website : `https://${detail.website}`} target="_blank" rel="noreferrer"><Globe size={14} />{detail.website}</a>}
                <span>Attempts: {detail.call_attempts}</span>
                {detail.created_by && <span>Found by {detail.created_by.name}</span>}
              </div>
              {detail.notes && <p className="rounded-2xl bg-well px-4 py-3 text-sm"><b className="font-medium">From the lead team:</b> {detail.notes}</p>}
            </div>

            {canLog && (
              <form className="card space-y-4" onSubmit={save}>
                <h3 className="font-medium">How did the call go?</h3>
                <div role="radiogroup" aria-label="Call outcome" className="flex flex-wrap gap-2">
                  {CALL_OUTCOMES.map((o) => (
                    <button key={o.id} type="button" role="radio" aria-checked={log.outcome === o.id} onClick={() => setLog({ ...log, outcome: o.id })}
                      className={`rounded-full px-3.5 py-2 text-sm ring-1 transition ${log.outcome === o.id ? "bg-brand-fill font-medium text-on-brand ring-brand-fill" : "bg-surface text-ink ring-border hover:ring-brand"}`}>
                      {o.label}
                    </button>
                  ))}
                </div>

                {(log.outcome === "callback" || log.outcome === "interested") && (
                  <div className="max-w-xs"><label className="label" htmlFor="cb">Call back at</label>
                    <input id="cb" type="datetime-local" className="input" required value={log.callback_at} onChange={(e) => setLog({ ...log, callback_at: e.target.value })} /></div>
                )}

                {log.outcome === "meeting_booked" && (
                  <div className="grid gap-3 rounded-3xl bg-well p-4 sm:grid-cols-2">
                    <div className="flex items-center gap-2 font-medium sm:col-span-2"><CalendarCheck size={18} className="text-brand" />Meeting details for Sales L2</div>
                    <div><label className="label" htmlFor="m-at">Date and time</label>
                      <input id="m-at" type="datetime-local" className="input bg-surface" required value={log.scheduled_at} onChange={(e) => setLog({ ...log, scheduled_at: e.target.value })} /></div>
                    <div><label className="label" htmlFor="m-dur">Length</label>
                      <select id="m-dur" className="input bg-surface" value={log.duration} onChange={(e) => setLog({ ...log, duration: e.target.value })}>
                        {["15", "30", "45", "60", "90"].map((m) => <option key={m} value={m}>{m} minutes</option>)}
                      </select></div>
                    <div><label className="label" htmlFor="m-mode">How</label>
                      <select id="m-mode" className="input bg-surface" value={log.mode} onChange={(e) => setLog({ ...log, mode: e.target.value })}>
                        {Object.entries(MODES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select></div>
                    <div><label className="label" htmlFor="m-link">Link or address</label>
                      <input id="m-link" className="input bg-surface" placeholder="https://meet.google.com/…" value={log.link} onChange={(e) => setLog({ ...log, link: e.target.value })} /></div>
                    <div className="sm:col-span-2"><label className="label" htmlFor="m-agenda">What do they want? (L2 reads this before the meeting)</label>
                      <textarea id="m-agenda" className="input min-h-20 rounded-3xl bg-surface" value={log.agenda} onChange={(e) => setLog({ ...log, agenda: e.target.value })}
                        placeholder="e.g. Loses leads on WhatsApp, wants auto-replies and a follow-up reminder" /></div>
                  </div>
                )}

                <div><label className="label" htmlFor="notes">Call notes</label>
                  <textarea id="notes" className="input min-h-20 rounded-3xl" value={log.notes} onChange={(e) => setLog({ ...log, notes: e.target.value })} placeholder="Anything the next person should know" /></div>
                <div className="flex justify-end"><button className="btn-primary" disabled={!log.outcome || saving}>{saving ? "Saving…" : "Save and next lead"}</button></div>
              </form>
            )}

            <div className="card">
              <h3 className="mb-3 font-medium">Call history</h3>
              {detail.calls.length === 0 ? <p className="text-sm text-ink-soft">No calls yet. You're first.</p> : (
                <ol className="space-y-3">
                  {detail.calls.map((c, i) => (
                    <li key={i} className="flex gap-3 text-sm">
                      <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand" aria-hidden="true" />
                      <div><div><b className="font-medium">{OUTCOME_LABEL[c.outcome] ?? c.outcome}</b> <span className="text-xs text-ink-faint">· {fmtDateTime(c.at)}{c.by ? ` · ${c.by.name}` : ""}</span></div>
                        {c.notes && <p className="text-ink-soft">{c.notes}</p>}</div>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </section>
        ) : (
          <section className="card grid place-items-center py-16 text-sm text-ink-soft">{ordered.length ? "Loading…" : "Your queue is empty."}</section>
        )}
      </div>
    </div>
  );
}
