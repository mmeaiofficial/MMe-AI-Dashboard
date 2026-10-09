"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CalendarClock, ExternalLink, Plus, Trash2 } from "lucide-react";
import { useSession } from "@/components/session";
import { Modal, PageHeader } from "@/components/ui";
import { api, ApiError, can } from "@/lib/api";
import {
  dayLabel, fmtDateTime, fmtTime, fromLocalInput, MODES, OUTCOME_LABEL, PRIORITIES, toLocalInput, type CallEntry, type Person,
} from "@/lib/pipeline";

interface MeetingLead { id: string; contact_name: string; company: string | null; phone: string | null; email: string | null;
  city: string | null; industry: string | null; website: string | null; notes: string | null; }
interface Meeting {
  id: string; scheduled_at: string; duration_minutes: number; mode: string; link_or_location: string | null; agenda: string | null;
  status: string; outcome: string | null; outcome_notes: string | null; deal_value: number | null; booked_by: Person | null; closer: Person | null;
  lead: MeetingLead; calls?: CallEntry[]; project?: { id: string; name: string; tickets: number };
}
interface Feature { title: string; details: string; priority: string; }
const newFeature = (): Feature => ({ title: "", details: "", priority: "normal" });

export default function MeetingsPage() {
  const { me } = useSession();
  const [when, setWhen] = useState<"upcoming" | "past">("upcoming");
  const [items, setItems] = useState<Meeting[]>([]);
  const [open, setOpen] = useState<Meeting | null>(null);
  const [closing, setClosing] = useState<"won" | "lost" | "no_show" | null>(null);
  const [notes, setNotes] = useState("");
  const [value, setValue] = useState("");
  const [project, setProject] = useState({ name: "", summary: "" });
  const [features, setFeatures] = useState<Feature[]>([newFeature()]);
  const [resched, setResched] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try { setItems((await api.get<{ items: Meeting[] }>(`/meetings?when=${when}`)).items); }
    catch (e) { setMsg({ text: (e as ApiError).message, error: true }); }
  }, [when]);
  useEffect(() => { void load(); }, [load]);

  const show = async (m: Meeting) => {
    setClosing(null); setResched(null); setNotes(""); setValue(""); setFeatures([newFeature()]);
    setProject({ name: `${m.lead.company || m.lead.contact_name} project`, summary: m.agenda ?? "" });
    try { setOpen(await api.get<Meeting>(`/meetings/${m.id}`)); } catch (e) { setMsg({ text: (e as ApiError).message, error: true }); }
  };

  if (!me) return null;
  const canEdit = can(me, "sales.deals.edit");
  const groups = items.reduce<Record<string, Meeting[]>>((acc, m) => { (acc[dayLabel(m.scheduled_at)] ??= []).push(m); return acc; }, {});

  async function complete() {
    if (!open || !closing) return;
    const reqs = features.filter((f) => f.title.trim()).map((f) => ({ title: f.title.trim(), details: f.details.trim() || null, priority: f.priority }));
    setSaving(true); setMsg(null);
    try {
      const r = await api.post<{ tickets?: number }>(`/meetings/${open.id}/complete`, {
        outcome: closing, notes: notes || null, deal_value: closing === "won" && value ? Number(value) : null,
        project_name: project.name || null, project_summary: project.summary || null, requirements: closing === "won" ? reqs : [],
      });
      setMsg({ text: closing === "won" ? `Won! ${r.tickets} ticket(s) sent to the tech team.`
        : closing === "lost" ? "Marked as lost." : `No-show noted. ${open.lead.contact_name} is back in the caller's queue to rebook.` });
      setOpen(null); await load();
    } catch (e) { setMsg({ text: (e as ApiError).message, error: true }); } finally { setSaving(false); }
  }

  async function reschedule() {
    if (!open || !resched) return;
    setSaving(true);
    try { await api.post(`/meetings/${open.id}/reschedule`, { scheduled_at: fromLocalInput(resched) }); setMsg({ text: "Meeting moved." }); setOpen(null); await load(); }
    catch (e) { setMsg({ text: (e as ApiError).message, error: true }); } finally { setSaving(false); }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader title="Meetings" subtitle="Meetings booked by Sales L1. Close each one: a win sends the client's features to tech as tickets." />
      <div role="tablist" className="flex w-fit gap-1 rounded-full bg-well p-1">
        {(["upcoming", "past"] as const).map((w) => (
          <button key={w} role="tab" aria-selected={when === w} onClick={() => setWhen(w)}
            className={`rounded-full px-4 py-1.5 text-sm ${when === w ? "bg-brand-fill font-medium text-on-brand" : "text-ink-soft hover:text-ink"}`}>{w === "upcoming" ? "Upcoming" : "Past"}</button>
        ))}
      </div>
      {msg && <p role="status" className={msg.error ? "alert-error" : "rounded-2xl bg-surface px-4 py-3 text-sm ring-1 ring-border"}>{msg.text}</p>}

      {items.length === 0 && <div className="card py-12 text-center text-sm text-ink-soft">{when === "upcoming" ? "No meetings booked yet. They appear here as soon as a caller books one." : "No past meetings yet."}</div>}
      {Object.entries(groups).map(([day, ms]) => (
        <section key={day} className="space-y-2">
          <h2 className="px-1 text-sm font-medium text-ink-soft">{day}</h2>
          {ms.map((m) => (
            <button key={m.id} onClick={() => show(m)} className="card flex w-full flex-wrap items-center gap-4 py-4 text-left transition hover:ring-brand">
              <div className="w-20 shrink-0"><div className="text-lg font-semibold tabular-nums">{fmtTime(m.scheduled_at)}</div><div className="text-xs text-ink-faint">{m.duration_minutes} min</div></div>
              <div className="min-w-48 flex-1">
                <div className="font-medium">{m.lead.company || m.lead.contact_name}</div>
                <div className="text-xs text-ink-soft">{m.lead.contact_name} · {MODES[m.mode]}{m.booked_by ? ` · booked by ${m.booked_by.name}` : ""}</div>
              </div>
              {m.status === "scheduled"
                ? <span className={m.closer ? "pill" : "pill-warn"}>{m.closer ? m.closer.name : "Unassigned"}</span>
                : <span className={m.outcome === "won" ? "pill-good" : "pill"}>{m.outcome === "won" ? "Won" : m.outcome === "lost" ? "Lost" : m.status === "no_show" ? "No-show" : m.status}</span>}
            </button>
          ))}
        </section>
      ))}

      {open && (
        <Modal title={`${open.lead.company || open.lead.contact_name}`} onClose={() => setOpen(null)} wide>
          <div className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-3">
              <span className="flex items-center gap-1.5 font-medium"><CalendarClock size={16} className="text-brand" />{fmtDateTime(open.scheduled_at)} · {open.duration_minutes} min · {MODES[open.mode]}</span>
              {open.link_or_location && (/^https?:\/\//.test(open.link_or_location)
                ? <a className="btn-primary px-3 py-1.5 text-xs" href={open.link_or_location} target="_blank" rel="noreferrer"><ExternalLink size={14} />Join</a>
                : <span className="pill">{open.link_or_location}</span>)}
            </div>
            <div className="grid gap-3 rounded-3xl bg-well p-4 sm:grid-cols-2">
              <div><div className="label px-0">Contact</div>{open.lead.contact_name}<div className="text-ink-soft">{open.lead.phone}</div><div className="text-ink-soft">{open.lead.email}</div></div>
              <div><div className="label px-0">Business</div>{[open.lead.company, open.lead.industry, open.lead.city].filter(Boolean).join(" · ") || "—"}<div className="text-ink-soft">{open.lead.website}</div></div>
              {open.agenda && <div className="sm:col-span-2"><div className="label px-0">What they want (from the caller)</div>{open.agenda}</div>}
              {open.lead.notes && <div className="sm:col-span-2"><div className="label px-0">Lead team notes</div>{open.lead.notes}</div>}
            </div>
            {!!open.calls?.length && (
              <details className="rounded-3xl bg-surface px-4 py-3 ring-1 ring-border">
                <summary className="cursor-pointer font-medium">Call history ({open.calls.length})</summary>
                <ol className="mt-2 space-y-2">{open.calls.map((c, i) => (
                  <li key={i}><b className="font-medium">{OUTCOME_LABEL[c.outcome]}</b> <span className="text-xs text-ink-faint">· {fmtDateTime(c.at)}{c.by ? ` · ${c.by.name}` : ""}</span>{c.notes && <div className="text-ink-soft">{c.notes}</div>}</li>
                ))}</ol>
              </details>
            )}

            {open.status !== "scheduled" && (
              <div className="rounded-3xl bg-well p-4">
                <b className="font-medium">{open.outcome === "won" ? "Won" : open.outcome === "lost" ? "Lost" : "No-show"}</b>{open.deal_value != null && ` · ₹${open.deal_value.toLocaleString()}`}
                {open.outcome_notes && <p className="text-ink-soft">{open.outcome_notes}</p>}
                {open.project && <p className="mt-2"><Link className="font-medium text-brand-text underline" href="/tickets">{open.project.tickets} ticket(s) in {open.project.name}</Link></p>}
              </div>
            )}

            {open.status === "scheduled" && canEdit && !closing && resched === null && (
              <div className="flex flex-wrap justify-end gap-2">
                <button className="btn" onClick={() => setResched(toLocalInput(new Date(open.scheduled_at)))}>Reschedule</button>
                <button className="btn" onClick={() => setClosing("no_show")}>No-show</button>
                <button className="btn" onClick={() => setClosing("lost")}>Lost</button>
                <button className="btn-primary" onClick={() => setClosing("won")}>Won</button>
              </div>
            )}

            {resched !== null && (
              <div className="flex flex-wrap items-end gap-2 rounded-3xl bg-well p-4">
                <div className="flex-1"><label className="label" htmlFor="rs">New date and time</label><input id="rs" type="datetime-local" className="input bg-surface" value={resched} onChange={(e) => setResched(e.target.value)} /></div>
                <button className="btn" onClick={() => setResched(null)}>Cancel</button>
                <button className="btn-primary" disabled={saving} onClick={reschedule}>Move meeting</button>
              </div>
            )}

            {closing && (
              <div className="space-y-3 rounded-3xl bg-well p-4">
                <div className="font-medium">{closing === "won" ? "Close as won" : closing === "lost" ? "Close as lost" : "Mark as no-show"}</div>
                {closing === "won" && (
                  <>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div><label className="label" htmlFor="pn">Project name</label><input id="pn" className="input bg-surface" value={project.name} onChange={(e) => setProject({ ...project, name: e.target.value })} /></div>
                      <div><label className="label" htmlFor="dv">Deal value (₹, optional)</label><input id="dv" type="number" min="0" className="input bg-surface" value={value} onChange={(e) => setValue(e.target.value)} /></div>
                      <div className="sm:col-span-2"><label className="label" htmlFor="ps">Project summary for tech</label>
                        <textarea id="ps" className="input min-h-16 rounded-3xl bg-surface" value={project.summary} onChange={(e) => setProject({ ...project, summary: e.target.value })} /></div>
                    </div>
                    <div>
                      <div className="label">Features the client confirmed (each becomes a ticket)</div>
                      <div className="space-y-2">
                        {features.map((f, i) => (
                          <div key={i} className="grid gap-2 rounded-2xl bg-surface p-3 ring-1 ring-border sm:grid-cols-[1fr_120px_auto]">
                            <input className="input" placeholder={`Feature ${i + 1}, e.g. WhatsApp auto-reply`} aria-label={`Feature ${i + 1} title`} value={f.title}
                              onChange={(e) => setFeatures(features.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))} />
                            <select className="input" aria-label={`Feature ${i + 1} priority`} value={f.priority} onChange={(e) => setFeatures(features.map((x, j) => (j === i ? { ...x, priority: e.target.value } : x)))}>
                              {Object.entries(PRIORITIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                            </select>
                            <button type="button" className="grid h-10 w-10 place-items-center rounded-full text-ink-soft hover:text-ink disabled:opacity-40" aria-label={`Remove feature ${i + 1}`}
                              disabled={features.length === 1} onClick={() => setFeatures(features.filter((_, j) => j !== i))}><Trash2 size={16} /></button>
                            <textarea className="input min-h-14 rounded-2xl sm:col-span-3" placeholder="Details: what exactly it should do, examples, deadlines" aria-label={`Feature ${i + 1} details`}
                              value={f.details} onChange={(e) => setFeatures(features.map((x, j) => (j === i ? { ...x, details: e.target.value } : x)))} />
                          </div>
                        ))}
                      </div>
                      <button type="button" className="btn mt-2" onClick={() => setFeatures([...features, newFeature()])}><Plus size={16} />Add another feature</button>
                    </div>
                  </>
                )}
                <div><label className="label" htmlFor="on">{closing === "lost" ? "Why did we lose it?" : "Meeting notes"}</label>
                  <textarea id="on" className="input min-h-16 rounded-3xl bg-surface" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
                <div className="flex justify-end gap-2">
                  <button className="btn" onClick={() => setClosing(null)}>Back</button>
                  <button className="btn-primary" disabled={saving || (closing === "won" && !features.some((f) => f.title.trim()))} onClick={complete}>
                    {closing === "won" ? `Create project and ${features.filter((f) => f.title.trim()).length} ticket(s)` : "Save"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
