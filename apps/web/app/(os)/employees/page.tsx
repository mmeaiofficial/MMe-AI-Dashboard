"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

interface Emp { user_id: string; email: string; full_name: string; status: string; designation: string | null; employment_type: string | null; location: string | null; }

export default function EmployeesPage() {
  const [rows, setRows] = useState<Emp[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => {
    setQ(new URLSearchParams(window.location.search).get("q") ?? "");
    api.get<Emp[]>("/employees").then(setRows).catch((e) => setMsg((e as ApiError).message));
  }, []);
  const shown = rows.filter((r) => (r.full_name + r.email + (r.designation || "")).toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="max-w-5xl space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">People</h1>
      <p className="text-sm text-ink-soft">You see the people inside your access scope (for most roles, your own teams).</p>
      {msg && <p role="status" className="text-sm">{msg}</p>}
      <input aria-label="Search people" className="input max-w-sm" placeholder="Search by name, email or designation" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="thead"><tr><th className="px-5 py-3 font-medium">Name</th><th className="px-5 py-3 font-medium">Designation</th><th className="px-5 py-3 font-medium">Type</th><th className="px-5 py-3 font-medium">Location</th><th className="px-5 py-3 font-medium">Status</th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.user_id} className="border-t border-well">
                <td className="px-5 py-3.5"><div className="font-medium">{r.full_name || r.email}</div><div className="text-xs text-ink-soft">{r.email}</div></td>
                <td className="px-5 py-3.5">{r.designation || "—"}</td>
                <td className="px-5 py-3.5">{r.employment_type?.replace("_", " ") || "—"}</td>
                <td className="px-5 py-3.5">{r.location || "—"}</td>
                <td className="px-5 py-3.5"><span className="pill">{r.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
