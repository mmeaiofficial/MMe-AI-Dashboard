"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "@/components/session";
import { api, ApiError, Scope } from "@/lib/api";

interface Grant { permission: string; scope: Scope; }
interface Role { id: string; key: string; name: string; description: string; is_system: boolean; grants: Grant[]; }
interface Catalog { resources: { key: string; label: string }[]; actions: string[]; scopes: Scope[]; }

export default function RolesPage() {
  const { me } = useSession();
  const [roles, setRoles] = useState<Role[]>([]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, Scope | "">>({});
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, c] = await Promise.all([api.get<Role[]>("/admin/roles"), api.get<Catalog>("/admin/permissions")]);
      setRoles(r); setCatalog(c); setSelected((s) => s ?? r[0]?.id ?? null);
    } catch (e) { setMsg((e as ApiError).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const role = useMemo(() => roles.find((r) => r.id === selected) || null, [roles, selected]);
  useEffect(() => { setDraft(Object.fromEntries((role?.grants || []).map((g) => [g.permission, g.scope]))); }, [role]);

  if (!me || !catalog) return msg ? <p className="text-sm">{msg}</p> : null;
  const editable = me.is_super_admin;

  async function save() {
    if (!role) return;
    setMsg(null);
    const grants = Object.entries(draft).filter(([, s]) => s).map(([permission, scope]) => ({ permission, scope }));
    try {
      await api.put(`/admin/roles/${role.id}`, { key: role.key, name: role.name, description: role.description, grants });
      setMsg("Saved. Changes apply on each person's next request.");
      await load();
    } catch (e) { setMsg((e as ApiError).message); }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Roles and permissions</h1>
      <p className="max-w-3xl text-sm text-slate-600">Each cell sets how far a role reaches: <b>own</b> (records they own or are assigned), <b>team</b>, <b>department</b> or <b>all</b>. Empty means no access. The API enforces this on every request; nobody can edit a role they hold.</p>
      {msg && <p role="status" className="rounded-lg bg-slate-100 px-3 py-2 text-sm">{msg}</p>}
      <div className="flex flex-wrap gap-2">
        {roles.map((r) => (
          <button key={r.id} onClick={() => setSelected(r.id)} className={`btn ${r.id === selected ? "border-brand text-brand" : ""}`}>{r.name}</button>
        ))}
      </div>
      {role && (
        <section className="card overflow-x-auto p-0">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="p-3">Area</th>{catalog.actions.map((a) => <th key={a} className="p-3">{a}</th>)}</tr>
            </thead>
            <tbody>
              {catalog.resources.map((res) => (
                <tr key={res.key} className="border-t border-slate-100">
                  <td className="p-3"><div className="font-medium">{res.label}</div><div className="font-mono text-xs text-slate-400">{res.key}</div></td>
                  {catalog.actions.map((a) => {
                    const p = `${res.key}.${a}`;
                    return (
                      <td key={a} className="p-2">
                        <select aria-label={`${res.label} ${a}`} className="input px-1 py-1 text-xs" disabled={!editable}
                          value={draft[p] || ""} onChange={(e) => setDraft({ ...draft, [p]: e.target.value as Scope | "" })}>
                          <option value="">—</option>
                          {catalog.scopes.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {editable && role && <button className="btn-primary" onClick={save}>Save {role.name}</button>}
    </div>
  );
}
