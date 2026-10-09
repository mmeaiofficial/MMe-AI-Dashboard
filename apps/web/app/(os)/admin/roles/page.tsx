"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Copy, Search, UserPlus } from "lucide-react";
import { AREAS, areaState, GROUPS, LEVELS, LIVE, setArea, type Draft } from "@/components/access";
import { useSession } from "@/components/session";
import { Avatar, Modal, PageHeader } from "@/components/ui";
import { api, ApiError, can, type Scope } from "@/lib/api";

interface Grant { permission: string; scope: Scope; }
interface Role { id: string; key: string; name: string; description: string; personal: boolean; grants: Grant[]; }
interface Team { id: string; name: string; kind: string; }
interface Feature { resource: string; level: string; reach: Scope; }
interface Person {
  kind: "user" | "invite"; id: string; email: string; name: string; status: string; is_super_admin: boolean;
  roles: { id: string; key: string; name: string; personal: boolean }[]; teams: (Team & { is_manager: boolean })[]; features: Feature[];
  expires_at?: string; last_login_at?: string | null;
}

// Plain descriptions for the default jobs, pipeline first.
const JOBS: Record<string, string> = {
  lead_generation: "Finds new leads and qualifies them",
  sales_l1: "Cold-calls leads and books meetings",
  sales_l2: "Runs meetings and closes clients",
  tech_automation: "Builds what clients need from tickets",
  marketing: "Social media, posts and campaigns",
  sales_manager: "Leads the sales teams",
  sales_executive: "Sells and follows up on their own deals",
  customer_success: "Looks after clients once they sign",
  operations_admin: "Runs day-to-day operations across teams",
  finance: "Billing, invoices and payments",
  employee: "Basic access: their own tasks, attendance and leave",
};
const JOB_ORDER = Object.keys(JOBS);
const ACTIONS = ["view", "create", "edit", "delete", "export", "approve", "manage"];
const REACH_WORDS: Record<Scope, string> = { own: "their own", team: "their team's", department: "their department's", all: "everyone's" };
const LEVEL_WORDS: Record<string, string> = { view: "view", add: "view and add", edit: "edit", full: "full", custom: "custom" };
const TEAM_FOR_JOB: Record<string, string> = { lead_generation: "lead_gen", sales_l1: "sales_l1", sales_l2: "sales_l2", tech_automation: "tech", marketing: "marketing" };

const toDraft = (grants: Grant[]): Draft => Object.fromEntries(grants.map((g) => [g.permission, g.scope]));
const widen = (d: Draft): Draft => Object.fromEntries(Object.entries(d).map(([p, s]) => [p, s === "own" ? "team" : s])) as Draft;
const same = (a: Draft, b: Draft) => JSON.stringify(Object.entries(a).sort()) === JSON.stringify(Object.entries(b).sort());

export default function AccessPage() {
  const { me } = useSession();
  const [people, setPeople] = useState<Person[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [filter, setFilter] = useState<"all" | "invited" | "active">("all");
  const [q, setQ] = useState("");
  const [msg, setMsg] = useState<{ text: string; error?: boolean; link?: string } | null>(null);
  const [form, setForm] = useState<{ email: string; locked: boolean; roleId: string; teamId: string; manager: boolean; draft: Draft; tweak: boolean } | null>(null);
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [later, setLater] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, r] = await Promise.all([api.get<{ people: Person[] }>("/admin/access"), api.get<Role[]>("/admin/roles")]);
      setPeople(a.people); setRoles(r);
    } catch (e) { setMsg({ text: (e as ApiError).message, error: true }); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (me && can(me, "org.teams.view")) api.get<Team[]>("/teams").then(setTeams).catch(() => {}); }, [me]);

  const jobs = useMemo(() => roles.filter((r) => !r.personal)
    .sort((a, b) => (JOB_ORDER.indexOf(a.key) + 1 || 99) - (JOB_ORDER.indexOf(b.key) + 1 || 99) || a.name.localeCompare(b.name)), [roles]);
  const byId = useMemo(() => Object.fromEntries(roles.map((r) => [r.id, r])), [roles]);

  if (!me) return null;
  const canGive = can(me, "admin.roles.manage");
  const shown = people.filter((p) => (filter === "all" || (filter === "invited" ? p.status === "invited" : p.status === "active"))
    && (!q || `${p.name} ${p.email} ${p.roles.map((r) => r.name).join(" ")} ${p.teams.map((t) => t.name).join(" ")}`.toLowerCase().includes(q.toLowerCase())));

  const jobDraft = (roleId: string, manager: boolean) => { const d = toDraft(byId[roleId]?.grants ?? []); return manager ? widen(d) : d; };
  const suggestTeam = (roleId: string) => teams.find((t) => t.kind === TEAM_FOR_JOB[byId[roleId]?.key])?.id ?? "";

  function openNew() {
    const first = jobs[0];
    setMsg(null); setCopied(false);
    setForm({ email: "", locked: false, roleId: first?.id ?? "", teamId: first ? suggestTeam(first.id) : "", manager: false, draft: first ? jobDraft(first.id, false) : {}, tweak: false });
  }

  function openEdit(p: Person) {
    const current = p.roles[0] ? byId[p.roles[0].id] : undefined;
    const job = current && !current.personal ? current : jobs.find((j) => current?.name.startsWith(`${j.name} (`)) ?? jobs.find((j) => j.key === "employee") ?? jobs[0];
    const team = p.teams[0];
    setMsg(null); setCopied(false);
    setForm({ email: p.email, locked: true, roleId: job?.id ?? "", teamId: team?.id ?? "", manager: !!team?.is_manager,
      draft: current ? toDraft(current.grants) : {}, tweak: !!current?.personal });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    const custom = !same(form.draft, toDraft(byId[form.roleId]?.grants ?? []));
    setSaving(true); setMsg(null);
    try {
      const r = await api.post<{ result: string; email: string; accept_path?: string }>("/admin/access", {
        email: form.email, role_id: form.roleId, team_id: form.teamId || null, team_manager: form.manager && !!form.teamId,
        grants: custom ? Object.entries(form.draft).map(([permission, scope]) => ({ permission, scope })) : null,
      });
      setForm(null);
      setMsg(r.result === "invited"
        ? { text: `Done. ${r.email} can now sign in at ${window.location.origin}/sign-in with Google using this email, and will get exactly this access.`, link: r.accept_path ? window.location.origin + r.accept_path : undefined }
        : { text: `${r.email}'s access is updated. It applies on their next click.` });
      await load();
    } catch (err) { setMsg({ text: (err as ApiError).message, error: true }); } finally { setSaving(false); }
  }

  const job = form ? byId[form.roleId] : undefined;
  const liveOn = form ? [...LIVE].filter((k) => areaState(form.draft, k, ACTIONS).level !== "off") : [];

  return (
    <div className="max-w-6xl space-y-6">
      <PageHeader title="Roles and permissions" subtitle="Give people access with their Google email: pick their job and team. They get exactly these screens when they sign in."
        actions={<div className="flex gap-2">
          {me.is_super_admin && <Link href="/admin/roles/jobs" className="btn">Edit jobs</Link>}
          {canGive && <button className="btn-primary" onClick={openNew}><UserPlus size={16} />Give someone access</button>}
        </div>} />

      {msg && (
        <div role="status" className={msg.error ? "alert-error" : "space-y-2 rounded-2xl bg-surface px-4 py-3 text-sm ring-1 ring-border"}>
          <p>{msg.text}</p>
          {msg.link && (
            <button className="btn px-3 py-1.5 text-xs" onClick={async () => { try { await navigator.clipboard.writeText(msg.link!); setCopied(true); } catch { /* clipboard blocked */ } }}>
              {copied ? <Check size={14} /> : <Copy size={14} />}{copied ? "Link copied" : "Copy invite link to send them"}
            </button>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" className="flex gap-1 rounded-full bg-well p-1">
          {([["all", "Everyone"], ["active", "Active"], ["invited", "Invited"]] as const).map(([id, label]) => (
            <button key={id} role="tab" aria-selected={filter === id} onClick={() => setFilter(id)}
              className={`rounded-full px-4 py-1.5 text-sm ${filter === id ? "bg-brand-fill font-medium text-on-brand" : "text-ink-soft hover:text-ink"}`}>
              {label} <span className="tabular-nums opacity-80">{id === "all" ? people.length : people.filter((p) => (id === "invited" ? p.status === "invited" : p.status === "active")).length}</span>
            </button>
          ))}
        </div>
        <div className="relative min-w-56 flex-1">
          <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
          <input className="input pl-10" placeholder="Search by name, email, job or team" aria-label="Search people" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      <ul className="space-y-2">
        {shown.map((p) => {
          const live = p.features.filter((f) => LIVE.has(f.resource));
          const self = p.kind === "user" && p.id === me.id;
          return (
            <li key={`${p.kind}-${p.id}`} className="card flex flex-wrap items-center gap-x-6 gap-y-3 py-4">
              <div className="flex min-w-60 flex-1 items-center gap-3">
                <Avatar name={p.name || p.email} size={38} />
                <div className="min-w-0">
                  <div className="truncate font-medium">{p.name || p.email}</div>
                  <div className="truncate text-xs text-ink-soft">{p.name ? p.email : p.status === "invited" ? "Hasn't signed in yet" : ""}</div>
                </div>
              </div>
              <div className="w-48">
                <div className="text-sm font-medium">{p.is_super_admin ? "Super Admin" : p.roles[0]?.name ?? "No job"}</div>
                <div className="text-xs text-ink-soft">{p.teams.length ? p.teams.map((t) => `${t.name}${t.is_manager ? " (manager)" : ""}`).join(", ") : "No team"}</div>
              </div>
              <div className="flex min-w-60 flex-[2] flex-wrap gap-1.5" aria-label="Can open">
                {p.is_super_admin ? <span className="pill-brand">Everything</span>
                  : live.length ? live.map((f) => <span key={f.resource} className="pill" title={`${LEVEL_WORDS[f.level]} · ${REACH_WORDS[f.reach]}`}>{AREAS[f.resource]?.[0] ?? f.resource}</span>)
                    : <span className="text-xs text-ink-faint">No screens yet</span>}
              </div>
              <div className="flex items-center gap-2">
                <span className={p.status === "active" ? "pill-good" : p.status === "invited" ? "pill-warn" : "pill"}>{p.status === "invited" ? "Invited" : p.status === "active" ? "Active" : "Deactivated"}</span>
                {canGive && !self && !(p.is_super_admin && !me.is_super_admin) && <button className="btn px-3 py-1.5 text-xs" onClick={() => openEdit(p)}>Change</button>}
                {canGive && p.kind === "invite" && (
                  <button className="btn px-3 py-1.5 text-xs" onClick={async () => {
                    try { await api.post(`/admin/access/invitations/${p.id}/revoke`); setMsg({ text: `Invitation for ${p.email} withdrawn.` }); await load(); }
                    catch (e) { setMsg({ text: (e as ApiError).message, error: true }); }
                  }}>Revoke</button>
                )}
              </div>
            </li>
          );
        })}
        {shown.length === 0 && <li className="card py-10 text-center text-sm text-ink-soft">{people.length ? "Nobody matches." : "Nobody yet. Give someone access to get started."}</li>}
      </ul>

      {form && (
        <Modal title={form.locked ? `Change access for ${form.email}` : "Give someone access"} onClose={() => setForm(null)} wide>
          <form className="space-y-5" onSubmit={submit}>
            {!form.locked && (
              <div><label className="label" htmlFor="ga-email">Their Google email</label>
                <input id="ga-email" type="email" required autoFocus className="input" placeholder="name@mme-ai.com" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                <p className="mt-1 px-1 text-xs text-ink-faint">They sign in with Google using this email. No password needed.</p></div>
            )}

            <fieldset>
              <legend className="label">Their job</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {jobs.map((j) => (
                  <label key={j.id} className={`flex cursor-pointer items-start gap-3 rounded-3xl p-3 ring-1 transition ${form.roleId === j.id ? "bg-brand-soft ring-brand" : "bg-surface ring-border hover:ring-brand"}`}>
                    <input type="radio" name="job" className="mt-1 accent-[rgb(var(--brand-fill))]" checked={form.roleId === j.id}
                      onChange={() => setForm({ ...form, roleId: j.id, teamId: suggestTeam(j.id) || form.teamId, draft: jobDraft(j.id, form.manager), tweak: false })} />
                    <span><span className="block text-sm font-medium">{j.name}</span><span className="block text-xs text-ink-soft">{JOBS[j.key] ?? j.description}</span></span>
                  </label>
                ))}
              </div>
            </fieldset>

            {teams.length > 0 && (
              <div className="grid items-end gap-3 sm:grid-cols-[1fr_auto]">
                <div><label className="label" htmlFor="ga-team">Their team</label>
                  <select id="ga-team" className="input" value={form.teamId} onChange={(e) => setForm({ ...form, teamId: e.target.value, manager: e.target.value ? form.manager : false })}>
                    <option value="">No team</option>
                    {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select></div>
                <label className={`flex items-center gap-2 rounded-full px-4 py-2.5 text-sm ring-1 ring-border ${form.teamId ? "cursor-pointer" : "opacity-50"}`}>
                  <input type="checkbox" disabled={!form.teamId} checked={form.manager} className="accent-[rgb(var(--brand-fill))]"
                    onChange={(e) => setForm({ ...form, manager: e.target.checked, draft: jobDraft(form.roleId, e.target.checked), tweak: false })} />
                  Manages this team
                </label>
              </div>
            )}
            {form.manager && <p className="-mt-3 px-1 text-xs text-ink-soft">Managers see their whole team's work (leads, calls, meetings, tickets, attendance) instead of only their own.</p>}

            <section className="rounded-3xl bg-well p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-medium">What they can open</div>
                  <div className="text-xs text-ink-soft">{liveOn.length ? liveOn.map((k) => AREAS[k][0]).join(" · ") : "Nothing yet"}</div>
                </div>
                <button type="button" className="btn px-3 py-1.5 text-xs" onClick={() => setForm({ ...form, tweak: !form.tweak })} aria-expanded={form.tweak}>
                  {form.tweak ? "Done adjusting" : "Adjust screens"}
                </button>
              </div>
              {form.tweak && (
                <div className="mt-3 space-y-4">
                  {GROUPS.map((g) => {
                    const keys = g.keys.filter((k) => AREAS[k]);
                    const isLive = keys.some((k) => LIVE.has(k));
                    // Screens that don't exist yet stay hidden unless asked for (or already switched on).
                    if (!isLive && !later && !keys.some((k) => areaState(form.draft, k, ACTIONS).level !== "off")) return null;
                    return (
                      <div key={g.label}>
                        <div className="mb-1 px-1 text-xs font-medium text-ink-faint">{g.label}{!isLive && " · coming later"}</div>
                        <ul className="divide-y divide-border rounded-2xl bg-surface ring-1 ring-border">
                          {keys.map((k) => {
                            const st = areaState(form.draft, k, ACTIONS);
                            const reach = st.reach ?? (form.manager ? "team" : "own");
                            const on = st.level !== "off";
                            return (
                              <li key={k} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                                <label className="flex min-w-48 flex-1 cursor-pointer items-center gap-3">
                                  <input type="checkbox" checked={on} className="h-4 w-4 accent-[rgb(var(--brand-fill))]"
                                    onChange={(e) => setForm({ ...form, draft: setArea(form.draft, k, ACTIONS, e.target.checked ? ["view"] : [], reach) })} />
                                  <span><span className="block text-sm">{AREAS[k][0]}</span><span className="block text-xs text-ink-faint">{AREAS[k][1]}</span></span>
                                </label>
                                {on && (
                                  <>
                                    <select aria-label={`${AREAS[k][0]} level`} className="input w-auto py-1.5 text-xs" value={st.level === "custom" ? "custom" : st.level}
                                      onChange={(e) => e.target.value !== "custom" && setForm({ ...form, draft: setArea(form.draft, k, ACTIONS, LEVELS.find((l) => l.id === e.target.value)!.actions, reach) })}>
                                      {st.level === "custom" && <option value="custom">Custom mix</option>}
                                      <option value="view">Can view</option><option value="add">Can view and add</option><option value="edit">Can view and edit</option><option value="full">Full control</option>
                                    </select>
                                    <select aria-label={`${AREAS[k][0]} reach`} className="input w-auto py-1.5 text-xs" value={st.mixed ? "" : reach}
                                      onChange={(e) => setForm({ ...form, draft: setArea(form.draft, k, ACTIONS, st.held, e.target.value as Scope) })}>
                                      {st.mixed && <option value="">Mixed</option>}
                                      {(["own", "team", "department", "all"] as Scope[]).map((s) => <option key={s} value={s}>{REACH_WORDS[s].replace(/^./, (c) => c.toUpperCase())} work</option>)}
                                    </select>
                                  </>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              )}
              {form.tweak && (
                <button type="button" className="mt-3 px-1 text-xs font-medium text-brand-text underline" onClick={() => setLater(!later)}>
                  {later ? "Hide features coming later" : "Show features coming later (attendance, billing, automations…)"}
                </button>
              )}
              {job && !same(form.draft, toDraft(job.grants)) && (
                <p className="mt-3 px-1 text-xs text-ink-soft">This person gets their own version of “{job.name}”. Other people with this job aren't affected.</p>
              )}
            </section>

            <div className="flex justify-end gap-2">
              <button type="button" className="btn" onClick={() => setForm(null)}>Cancel</button>
              <button className="btn-primary" disabled={saving || !form.roleId || !form.email}>{saving ? "Saving…" : form.locked ? "Save access" : "Give access"}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
