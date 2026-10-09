"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Mail, Phone, Search, X } from "lucide-react";
import { useSession } from "@/components/session";
import { Avatar, PageHeader } from "@/components/ui";
import { api, ApiError, can } from "@/lib/api";
import { fmtDate, fmtDateTime, PRIORITIES, relative, TICKET_STATUS, type Person } from "@/lib/pipeline";

interface Ticket {
  id: string; number: number; title: string; description: string | null; priority: string; status: string;
  assignee: Person | null; created_by: Person | null; due_on: string | null; created_at: string; updated_at: string;
  project: { id: string; name: string; summary?: string | null; tickets?: number }; client: { id: string; name: string; contact_name?: string | null;
    email?: string | null; phone?: string | null; website?: string | null; industry?: string | null; city?: string | null };
}
interface Detail extends Ticket {
  meeting: { scheduled_at: string; closer: Person | null; agenda: string | null; outcome_notes: string | null } | null;
  notes: { id: string; body: string; at: string; by: Person | null }[]; teammates: Person[];
}

const PRIORITY_ORDER: Record<string, number> = { urgent: 0, high: 1, normal: 2, low: 3 };

export default function TicketsPage() {
  const { me } = useSession();
  const [items, setItems] = useState<Ticket[]>([]);
  const [mine, setMine] = useState(false);
  const [project, setProject] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Detail | null>(null);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);

  const load = useCallback(async () => {
    try { setItems((await api.get<{ items: Ticket[] }>(`/tickets${mine ? "?mine=true" : ""}`)).items); }
    catch (e) { setMsg({ text: (e as ApiError).message, error: true }); }
  }, [mine]);
  useEffect(() => { void load(); }, [load]);

  const projects = useMemo(() => [...new Map(items.map((t) => [t.project.id, `${t.client.name} · ${t.project.name}`])).entries()], [items]);
  const shown = items.filter((t) => (!project || t.project.id === project) &&
    (!q || `${t.title} ${t.client.name} ${t.project.name} #${t.number}`.toLowerCase().includes(q.toLowerCase())));

  const openTicket = async (id: string) => {
    setNote("");
    try { setOpen(await api.get<Detail>(`/tickets/${id}`)); } catch (e) { setMsg({ text: (e as ApiError).message, error: true }); }
  };
  if (!me) return null;
  const canEdit = can(me, "work.tasks.edit");

  async function patch(body: Record<string, unknown>) {
    if (!open) return;
    try { await api.patch(`/tickets/${open.id}`, body); await Promise.all([openTicket(open.id), load()]); }
    catch (e) { setMsg({ text: (e as ApiError).message, error: true }); }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Tickets" subtitle="Client work for the tech team. Each ticket is a feature a client confirmed with Sales L2." />
      {msg && <p role="status" className={msg.error ? "alert-error" : "rounded-2xl bg-surface px-4 py-3 text-sm ring-1 ring-border"}>{msg.text}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" className="flex gap-1 rounded-full bg-well p-1">
          {[[false, "All I can see"], [true, "Assigned to me"]].map(([v, label]) => (
            <button key={String(v)} role="tab" aria-selected={mine === v} onClick={() => setMine(v as boolean)}
              className={`rounded-full px-4 py-1.5 text-sm ${mine === v ? "bg-brand-fill font-medium text-on-brand" : "text-ink-soft hover:text-ink"}`}>{label as string}</button>
          ))}
        </div>
        <select className="input w-auto max-w-xs" aria-label="Project" value={project} onChange={(e) => setProject(e.target.value)}>
          <option value="">All clients and projects</option>
          {projects.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <div className="relative min-w-56 flex-1">
          <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
          <input className="input pl-10" placeholder="Search tickets" aria-label="Search tickets" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      {items.length === 0 ? (
        <div className="card py-12 text-center text-sm text-ink-soft">No tickets yet. They appear when Sales L2 wins a client and lists the features they need.</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {TICKET_STATUS.map((col) => {
            const list = shown.filter((t) => t.status === col.id).sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority] || a.number - b.number);
            return (
              <section key={col.id} className="rounded-4xl bg-well p-3" aria-label={col.label}>
                <h2 className="flex items-center justify-between px-2 pb-2 text-sm font-medium">{col.label}<span className="text-ink-faint">{list.length}</span></h2>
                <ul className="space-y-2">
                  {list.map((t) => (
                    <li key={t.id}>
                      <button onClick={() => openTicket(t.id)} className="w-full rounded-3xl bg-surface p-4 text-left ring-1 ring-border transition hover:ring-brand">
                        <div className="flex items-center justify-between gap-2 text-xs text-ink-faint">
                          <span>#{t.number}</span>
                          {t.priority !== "normal" && <span className={t.priority === "urgent" || t.priority === "high" ? "pill-bad" : "pill"}>{PRIORITIES[t.priority]}</span>}
                        </div>
                        <div className="mt-1 font-medium leading-snug">{t.title}</div>
                        <div className="mt-1 truncate text-xs text-ink-soft">{t.client.name} · {t.project.name}</div>
                        <div className="mt-3 flex items-center justify-between text-xs text-ink-soft">
                          {t.assignee ? <span className="flex items-center gap-1.5"><Avatar name={t.assignee.name} size={20} />{t.assignee.name}</span> : <span className="text-ink-faint">Unassigned</span>}
                          {t.due_on && <span>Due {fmtDate(t.due_on)}</span>}
                        </div>
                      </button>
                    </li>
                  ))}
                  {list.length === 0 && <li className="px-2 py-4 text-center text-xs text-ink-faint">Nothing here</li>}
                </ul>
              </section>
            );
          })}
        </div>
      )}

      {open && (
        <div className="fixed inset-0 z-50 flex justify-end bg-canvas sm:bg-transparent" role="dialog" aria-modal="true" aria-label={`Ticket ${open.number}`}
          onKeyDown={(e) => { if (e.key === "Escape") setOpen(null); }}>
          <div className="hidden flex-1 sm:block" onClick={() => setOpen(null)} />
          <aside className="flex h-full w-full flex-col overflow-y-auto bg-surface ring-1 ring-border sm:w-[560px]">
            <header className="sticky top-0 z-10 flex items-start gap-3 border-b border-border bg-surface px-6 py-4">
              <div className="flex-1">
                <div className="text-xs text-ink-faint">#{open.number} · {open.client.name} · {open.project.name}</div>
                <h2 className="text-xl font-semibold leading-snug">{open.title}</h2>
              </div>
              <button className="grid h-9 w-9 place-items-center rounded-full text-ink-soft hover:bg-well" onClick={() => setOpen(null)} aria-label="Close"><X size={18} /></button>
            </header>
            <div className="space-y-5 px-6 py-5 text-sm">
              {/* Status and ownership */}
              <div role="radiogroup" aria-label="Status" className="grid grid-cols-4 gap-1 rounded-full bg-well p-1">
                {TICKET_STATUS.map((s) => (
                  <button key={s.id} role="radio" aria-checked={open.status === s.id} disabled={!canEdit} onClick={() => patch({ status: s.id })}
                    className={`rounded-full py-1.5 text-xs font-medium ${open.status === s.id ? "bg-brand-fill text-on-brand" : "text-ink-soft enabled:hover:text-ink"}`}>{s.label}</button>
                ))}
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div><label className="label" htmlFor="as">Assignee</label>
                  <select id="as" className="input" disabled={!canEdit} value={open.assignee?.id ?? ""} onChange={(e) => patch({ assignee_id: e.target.value || null })}>
                    <option value="">Unassigned</option>
                    {[...new Map([...(open.assignee ? [open.assignee] : []), { id: me.id, name: "Me" }, ...open.teammates.filter((p) => p.id !== me.id)].map((p) => [p.id, p])).values()]
                      .map((p) => <option key={p.id} value={p.id}>{p.id === me.id ? `Me (${me.full_name || me.email})` : p.name}</option>)}
                  </select></div>
                <div><label className="label" htmlFor="pr">Priority</label>
                  <select id="pr" className="input" disabled={!canEdit} value={open.priority} onChange={(e) => patch({ priority: e.target.value })}>
                    {Object.entries(PRIORITIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select></div>
                <div><label className="label" htmlFor="due">Due</label>
                  <input id="due" type="date" className="input" disabled={!canEdit} value={open.due_on ?? ""} onChange={(e) => patch({ due_on: e.target.value || null })} /></div>
              </div>
              {canEdit && !open.assignee && <button className="btn-primary w-full justify-center" onClick={() => patch({ assignee_id: me.id, status: open.status === "todo" ? "in_progress" : open.status })}>Take this ticket</button>}

              <section><h3 className="mb-1 font-medium">What the client needs</h3>
                <p className="whitespace-pre-wrap rounded-3xl bg-well px-4 py-3">{open.description || "No extra details. Check the meeting notes below or ask the Sales L2 owner."}</p></section>

              <section className="rounded-3xl p-4 ring-1 ring-border"><h3 className="mb-2 font-medium">Client</h3>
                <div className="font-medium">{open.client.name}</div>
                <div className="text-ink-soft">{[open.client.contact_name, open.client.industry, open.client.city].filter(Boolean).join(" · ")}</div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                  {open.client.phone && <a className="flex items-center gap-1.5 text-brand-text" href={`tel:${open.client.phone.replace(/[^\d+]/g, "")}`}><Phone size={14} />{open.client.phone}</a>}
                  {open.client.email && <a className="flex items-center gap-1.5 text-brand-text" href={`mailto:${open.client.email}`}><Mail size={14} />{open.client.email}</a>}
                  {open.client.website && <span className="text-ink-soft">{open.client.website}</span>}
                </div></section>

              <section className="rounded-3xl p-4 ring-1 ring-border"><h3 className="mb-2 font-medium">Project · {open.project.name}</h3>
                <p className="whitespace-pre-wrap text-ink-soft">{open.project.summary || "No summary."}</p>
                <p className="mt-2 text-xs text-ink-faint">{open.project.tickets} ticket(s) in this project</p></section>

              {open.meeting && (
                <section className="rounded-3xl p-4 ring-1 ring-border"><h3 className="mb-2 font-medium">From the sales meeting</h3>
                  <p className="text-xs text-ink-faint">{fmtDateTime(open.meeting.scheduled_at)}{open.meeting.closer ? ` · closed by ${open.meeting.closer.name}` : ""}</p>
                  {open.meeting.agenda && <p className="mt-2"><b className="font-medium">What they asked for:</b> {open.meeting.agenda}</p>}
                  {open.meeting.outcome_notes && <p className="mt-1"><b className="font-medium">Meeting notes:</b> {open.meeting.outcome_notes}</p>}
                </section>
              )}

              <section><h3 className="mb-2 font-medium">Notes</h3>
                <ol className="space-y-3">
                  {open.notes.map((n) => (
                    <li key={n.id} className="flex gap-2.5"><Avatar name={n.by?.name ?? "?"} size={26} />
                      <div className="flex-1 rounded-2xl bg-well px-3 py-2"><div className="text-xs text-ink-faint">{n.by?.name ?? "Someone"} · {relative(n.at)}</div><p className="whitespace-pre-wrap">{n.body}</p></div></li>
                  ))}
                  {open.notes.length === 0 && <li className="text-ink-faint">No notes yet.</li>}
                </ol>
                {canEdit && (
                  <form className="mt-3 flex gap-2" onSubmit={async (e) => {
                    e.preventDefault();
                    if (!note.trim()) return;
                    try { await api.post(`/tickets/${open.id}/notes`, { body: note }); setNote(""); await openTicket(open.id); }
                    catch (err) { setMsg({ text: (err as ApiError).message, error: true }); }
                  }}>
                    <input className="input" placeholder="Add a note for the team" aria-label="Add a note" value={note} onChange={(e) => setNote(e.target.value)} />
                    <button className="btn-primary" disabled={!note.trim()}>Add</button>
                  </form>
                )}
              </section>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
