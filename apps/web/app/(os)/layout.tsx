"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarClock, House, KeyRound, LogOut, Network, PhoneCall, ScrollText, ShieldCheck, Target, Ticket, UsersRound, type LucideIcon } from "lucide-react";
import { RekhaMark, RekhaProvider, useRekha } from "@/components/rekha";
import { SessionProvider, useSession } from "@/components/session";
import { ThemeToggle } from "@/components/theme";
import { Avatar, LogoMark } from "@/components/ui";
import { can } from "@/lib/api";

const NAV: { href: string; label: string; icon: LucideIcon; perm?: string; group: string }[] = [
  { href: "/", label: "Home", icon: House, group: "Work" },
  { href: "/leads", label: "Leads", icon: Target, perm: "crm.leads.view", group: "Pipeline" },
  { href: "/calls", label: "Cold calls", icon: PhoneCall, perm: "sales.calls.view", group: "Pipeline" },
  { href: "/meetings", label: "Meetings", icon: CalendarClock, perm: "sales.deals.view", group: "Pipeline" },
  { href: "/tickets", label: "Tickets", icon: Ticket, perm: "work.tasks.view", group: "Pipeline" },
  { href: "/employees", label: "People", icon: UsersRound, perm: "org.employees.view", group: "Organization" },
  { href: "/teams", label: "Teams", icon: Network, perm: "org.teams.view", group: "Organization" },
  { href: "/admin/users", label: "Users and access", icon: ShieldCheck, perm: "admin.users.view", group: "Super Admin" },
  { href: "/admin/roles", label: "Roles and permissions", icon: KeyRound, perm: "admin.roles.view", group: "Super Admin" },
  { href: "/audit", label: "Audit log", icon: ScrollText, perm: "audit.events.view", group: "Super Admin" },
];

function Shell({ children }: { children: React.ReactNode }) {
  const { me, loading, signOut } = useSession();
  const path = usePathname();
  if (loading || !me) {
    return <div className="grid min-h-screen place-items-center"><span className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-brand" aria-label="Loading" /></div>;
  }
  const items = NAV.filter((n) => !n.perm || can(me, n.perm));
  const groups = [...new Set(items.map((i) => i.group))];
  const name = me.full_name || me.email;
  return (
    <RekhaProvider>
      <div className="min-h-screen md:grid md:grid-cols-[260px_1fr]">
        <aside className="md:sticky md:top-0 md:h-screen md:p-4 md:pr-0">
          <div className="flex h-full flex-col bg-surface px-4 py-4 ring-1 ring-border md:rounded-4xl md:py-6">
            <div className="mb-4 flex items-center justify-between md:mb-8">
              <Link href="/" className="flex items-center gap-3 px-2">
                <LogoMark size={40} />
                <span className="leading-tight"><span className="block font-semibold">MME OS</span><span className="block text-xs text-ink-faint">Business OS</span></span>
              </Link>
              <div className="flex gap-2 md:hidden">
                <ThemeToggle compact />
                <button className="btn-icon" onClick={signOut} aria-label="Sign out"><LogOut size={16} /></button>
              </div>
            </div>
            <nav className="-mx-1 flex gap-1 overflow-x-auto px-1 md:mx-0 md:flex-1 md:flex-col md:gap-5 md:overflow-visible md:px-0">
              {groups.map((g) => (
                <div key={g} className="flex gap-1 md:flex-col">
                  <div className="mb-1 hidden px-3 text-[11px] font-medium uppercase tracking-wider text-ink-faint md:block">{g}</div>
                  {items.filter((i) => i.group === g).map((i) => {
                    const active = i.href === "/" ? path === "/" : path.startsWith(i.href);
                    const Icon = i.icon;
                    return (
                      <Link key={i.href} href={i.href} aria-current={active ? "page" : undefined}
                        className={`flex shrink-0 items-center gap-3 rounded-full px-3 py-2 text-sm transition ${active ? "bg-brand-fill font-medium text-on-brand ring-1 ring-border" : "text-ink-soft hover:bg-canvas hover:text-ink"}`}>
                        <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                        <span className="whitespace-nowrap">{i.label}</span>
                      </Link>
                    );
                  })}
                  {g === "Work" && <RekhaNavButton />}
                </div>
              ))}
            </nav>
            <div className="mt-6 hidden md:block"><ThemeToggle /></div>
            <div className="mt-3 hidden items-center gap-3 rounded-3xl bg-canvas p-3 md:flex">
              <Avatar name={name} src={me.avatar_url} size={38} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{name}</div>
                <div className="truncate text-xs text-ink-faint">{me.is_super_admin ? "Super Admin" : me.roles.map((r) => r.name).join(", ") || "No role yet"}</div>
              </div>
              <button className="grid h-8 w-8 place-items-center rounded-full text-ink-soft hover:bg-surface hover:text-ink" onClick={signOut} aria-label="Sign out" title="Sign out">
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </aside>
        <main className="min-w-0 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </RekhaProvider>
  );
}

function RekhaNavButton() {
  const { open, setOpen } = useRekha();
  return (
    <button onClick={() => setOpen(!open)} aria-expanded={open}
      className={`flex shrink-0 items-center gap-3 rounded-full py-1.5 pl-1.5 pr-3 text-sm transition ${open ? "bg-brand-soft font-medium text-brand-text" : "text-ink-soft hover:bg-canvas hover:text-ink"}`}>
      <RekhaMark size={26} />
      <span className="whitespace-nowrap">Ask Rekha</span>
    </button>
  );
}

export default function OsLayout({ children }: { children: React.ReactNode }) {
  return <SessionProvider><Shell>{children}</Shell></SessionProvider>;
}
