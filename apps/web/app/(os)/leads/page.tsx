"use client";

import { useCallback, useEffect, useState } from "react";
import { ClipboardList, Plus, Search } from "lucide-react";
import { useSession } from "@/components/session";
import { Modal, PageHeader, Stat } from "@/components/ui";
import { api, ApiError, can } from "@/lib/api";
import { fmtDate, LEAD_STATUS, SOURCES, type Lead } from "@/lib/pipeline";

const TABS: { id: string; label: string; statuses: string[] }[] = [
  { id: "new", label: "New", statuses: ["new"] },
  { id: "calling", label: "With callers", statuses: ["qualified", "contacted", "callback"] },
  { id: "meeting", label: "Meeting booked", statuses: ["meeting_booked"] },
  { id: "won", label: "Won", statuses: ["won"] },
  { id: "closed", label: "Closed", statuses: ["disqualified", "not_interested", "lost"] },
  { id: "all", label: "All", statuses: [] },
];
const EMPTY = { contact_name: "", company: "", phone: "", email: "", city: "", industry: "", website: "", source: "manual", notes: "" };

/** Parses rows pasted from Excel / Google Sheets / CSV: Name, Company, Phone, Email, City (header row optional). */
function parseRows(text: string) {
  return text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
    .map((l) => l.split(l.includes("\t") ? "\t" : ",").map((c) => c.trim().replace(/^"|"$/g, "")))
    .filter((c) => c[0] && !/^(name|contact)/i.test(c[0]))
    .map(([contact_name, company, phone, email, city]) => ({ contact_name, company: company || null, phone: phone || null, email: email || null, city: city || null }));
}

export default function LeadsPage() {
  const { me } = useSession();
  const [tab, setTab] = useState("new");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Lead[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);
  const [form, setForm] = useState<typeof EMPTY | null>(null);
  const [paste, setPaste] = useState<string | null>(null);
  const [reject, setReject] = useState<Lead | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    const statuses = TABS.find((t) => t.id === tab)!.statuses.join(",");
    const qs = new URLSearchParams();
    if (statuses) qs.set("status", statuses);
    if (q.trim()) qs.set("q", q.trim());
    try {
      const r = await api.get<{ items: Lead[]; counts: Record<string, number> }>(`/leads?${qs}`);
      setItems(r.items); setCounts(r.counts);
    } catch (e) { setMsg({ text: (e as ApiError).message, error: true }); }
  }, [tab, q]);
  useEffect(() => { const t = setTimeout(() => void load(), q ? 250 : 0); return () => clearTimeout(t); }, [load, q]);

  if (!me) return null;
  const canAdd = can(me, "crm.leads.create"), canEdit = can(me, "crm.leads.edit");
  const count = (id: string) => { const s = TABS.find((t) => t.id === id)!.statuses; return s.length ? s.reduce((n, k) => n + (counts[k] ?? 0), 0) : Object.values(counts).reduce((a, b) => a + b, 0); };

  /** Runs an action; ``fn`` returns the success message to show. */
  async function act(fn: () => Promise<string>, key: string) {
    setBusy(key); setMsg(null);
    try { const ok = await fn(); setMsg({ text: ok }); await load(); } catch (e) { setMsg({ text: (e as ApiError).message, error: true }); } finally { setBusy(null); }
  }

  return (
    <div className="max-w-6xl space-y-6">
      <PageHeader title="Leads" subtitle="Add and qualify leads. Qualified leads go straight to a Sales L1 caller's queue."
        actions={canAdd && (
          <div className="flex gap-2">
            <button className="btn" onClick={() => setPaste("")}><ClipboardList size={16} />Paste a list</button>
            <button className="btn-primary" onClick={() => setForm({ ...EMPTY })}><Plus size={16} />Add lead</button>
          </div>
        )} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="New, waiting to qualify" value={count("new")} strong />
        <Stat label="With callers" value={count("calling")} />
        <Stat label="Meetings booked" value={count("meeting")} />
        <Stat label="Won" value={count("won")} />
      </div>

      {msg && <p role="status" className={msg.error ? "alert-error" : "rounded-2xl bg-surface px-4 py-3 text-sm ring-1 ring-border"}>{msg.text}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label="Lead status" className="flex flex-wrap gap-1 rounded-full bg-well p-1">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
              className={`rounded-full px-3.5 py-1.5 text-sm transition ${tab === t.id ? "bg-brand-fill font-medium text-on-brand" : "text-ink-soft hover:text-ink"}`}>
              {t.label} <span className="tabular-nums opacity-80">{count(t.id)}</span>
            </button>
          ))}
        </div>
        <div className="relative min-w-56 flex-1">
          <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
          <input className="input pl-10" placeholder="Search name, company, phone, email, city" aria-label="Search leads" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="thead"><tr><th className="px-5 py-3 font-medium">Lead</th><th className="px-5 py-3 font-medium">Contact</th><th className="px-5 py-3 font-medium">Source</th><th className="px-5 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">With</th><th className="px-5 py-3 font-medium">Added</th><th className="px-5 py-3" /></tr></thead>
          <tbody>
            {items.map((l) => (
              <tr key={l.id} className="border-t border-border align-top">
                <td className="px-5 py-3.5"><div className="font-medium">{l.contact_name}</div><div className="text-xs text-ink-soft">{[l.company, l.city].filter(Boolean).join(" · ") || "—"}</div></td>
                <td className="px-5 py-3.5 text-xs"><div>{l.phone || "—"}</div><div className="text-ink-soft">{l.email || ""}</div></td>
                <td className="px-5 py-3.5 text-xs text-ink-soft">{SOURCES[l.source] ?? l.source}</td>
                <td className="px-5 py-3.5"><span className={l.status === "won" ? "pill-good" : "pill"}>{LEAD_STATUS[l.status] ?? l.status}</span>
                  {l.status_reason && <div className="mt-1 max-w-48 text-xs text-ink-faint">{l.status_reason}</div>}</td>
                <td className="px-5 py-3.5 text-xs text-ink-soft">{l.closer?.name ?? l.caller?.name ?? (["qualified"].includes(l.status) ? "Waiting for a caller" : "—")}</td>
                <td className="px-5 py-3.5 text-xs text-ink-soft">{fmtDate(l.created_at)}</td>
                <td className="whitespace-nowrap px-5 py-3.5 text-right">
                  {canEdit && (l.status === "new" || l.status === "disqualified") && (
                    <button className="btn-primary px-3 py-1.5 text-xs" disabled={busy === l.id}
                      onClick={() => act(async () => {
                        const r = await api.post<Lead>(`/leads/${l.id}/qualify`);
                        return r.caller ? `${l.contact_name} qualified and sent to ${r.caller.name}'s call queue.`
                          : `${l.contact_name} qualified. No Sales L1 team yet, so it waits in the shared call pool.`;
                      }, l.id)}>Qualify</button>
                  )}
                  {canEdit && (l.status === "new" || l.status === "qualified") && (
                    <button className="btn ml-2 px-3 py-1.5 text-xs" onClick={() => { setReject(l); setReason(""); }}>Reject</button>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={7} className="px-5 py-10 text-center text-ink-soft">{q ? "No leads match your search." : tab === "new" ? "No new leads. Add one or paste a list." : "Nothing here yet."}</td></tr>}
          </tbody>
        </table>
      </div>

      {form && (
        <Modal title="Add a lead" onClose={() => setForm(null)} wide>
          <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => {
            e.preventDefault();
            if (!form.phone.trim() && !form.email.trim()) { setMsg({ text: "Add a phone number or an email so the caller can reach them.", error: true }); return; }
            void act(async () => { await api.post("/leads", form); setForm(null); setTab("new"); return `${form.contact_name} added.`; }, "add");
          }}>
            {([["contact_name", "Contact name *"], ["company", "Company"], ["phone", "Phone"], ["email", "Email"], ["city", "City"], ["industry", "Industry"], ["website", "Website"]] as const).map(([k, label]) => (
              <div key={k}><label className="label" htmlFor={`lead-${k}`}>{label}</label>
                <input id={`lead-${k}`} className="input" required={k === "contact_name"} type={k === "email" ? "email" : "text"} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></div>
            ))}
            <div><label className="label" htmlFor="lead-source">Source</label>
              <select id="lead-source" className="input" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}>
                {Object.entries(SOURCES).filter(([k]) => k !== "import").map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></div>
            <div className="sm:col-span-2"><label className="label" htmlFor="lead-notes">Notes for the caller</label>
              <textarea id="lead-notes" className="input min-h-24 rounded-3xl" placeholder="What they do, why they might need MME-AI…" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
            {msg?.error && <p className="alert-error sm:col-span-2">{msg.text}</p>}
            <div className="flex justify-end gap-2 sm:col-span-2">
              <button type="button" className="btn" onClick={() => setForm(null)}>Cancel</button>
              <button className="btn-primary" disabled={busy === "add"}>Add lead</button>
            </div>
          </form>
        </Modal>
      )}

      {paste !== null && (
        <Modal title="Paste a list of leads" onClose={() => setPaste(null)} wide>
          <p className="text-sm text-ink-soft">Copy rows from Excel or Google Sheets and paste them here. Columns in this order: <b className="font-medium text-ink">Name, Company, Phone, Email, City</b>. Leads whose phone or email is already in MME OS are skipped.</p>
          <textarea className="input min-h-48 rounded-3xl font-mono text-xs" aria-label="Pasted rows" value={paste} onChange={(e) => setPaste(e.target.value)}
            placeholder={"Asha Rao\tRao Realty\t+91 98765 43210\tasha@raorealty.in\tPune"} />
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm text-ink-soft">{parseRows(paste).length} lead(s) found</span>
            <div className="flex gap-2">
              <button className="btn" onClick={() => setPaste(null)}>Cancel</button>
              <button className="btn-primary" disabled={!parseRows(paste).length || busy === "import"} onClick={() => act(async () => {
                const r = await api.post<{ created: number; skipped: number }>("/leads/import", { leads: parseRows(paste).slice(0, 500) });
                setPaste(null); setTab("new");
                return `${r.created} lead(s) added${r.skipped ? `, ${r.skipped} skipped as duplicates` : ""}.`;
              }, "import")}>Add leads</button>
            </div>
          </div>
        </Modal>
      )}

      {reject && (
        <Modal title={`Reject ${reject.contact_name}?`} onClose={() => setReject(null)}>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); void act(async () => { await api.post(`/leads/${reject.id}/disqualify`, { reason }); setReject(null); return `${reject.contact_name} rejected.`; }, "reject"); }}>
            <label className="label" htmlFor="reject-reason">Why? (the team will see this)</label>
            <input id="reject-reason" className="input" required autoFocus value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Not a business, outside our market" />
            <div className="flex justify-end gap-2"><button type="button" className="btn" onClick={() => setReject(null)}>Cancel</button><button className="btn-primary" disabled={busy === "reject"}>Reject lead</button></div>
          </form>
        </Modal>
      )}
    </div>
  );
}
