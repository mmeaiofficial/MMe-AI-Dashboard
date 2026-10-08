"use client";

import { useSession } from "@/components/session";

export default function Home() {
  const { me } = useSession();
  if (!me) return null;
  const perms = Object.entries(me.permissions);
  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Welcome, {me.full_name.split(" ")[0] || me.email}</h1>
        <p className="text-sm text-slate-600">Milestone 1 is live: sign-in, teams, people and access control. Work, HR and revenue modules arrive in the next milestones.</p>
      </div>
      <section className="card">
        <h2 className="mb-3 font-semibold">What you can access</h2>
        {perms.length === 0 ? (
          <p className="text-sm text-slate-500">No permissions yet. A Super Admin assigns your role.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {perms.map(([p, s]) => <span key={p} className="pill">{p} · {s}</span>)}
          </div>
        )}
      </section>
    </div>
  );
}
