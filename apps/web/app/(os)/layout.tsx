"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SessionProvider, useSession } from "@/components/session";
import { can } from "@/lib/api";

const NAV: { href: string; label: string; perm?: string; group: string }[] = [
  { href: "/", label: "Home", group: "Work" },
  { href: "/employees", label: "People", perm: "org.employees.view", group: "Organization" },
  { href: "/teams", label: "Teams", perm: "org.teams.view", group: "Organization" },
  { href: "/admin/users", label: "Users and access", perm: "admin.users.view", group: "Super Admin" },
  { href: "/admin/roles", label: "Roles and permissions", perm: "admin.roles.view", group: "Super Admin" },
  { href: "/audit", label: "Audit log", perm: "audit.events.view", group: "Super Admin" },
];

function Shell({ children }: { children: React.ReactNode }) {
  const { me, loading, signOut } = useSession();
  const path = usePathname();
  if (loading || !me) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  const items = NAV.filter((n) => !n.perm || can(me, n.perm));
  const groups = [...new Set(items.map((i) => i.group))];
  return (
    <div className="grid min-h-screen md:grid-cols-[240px_1fr]">
      <aside className="border-b border-slate-200 bg-white p-4 md:border-b-0 md:border-r">
        <div className="mb-5 flex items-center gap-2 font-semibold"><span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-sm text-white">M</span>MME OS</div>
        <nav className="space-y-4">
          {groups.map((g) => (
            <div key={g}>
              <div className="label mb-1 px-2">{g}</div>
              {items.filter((i) => i.group === g).map((i) => (
                <Link key={i.href} href={i.href}
                  className={`block rounded-lg px-2 py-1.5 text-sm ${path === i.href ? "bg-brand-soft font-medium text-brand" : "text-slate-600 hover:bg-slate-100"}`}>
                  {i.label}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="mt-8 border-t border-slate-200 pt-4 text-sm">
          <div className="font-medium">{me.full_name || me.email}</div>
          <div className="text-xs text-slate-500">{me.is_super_admin ? "Super Admin" : me.roles.map((r) => r.name).join(", ") || "No role yet"}</div>
          <button className="mt-2 text-xs text-slate-500 underline" onClick={signOut}>Sign out</button>
        </div>
      </aside>
      <main className="min-w-0 p-6">{children}</main>
    </div>
  );
}

export default function OsLayout({ children }: { children: React.ReactNode }) {
  return <SessionProvider><Shell>{children}</Shell></SessionProvider>;
}
