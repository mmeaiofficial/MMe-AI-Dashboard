"use client";

import Link from "next/link";
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
      <h1 className="text-2xl font-semibold tracking-tight">Users and access</h1>
      {msg && <p role="status" className="rounded-2xl bg-surface px-4 py-3 text-sm ring-1 ring-border">{msg}</p>}

      <p className="rounded-2xl bg-surface px-4 py-3 text-sm ring-1 ring-border">
        To add someone or change their job, team or screens, use <Link href="/admin/roles" className="font-medium text-brand-text underline">Roles and permissions</Link>. This page is for account status, Super Admins and authenticator resets.
      </p>

      <section className="card overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="thead">
            <tr><th className="px-5 py-3 font-medium">Person</th><th className="px-5 py-3 font-medium">Roles</th><th className="px-5 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">Last sign-in</th><th className="px-5 py-3 font-medium"></th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-well">
                <td className="px-5 py-3.5"><div className="font-medium">{u.full_name || u.email}</div><div className="text-xs text-ink-soft">{u.email}</div></td>
                <td className="px-5 py-3.5">{u.is_super_admin && <span className="pill-brand mr-1">super admin</span>}{u.roles.map((r) => <span key={r} className="pill mr-1">{r}</span>)}</td>
                <td className="px-5 py-3.5">{u.status === "active" ? <span className="pill-good">active</span> : <span className="pill-bad">deactivated</span>}</td>
                <td className="px-5 py-3.5 text-xs text-ink-soft">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}</td>
                <td className="space-x-2 whitespace-nowrap px-5 py-3.5 text-right">
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
        <div className="fixed inset-0 grid place-items-center bg-canvas p-4" role="dialog" aria-modal="true">
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
