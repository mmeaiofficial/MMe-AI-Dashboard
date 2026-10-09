"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, ChevronDown, KeyRound, Network, RefreshCw, ScrollText, Search, ShieldCheck, Smartphone, UsersRound } from "lucide-react";
import { ActivityChart, type DayPoint } from "@/components/activity-chart";
import { useSession } from "@/components/session";
import { Avatar } from "@/components/ui";
import { api, can, type Me, type Scope } from "@/lib/api";

interface AuditEvent { id: number; action: string; target_type: string | null; ip: string | null; created_at: string; }
interface Team { id: string; name: string; kind: string; }

const SCOPE_RANK: Record<Scope, number> = { own: 1, team: 2, department: 3, all: 4 };
const AREAS: Record<string, string> = {
  "admin.users": "Users", "admin.roles": "Roles", "org.employees": "People", "org.teams": "Teams", "org.departments": "Departments",
  "audit.events": "Audit log", "system.settings": "Settings", "crm.leads": "Leads", "sales.deals": "Deals", "clients.accounts": "Clients",
  "billing.subscriptions": "Billing", "work.projects": "Projects", "work.tasks": "Tasks", "hr.attendance": "Attendance", "hr.leave": "Leave",
  "automation.workflows": "Automations", "ai.agents": "AI agents", "reports.analytics": "Reports",
};
const ACTIONS: Record<string, string> = {
  "auth.login": "Signed in", "auth.login_failed": "Sign-in failed", "auth.logout": "Signed out", "auth.logout_all": "Signed out everywhere",
  "auth.mfa_enrolled": "Authenticator set up", "auth.mfa_passed": "Authenticator verified", "auth.mfa_failed": "Authenticator code rejected",
  "admin.user_created": "Account created", "admin.user_invited": "Invitation sent", "admin.user_updated": "Account updated",
  "admin.user_deactivated": "Account deactivated", "admin.user_reactivated": "Account reactivated", "admin.user_roles_changed": "Roles changed",
  "admin.super_admin_changed": "Super Admin changed", "admin.mfa_reset": "Authenticator reset", "admin.role_created": "Role created",
  "admin.role_changed": "Role edited", "admin.role_deleted": "Role deleted", "org.department_created": "Department created",
  "org.team_created": "Team created", "org.team_member_set": "Team member added", "org.team_member_removed": "Team member removed",
  "org.employee_updated": "Profile updated",
};
const actionLabel = (a: string) => ACTIONS[a] ?? a.split(".").pop()!.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const RANGES = [7, 14, 30] as const;
const dateFmt = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" });
const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const dayKey = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;

function accessAreas(me: Me) {
  const widest = new Map<string, Scope>();
  for (const [perm, scope] of Object.entries(me.permissions)) {
    const res = perm.split(".").slice(0, 2).join(".");
    const cur = widest.get(res);
    if (!cur || SCOPE_RANK[scope] > SCOPE_RANK[cur]) widest.set(res, scope);
  }
  const order = Object.keys(AREAS);
  return [...widest.entries()].sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0])).map(([res, scope]) => ({ res, label: AREAS[res] ?? res, scope }));
}

async function loadAudit(sinceDays: number): Promise<AuditEvent[]> {
  const since = Date.now() - sinceDays * 86_400_000;
  const out: AuditEvent[] = [];
  let before: number | null = null;
  for (let page = 0; page < 10; page++) {
    const qs = new URLSearchParams({ limit: "50" });
    if (before) qs.set("before_id", String(before));
    const r: { items: AuditEvent[]; next_before_id: number | null } = await api.get(`/audit-events?${qs}`);
    out.push(...r.items);
    before = r.next_before_id;
    const oldest = r.items.at(-1);
    if (!before || !oldest || new Date(oldest.created_at).getTime() < since) break;
  }
  return out;
}

export default function Home() {
  const { me, refresh } = useSession();
  const router = useRouter();
  const [people, setPeople] = useState<number | null>(null);
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [range, setRange] = useState<(typeof RANGES)[number]>(14);
  const [q, setQ] = useState("");
  const [spinning, setSpinning] = useState(false);

  const canPeople = !!me && can(me, "org.employees.view");
  const canTeams = !!me && can(me, "org.teams.view");
  const canAudit = !!me && can(me, "audit.events.view");

  useEffect(() => {
    if (canPeople) api.get<unknown[]>("/employees").then((r) => setPeople(r.length)).catch(() => setPeople(null));
    if (canTeams) api.get<Team[]>("/teams").then(setTeams).catch(() => setTeams(null));
    if (canAudit) loadAudit(30).then(setEvents).catch(() => setEvents([]));
  }, [canPeople, canTeams, canAudit]);

  const series = useMemo<DayPoint[]>(() => {
    const days: DayPoint[] = [];
    const today = new Date(); today.setHours(0, 0, 0, 0);
    for (let i = range - 1; i >= 0; i--) days.push({ day: new Date(today.getTime() - i * 86_400_000), signIns: 0, changes: 0 });
    const idx = new Map(days.map((d, i) => [dayKey(d.day), i]));
    for (const e of events ?? []) {
      const i = idx.get(dayKey(new Date(e.created_at)));
      if (i === undefined) continue;
      if (e.action.startsWith("auth.")) days[i].signIns++; else days[i].changes++;
    }
    return days;
  }, [events, range]);

  if (!me) return null;
  const first = me.full_name.split(" ")[0] || me.email;
  const name = me.full_name || me.email;
  const areas = accessAreas(me);
  const myTeams = (teams ?? []).filter((t) => me.team_ids.includes(t.id));
  const total = series.reduce((n, d) => n + d.signIns + d.changes, 0);
  const role = me.is_super_admin ? "Super Admin" : me.roles.map((r) => r.name).join(", ") || "No role yet";

  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-8">
        {/* Header */}
        <header className="flex flex-wrap items-center gap-4">
          <div className="mr-auto">
            <h1 className="text-2xl font-semibold tracking-tight">Welcome, {first}</h1>
            <p className="text-sm text-ink-soft">Your MME OS overview</p>
          </div>
          {canPeople && (
            <form role="search" className="relative w-full sm:w-72" onSubmit={(e) => { e.preventDefault(); router.push(`/employees${q ? `?q=${encodeURIComponent(q)}` : ""}`); }}>
              <Search size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
              <input aria-label="Search people" className="input py-3 pl-11" placeholder="Search people" value={q} onChange={(e) => setQ(e.target.value)} />
            </form>
          )}
          <Avatar name={name} src={me.avatar_url} size={46} className="hidden ring-4 ring-surface sm:block" />
        </header>

        {/* Profile + stats */}
        <section className="grid gap-4 lg:grid-cols-3">
          <div className="card flex flex-col lg:row-span-2">
            <div className="flex items-center justify-between">
              <h2 className="font-medium">Profile</h2>
              <button className="grid h-9 w-9 place-items-center rounded-full text-ink-soft hover:bg-canvas" aria-label="Refresh profile"
                onClick={async () => { setSpinning(true); await refresh(); setSpinning(false); }}>
                <RefreshCw size={18} className={spinning ? "animate-spin" : ""} />
              </button>
            </div>
            <div className="mx-auto mt-4 grid place-items-center">
              <div className="relative rounded-full p-1.5 ring-2 ring-brand">
                <Avatar name={name} src={me.avatar_url} size={96} />
                {me.mfa.enrolled && (
                  <span className="absolute bottom-0 right-0 grid h-8 w-8 place-items-center rounded-full bg-brand-fill text-on-brand ring-4 ring-surface" title="Authenticator on">
                    <ShieldCheck size={15} aria-label="Authenticator on" />
                  </span>
                )}
              </div>
            </div>
            <div className="mt-4 text-center">
              <div className="text-xl font-medium">{name}</div>
              <div className="text-sm text-ink-soft">{role}</div>
            </div>
            <dl className="mt-auto grid grid-cols-3 gap-2 pt-6 text-sm">
              {[
                { icon: Network, n: me.team_ids.length, label: "Teams", color: "text-brand" },
                { icon: KeyRound, n: me.is_super_admin ? "All" : me.roles.length, label: "Roles", color: "text-brand-text" },
                { icon: ShieldCheck, n: areas.length, label: "Areas", color: "text-brand" },
              ].map(({ icon: Icon, n, label, color }) => (
                <div key={label} className="flex flex-col items-center rounded-3xl bg-surface px-2 py-2.5 ring-1 ring-border">
                  <dt className="order-last text-[11px] text-ink-faint">{label}</dt>
                  <dd className="flex items-center gap-1.5 font-medium tabular-nums"><Icon size={15} className={color} aria-hidden="true" />{n}</dd>
                </div>
              ))}
            </dl>
          </div>

          <StatCard tone="solid" title={canPeople ? "People" : "Your teams"} caption={canPeople ? "In your access scope" : "Teams you belong to"}
            value={canPeople ? people : me.team_ids.length} icon={UsersRound} href={canPeople ? "/employees" : undefined} />
          <StatCard tone="soft" title={canTeams ? "Teams" : "Access areas"} caption={canTeams ? "Across the organization you can see" : "Parts of MME OS you can use"}
            value={canTeams ? teams?.length ?? null : areas.length} icon={Network} href={canTeams ? "/teams" : undefined} />

          <div className="card-well flex flex-wrap items-center gap-4 lg:col-span-2">
            <div className="mr-auto">
              <h2 className="font-medium">Account security</h2>
              <p className="text-sm text-ink-soft">Google sign-in · {me.mfa.enrolled ? "authenticator on" : me.mfa.required ? "authenticator required" : "authenticator optional"}</p>
            </div>
            <div className="flex -space-x-2">
              {[{ icon: KeyRound, label: "Google sign-in", on: true }, { icon: Smartphone, label: "Authenticator app", on: me.mfa.enrolled }, { icon: ShieldCheck, label: "Session verified", on: me.mfa.passed || !me.mfa.required }].map(({ icon: Icon, label, on }) => (
                <span key={label} title={`${label}: ${on ? "on" : "off"}`} className={`grid h-12 w-12 place-items-center rounded-full bg-surface ring-4 ring-well ${on ? "text-brand-text" : "text-ink-faint"}`}>
                  <Icon size={20} aria-label={`${label}: ${on ? "on" : "off"}`} />
                </span>
              ))}
            </div>
            <span className={me.mfa.enrolled || !me.mfa.required ? "pill-good" : "pill-warn"}>
              {me.mfa.enrolled || !me.mfa.required
                ? <><ShieldCheck size={12} className="mr-1" aria-hidden="true" />Protected</>
                : <><Smartphone size={12} className="mr-1" aria-hidden="true" />Action needed</>}
            </span>
          </div>
        </section>

        {/* Activity */}
        {canAudit && (
          <section>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="text-xl font-medium">Activity</h2>
                <p className="text-sm text-ink-soft">Audit events per day</p>
              </div>
              <label className="relative flex items-center gap-1 rounded-full bg-surface py-2.5 pl-4 pr-9 text-sm ring-1 ring-border">
                <span className="text-ink-soft">Range:</span>
                <select className="appearance-none bg-transparent font-medium focus:outline-none" value={range} onChange={(e) => setRange(Number(e.target.value) as (typeof RANGES)[number])}>
                  {RANGES.map((r) => <option key={r} value={r}>Last {r} days</option>)}
                </select>
                <ChevronDown size={16} className="pointer-events-none absolute right-3.5 text-ink-soft" aria-hidden="true" />
              </label>
            </div>
            <div className="mt-4">
              {events === null ? <div className="h-[260px] rounded-4xl bg-well" /> : (
                <ActivityChart data={series} aside={
                  <div className="text-right">
                    <div className="text-5xl font-medium tracking-tight tabular-nums">{total}</div>
                    <div className="text-sm text-ink-soft">Events, last {range} days</div>
                  </div>
                } />
              )}
            </div>
          </section>
        )}
      </div>

      {/* Right panel */}
      <aside className="card h-fit space-y-10 xl:sticky xl:top-8">
        {canAudit ? (
          <section>
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-medium">Recent activity</h2>
              <Link href="/audit" className="btn-icon" aria-label="Open audit log"><ScrollText size={18} /></Link>
            </div>
            <ul className="mt-4 divide-y divide-well">
              {(events ?? []).slice(0, 4).map((e) => {
                const at = new Date(e.created_at);
                return (
                  <li key={e.id} className="grid grid-cols-[88px_1fr_auto] gap-3 py-4">
                    <div className="text-xs text-ink-soft">{dateFmt.format(at)}<div className="mt-1 text-sm font-medium text-ink">{timeFmt.format(at)}</div></div>
                    <div className="min-w-0">
                      <div className="truncate font-medium">{actionLabel(e.action)}</div>
                      <div className="mt-1 flex items-center gap-1.5 truncate text-xs text-ink-soft">
                        <span className={`h-2 w-2 rounded-full ${e.action.startsWith("auth.") ? "bg-[rgb(var(--series-1))]" : "bg-[rgb(var(--series-2))]"}`} aria-hidden="true" />
                        {e.target_type ? e.target_type.replace(/_/g, " ") : "account"}{e.ip ? ` · ${e.ip}` : ""}
                      </div>
                    </div>
                    <Link href="/audit" aria-label={`Open ${actionLabel(e.action)} in the audit log`} className="text-ink-soft hover:text-brand-text"><ArrowUpRight size={18} /></Link>
                  </li>
                );
              })}
              {events !== null && events.length === 0 && <li className="py-4 text-sm text-ink-soft">No activity yet.</li>}
              {events === null && [0, 1, 2].map((i) => <li key={i} className="my-3 h-12 rounded-2xl bg-well" />)}
            </ul>
            <Link href="/audit" className="mt-1 inline-flex items-center gap-1 pl-[100px] text-sm text-ink-soft hover:text-brand-text">See all activity <ArrowUpRight size={14} /></Link>
          </section>
        ) : (
          <section>
            <h2 className="text-xl font-medium">Your teams</h2>
            <ul className="mt-4 divide-y divide-well">
              {myTeams.map((t) => <li key={t.id} className="flex items-center justify-between py-3"><span className="font-medium">{t.name}</span><span className="pill">{t.kind.replace(/_/g, " ")}</span></li>)}
              {myTeams.length === 0 && <li className="py-3 text-sm text-ink-soft">{me.team_ids.length ? `${me.team_ids.length} team(s)` : "You're not on a team yet."}</li>}
            </ul>
          </section>
        )}

        <section>
          <h2 className="text-xl font-medium">Your access</h2>
          <p className="text-sm text-ink-soft">How far each area reaches: own, team, department or all</p>
          <ul className="mt-5 space-y-4">
            {areas.slice(0, 7).map((a) => (
              <li key={a.res} className="grid grid-cols-[112px_1fr_44px] items-center gap-3">
                <span className="truncate font-medium">{a.label}</span>
                <span className="h-1.5 overflow-hidden rounded-full bg-well" role="meter" aria-label={`${a.label} access`} aria-valuemin={1} aria-valuemax={4} aria-valuenow={SCOPE_RANK[a.scope]} aria-valuetext={a.scope}>
                  <span className="block h-full rounded-full bg-brand" style={{ width: `${SCOPE_RANK[a.scope] * 25}%` }} />
                </span>
                <span className="text-right text-xs text-ink-soft">{a.scope === "department" ? "dept." : a.scope}</span>
              </li>
            ))}
            {areas.length === 0 && <li className="text-sm text-ink-soft">No access yet. A Super Admin assigns your role.</li>}
          </ul>
          {areas.length > 7 && (
            can(me, "admin.roles.view")
              ? <Link href="/admin/roles" className="mt-4 inline-flex items-center gap-1 text-sm text-ink-soft hover:text-brand-text">+{areas.length - 7} more areas <ArrowUpRight size={14} /></Link>
              : <p className="mt-4 text-sm text-ink-soft">+{areas.length - 7} more areas</p>
          )}
        </section>
      </aside>
    </div>
  );
}

function StatCard({ tone, title, caption, value, icon: Icon, href }: {
  tone: "solid" | "soft"; title: string; caption: string; value: number | null; icon: typeof UsersRound; href?: string;
}) {
  // Two flat cards: one solid brand color, one solid pale tint. No gradients.
  const solid = tone === "solid";
  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <h2 className="max-w-[8rem] text-lg font-medium leading-snug">{title}</h2>
        <span className={`grid h-11 w-11 place-items-center rounded-2xl ${solid ? "bg-on-brand text-brand-fill" : "bg-surface text-ink"}`}>
          {href ? <ArrowUpRight size={20} aria-hidden="true" /> : <Icon size={20} aria-hidden="true" />}
        </span>
      </div>
      <div className="mt-8 lg:mt-16">
        <div className="text-6xl font-medium tracking-tight tabular-nums">{value ?? "—"}</div>
        <div className={`mt-1 text-sm ${solid ? "text-on-brand" : "text-ink-soft"}`}>{caption}</div>
      </div>
    </>
  );
  const cls = `block rounded-4xl p-6 transition ${solid ? "bg-brand-fill text-on-brand hover:bg-brand-ink" : "bg-well text-ink ring-1 ring-border hover:ring-brand"}`;
  return href ? <Link href={href} className={cls}>{body}</Link> : <div className={cls}>{body}</div>;
}
