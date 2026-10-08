"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

interface Ev { id: number; action: string; actor_user_id: string | null; target_type: string | null; target_id: string | null; before: unknown; after: unknown; ip: string | null; created_at: string; }

export default function AuditPage() {
  const [items, setItems] = useState<Ev[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [action, setAction] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async (before?: number) => {
    try {
      const qs = new URLSearchParams({ limit: "50" });
      if (action) qs.set("action", action);
      if (before) qs.set("before_id", String(before));
      const r = await api.get<{ items: Ev[]; next_before_id: number | null }>(`/audit-events?${qs}`);
      setItems((cur) => (before ? [...cur, ...r.items] : r.items));
      setNext(r.next_before_id);
    } catch (e) { setMsg((e as ApiError).message); }
  }, [action]);
  useEffect(() => { void load(); }, [load]);

  return (
    <div className="max-w-5xl space-y-4">
      <h1 className="text-2xl font-semibold">Audit log</h1>
      <p className="text-sm text-slate-600">Every sign-in, access change and admin action. Entries can't be edited or deleted.</p>
      {msg && <p role="status" className="text-sm">{msg}</p>}
      <select aria-label="Filter by type" className="input max-w-xs" value={action} onChange={(e) => setAction(e.target.value)}>
        <option value="">All events</option><option value="auth.">Sign-in and MFA</option><option value="admin.">Access and users</option><option value="org.">Teams and people</option>
      </select>
      <div className="card divide-y divide-slate-100 p-0">
        {items.map((e) => (
          <details key={e.id} className="p-3 text-sm">
            <summary className="flex cursor-pointer flex-wrap justify-between gap-2">
              <span className="font-mono">{e.action}</span>
              <span className="text-xs text-slate-500">{new Date(e.created_at).toLocaleString()} · {e.ip || "—"}</span>
            </summary>
            <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify({ actor: e.actor_user_id, target: `${e.target_type}:${e.target_id}`, before: e.before, after: e.after }, null, 2)}</pre>
          </details>
        ))}
        {items.length === 0 && <p className="p-4 text-sm text-slate-500">No events yet.</p>}
      </div>
      {next && <button className="btn" onClick={() => load(next)}>Load older</button>}
    </div>
  );
}
