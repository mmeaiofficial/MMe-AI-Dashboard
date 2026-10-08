"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "@/components/session";
import { api, ApiError, can } from "@/lib/api";

interface Team { id: string; name: string; kind: string; members?: { user_id: string; full_name: string; email: string; is_manager: boolean }[]; }
interface Person { user_id: string; full_name: string; email: string; }
const KINDS = [["sales", "Sales"], ["marketing", "Marketing"], ["tech", "Tech / Development"], ["ai_automation", "AI / Automation"], ["customer_success", "Customer Success"], ["finance_ops", "Finance / Operations"], ["custom", "Custom"]];

export default function TeamsPage() {
  const { me } = useSession();
  const [teams, setTeams] = useState<Team[]>([]);
  const [open, setOpen] = useState<Team | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("custom");
  const [addId, setAddId] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setTeams(await api.get<Team[]>("/teams")); setPeople(await api.get<Person[]>("/employees")); } catch (e) { setMsg((e as ApiError).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const openTeam = async (id: string) => { try { setOpen(await api.get<Team>(`/teams/${id}`)); } catch (e) { setMsg((e as ApiError).message); } };
  if (!me) return null;
  const editable = can(me, "org.teams.edit");

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-2xl font-semibold">Teams</h1>
      {msg && <p role="status" className="rounded-lg bg-slate-100 px-3 py-2 text-sm">{msg}</p>}
      {can(me, "org.teams.create") && (
        <form className="card flex flex-wrap items-end gap-3" onSubmit={async (e) => { e.preventDefault(); try { await api.post("/teams", { name, kind }); setName(""); await load(); } catch (err) { setMsg((err as ApiError).message); } }}>
          <div className="min-w-56 flex-1"><label className="label" htmlFor="t-name">New team</label><input id="t-name" className="input" required value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div><label className="label" htmlFor="t-kind">Type</label><select id="t-kind" className="input" value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
          <button className="btn-primary">Create team</button>
        </form>
      )}
      <div className="grid gap-4 md:grid-cols-[280px_1fr]">
        <div className="card space-y-1 p-2">
          {teams.length === 0 && <p className="p-3 text-sm text-slate-500">No teams yet.</p>}
          {teams.map((t) => (
            <button key={t.id} onClick={() => openTeam(t.id)} className={`block w-full rounded-lg px-3 py-2 text-left text-sm ${open?.id === t.id ? "bg-brand-soft text-brand" : "hover:bg-slate-100"}`}>
              {t.name}<span className="ml-2 text-xs text-slate-400">{t.kind}</span>
            </button>
          ))}
        </div>
        {open && (
          <div className="card space-y-3">
            <h2 className="font-semibold">{open.name}</h2>
            <ul className="divide-y divide-slate-100 text-sm">
              {(open.members || []).map((m) => (
                <li key={m.user_id} className="flex items-center justify-between py-2">
                  <span>{m.full_name || m.email}{m.is_manager && <span className="pill ml-2">manager</span>}</span>
                  {editable && <button className="text-xs text-slate-500 underline" onClick={async () => { await api.del(`/teams/${open.id}/members/${m.user_id}`); await openTeam(open.id); }}>Remove</button>}
                </li>
              ))}
            </ul>
            {editable && (
              <div className="flex gap-2">
                <select aria-label="Add member" className="input" value={addId} onChange={(e) => setAddId(e.target.value)}>
                  <option value="">Add a person…</option>
                  {people.filter((p) => !(open.members || []).some((m) => m.user_id === p.user_id)).map((p) => <option key={p.user_id} value={p.user_id}>{p.full_name || p.email}</option>)}
                </select>
                <button className="btn" disabled={!addId} onClick={async () => { await api.put(`/teams/${open.id}/members`, { user_id: addId }); setAddId(""); await openTeam(open.id); }}>Add</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
