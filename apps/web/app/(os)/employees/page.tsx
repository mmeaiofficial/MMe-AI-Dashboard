"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

interface Emp { user_id: string; email: string; full_name: string; status: string; designation: string | null; employment_type: string | null; location: string | null; }

export default function EmployeesPage() {
  const [rows, setRows] = useState<Emp[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => { api.get<Emp[]>("/employees").then(setRows).catch((e) => setMsg((e as ApiError).message)); }, []);
  const shown = rows.filter((r) => (r.full_name + r.email + (r.designation || "")).toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="max-w-5xl space-y-4">
      <h1 className="text-2xl font-semibold">People</h1>
      <p className="text-sm text-slate-600">You see the people inside your access scope (for most roles, your own teams).</p>
      {msg && <p role="status" className="text-sm">{msg}</p>}
      <input aria-label="Search people" className="input max-w-sm" placeholder="Search by name, email or designation" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="p-3">Name</th><th className="p-3">Designation</th><th className="p-3">Type</th><th className="p-3">Location</th><th className="p-3">Status</th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.user_id} className="border-t border-slate-100">
                <td className="p-3"><div className="font-medium">{r.full_name || r.email}</div><div className="text-xs text-slate-500">{r.email}</div></td>
                <td className="p-3">{r.designation || "—"}</td>
                <td className="p-3">{r.employment_type?.replace("_", " ") || "—"}</td>
                <td className="p-3">{r.location || "—"}</td>
                <td className="p-3"><span className="pill">{r.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
