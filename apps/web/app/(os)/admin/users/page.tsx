"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "@/components/session";
import { api, ApiError, can } from "@/lib/api";

interface UserRow { id: string; email: string; full_name: string; status: string; is_super_admin: boolean; roles: string[]; last_login_at: string | null; }
interface RoleRow { id: string; key: string; name: string; }

export default function UsersPage() {
  const { me } = useSession();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [roleId, setRoleId] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [picked, setPicked] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      setUsers(await api.get<UserRow[]>("/admin/users"));
      setRoles(await api.get<RoleRow[]>("/admin/roles"));
    } catch (e) { setMsg((e as ApiError).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  if (!me) return null;
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    try { await fn(); setMsg(ok); await load(); } catch (e) { setMsg((e as ApiError).message); }
  };

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-2xl font-semibold">Users and access</h1>
      {msg && <p role="status" className="rounded-lg bg-slate-100 px-3 py-2 text-sm">{msg}</p>}

      {can(me, "admin.users.create") && (
        <section className="card space-y-3">
          <h2 className="font-semibold">Invite an employee</h2>
          <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); void run(async () => {
              const r = await api.post<{ accept_path: string }>("/admin/invitations", { email, role_ids: roleId ? [roleId] : [] });
              setLink(window.location.origin + r.accept_path); setEmail("");
            }, "Invitation created. Send the link below to the person."); }}>
            <div className="min-w-64 flex-1"><label className="label" htmlFor="inv-email">Google account email</label>
              <input id="inv-email" className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
            <div><label className="label" htmlFor="inv-role">Role</label>
              <select id="inv-role" className="input" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
                <option value="">Employee (base)</option>
                {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select></div>
            <button className="btn-primary">Create invitation</button>
          </form>
          {link && <p className="break-all rounded-lg bg-slate-100 p-3 font-mono text-xs">{link}</p>}
        </section>
      )}

      <section className="card overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="p-3">Person</th><th className="p-3">Roles</th><th className="p-3">Status</th><th className="p-3">Last sign-in</th><th className="p-3"></th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-slate-100">
                <td className="p-3"><div className="font-medium">{u.full_name || u.email}</div><div className="text-xs text-slate-500">{u.email}</div></td>
                <td className="p-3">{u.is_super_admin && <span className="pill mr-1 bg-brand-soft text-brand">super admin</span>}{u.roles.map((r) => <span key={r} className="pill mr-1">{r}</span>)}</td>
                <td className="p-3">{u.status === "active" ? <span className="pill bg-emerald-50 text-emerald-700">active</span> : <span className="pill bg-red-50 text-red-700">deactivated</span>}</td>
                <td className="p-3 text-xs text-slate-500">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}</td>
                <td className="space-x-2 whitespace-nowrap p-3 text-right">
                  {u.id !== me.id && can(me, "admin.roles.manage") && <button className="btn" onClick={() => { setEditing(u); setPicked(roles.filter((r) => u.roles.includes(r.key)).map((r) => r.id)); }}>Roles</button>}
                  {u.id !== me.id && can(me, "admin.users.edit") && (u.status === "active"
                    ? <button className="btn" onClick={() => run(() => api.patch(`/admin/users/${u.id}`, { status: "deactivated" }), "Deactivated. Their sessions have ended.")}>Deactivate</button>
                    : <button className="btn" onClick={() => run(() => api.patch(`/admin/users/${u.id}`, { status: "active" }), "Reactivated.")}>Reactivate</button>)}
                  {u.id !== me.id && me.is_super_admin && (
                    <button className="btn" onClick={() => run(() => api.put(`/admin/users/${u.id}/super-admin`, { is_super_admin: !u.is_super_admin }),
                      u.is_super_admin ? "Super Admin removed." : "Now a Super Admin. They must set up MFA at next sign-in.")}>
                      {u.is_super_admin ? "Remove super admin" : "Make super admin"}
                    </button>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {editing && (
        <div className="fixed inset-0 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true">
          <div className="card w-full max-w-md space-y-3">
            <h3 className="font-semibold">Roles for {editing.full_name || editing.email}</h3>
            {roles.map((r) => (
              <label key={r.id} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={picked.includes(r.id)} onChange={(e) => setPicked(e.target.checked ? [...picked, r.id] : picked.filter((x) => x !== r.id))} />
                {r.name}
              </label>
            ))}
            <div className="flex justify-end gap-2">
              <button className="btn" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn-primary" onClick={() => { const u = editing; setEditing(null); void run(() => api.put(`/admin/users/${u.id}/roles`, { role_ids: picked }), "Roles updated."); }}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
