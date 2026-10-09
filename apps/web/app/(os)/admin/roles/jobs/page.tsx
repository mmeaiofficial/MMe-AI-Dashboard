"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, Search, SlidersHorizontal } from "lucide-react";
import { useSession } from "@/components/session";
import { PageHeader } from "@/components/ui";
import { ACTION_LABEL, AREAS, areaState, GROUPS, LEVELS, LIVE, REACH, Segmented, setArea, type Draft } from "@/components/access";
import { api, ApiError, can, type Scope } from "@/lib/api";

interface Grant { permission: string; scope: Scope; }
interface Role { id: string; key: string; name: string; description: string; is_system: boolean; personal?: boolean; grants: Grant[]; }
interface Catalog { resources: { key: string; label: string }[]; actions: string[]; scopes: Scope[]; }
interface UserRow { roles: string[]; }

export default function RolesPage() {
  const { me } = useSession();
  const [roles, setRoles] = useState<Role[]>([]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [holders, setHolders] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>({});
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [custom, setCustom] = useState<Record<string, boolean>>({});
  const [q, setQ] = useState("");
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [r, c] = await Promise.all([api.get<Role[]>("/admin/roles"), api.get<Catalog>("/admin/permissions")]);
      setRoles(r.filter((x) => !x.personal)); setCatalog(c); setSelected((s) => s ?? r[0]?.id ?? null);
    } catch (e) { setMsg({ text: (e as ApiError).message, error: true }); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!me || !can(me, "admin.users.view")) return;
    api.get<UserRow[]>("/admin/users").then((us) => {
      const n: Record<string, number> = {};
      for (const u of us) for (const k of u.roles) n[k] = (n[k] ?? 0) + 1;
      setHolders(n);
    }).catch(() => {});
  }, [me]);

  const role = useMemo(() => roles.find((r) => r.id === selected) || null, [roles, selected]);
  const saved = useMemo<Draft>(() => Object.fromEntries((role?.grants || []).map((g) => [g.permission, g.scope])), [role]);
  useEffect(() => { setDraft(saved); setCustom({}); }, [saved]);
  const dirty = useMemo(() => JSON.stringify(Object.entries(draft).sort()) !== JSON.stringify(Object.entries(saved).sort()), [draft, saved]);

  if (!me || !catalog) return msg ? <p className="alert-error">{msg.text}</p> : null;
  const editable = can(me, "admin.roles.manage");
  const actions = catalog.actions;
  const known = new Set(GROUPS.flatMap((g) => g.keys));
  const groups = [...GROUPS, { label: "Other", keys: catalog.resources.map((r) => r.key).filter((k) => !known.has(k)) }]
    .map((g) => ({ ...g, keys: g.keys.filter((k) => catalog.resources.some((r) => r.key === k)) }))
    .filter((g) => g.keys.length);
  const label = (k: string) => AREAS[k] ?? [catalog.resources.find((r) => r.key === k)?.label ?? k, ""];
  const matches = (k: string) => !q || label(k).join(" ").toLowerCase().includes(q.toLowerCase());

  async function save() {
    if (!role) return;
    setSaving(true); setMsg(null);
    try {
      const grants = Object.entries(draft).map(([permission, scope]) => ({ permission, scope }));
      await api.put(`/admin/roles/${role.id}`, { key: role.key, name: role.name, description: role.description, grants });
      setMsg({ text: `${role.name} saved. Changes apply on each person's next click.` });
      await load();
    } catch (e) { setMsg({ text: (e as ApiError).message, error: true }); } finally { setSaving(false); }
  }

  const pick = (id: string) => {
    if (dirty && !window.confirm("Discard unsaved changes to this role?")) return;
    setSelected(id); setMsg(null);
  };

  return (
    <div className="max-w-5xl space-y-6 pb-24">
      <PageHeader title="Edit jobs" subtitle="What each job can open by default. Changes apply to everyone with that job." actions={<Link href="/admin/roles" className="btn">Back to people</Link>} />

      {/* Role picker */}
      <div className="flex flex-wrap gap-2">
        {roles.map((r) => {
          const areas = new Set(r.grants.map((g) => g.permission.split(".").slice(0, 2).join("."))).size;
          return (
            <button key={r.id} onClick={() => pick(r.id)} aria-pressed={r.id === selected}
              className={`shrink-0 rounded-3xl px-4 py-2.5 text-left transition ${r.id === selected ? "bg-brand-fill text-on-brand" : "bg-surface text-ink ring-1 ring-border hover:ring-brand"}`}>
              <div className="text-sm font-medium">{r.name}</div>
              <div className={`text-xs ${r.id === selected ? "text-on-brand" : "text-ink-faint"}`}>
                {areas} area{areas === 1 ? "" : "s"}{r.key in holders ? ` · ${holders[r.key]} ${holders[r.key] === 1 ? "person" : "people"}` : ""}
              </div>
            </button>
          );
        })}
      </div>

      {msg && <p role="status" className={msg.error ? "alert-error" : "rounded-2xl bg-surface px-4 py-3 text-sm ring-1 ring-border"}>{msg.text}</p>}
      {!editable && <p className="rounded-2xl bg-surface px-4 py-3 text-sm text-ink-soft ring-1 ring-border">You can view roles but not change them.</p>}

      {role && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative min-w-60 flex-1">
              <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
              <input className="input pl-10" placeholder="Find an area, e.g. leads or attendance" aria-label="Find an area" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <p className="text-xs text-ink-faint">Reach: <b className="font-medium text-ink-soft">Own</b> their records · <b className="font-medium text-ink-soft">Team</b> · <b className="font-medium text-ink-soft">Dept</b> · <b className="font-medium text-ink-soft">All</b> whole company</p>
          </div>

          {groups.map((g) => {
            const keys = g.keys.filter(matches);
            if (!keys.length) return null;
            const on = g.keys.filter((k) => areaState(draft, k, actions).level !== "off").length;
            const live = g.keys.some((k) => LIVE.has(k));
            const isOpen = q ? true : open[g.label] ?? live;
            return (
              <section key={g.label} className="card p-0">
                <button className="flex w-full items-center gap-3 px-6 py-4 text-left" aria-expanded={isOpen} onClick={() => setOpen({ ...open, [g.label]: !isOpen })}>
                  <span className="flex-1">
                    <span className="font-medium">{g.label}</span>
                    {!live && <span className="pill ml-2">coming later</span>}
                  </span>
                  <span className="text-xs text-ink-faint">{on} of {g.keys.length} on</span>
                  <ChevronDown size={18} className={`text-ink-soft transition ${isOpen ? "rotate-180" : ""}`} aria-hidden="true" />
                </button>
                {isOpen && (
                  <ul className="divide-y divide-border border-t border-border">
                    {keys.map((k) => {
                      const st = areaState(draft, k, actions);
                      const [name, hint] = label(k);
                      const showCustom = custom[k] || st.level === "custom";
                      const reach = st.reach ?? "own";
                      return (
                        <li key={k} className="px-6 py-4">
                          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                            <div className="min-w-48 flex-1">
                              <div className="font-medium">{name}</div>
                              {hint && <div className="text-xs text-ink-faint">{hint}</div>}
                            </div>
                            <Segmented label={`${name} access`} disabled={!editable}
                              value={st.level === "custom" ? undefined : st.level} options={LEVELS}
                              onChange={(lv) => { setDraft(setArea(draft, k, actions, LEVELS.find((l) => l.id === lv)!.actions, reach)); setCustom({ ...custom, [k]: false }); }} />
                            <div className={st.level === "off" ? "invisible" : ""}>
                              <Segmented label={`${name} reach`} disabled={!editable || st.level === "off"}
                                value={st.mixed ? undefined : st.reach} options={REACH}
                                onChange={(sc) => setDraft(setArea(draft, k, actions, st.held, sc))} />
                            </div>
                            <button type="button" onClick={() => setCustom({ ...custom, [k]: !showCustom })} aria-expanded={showCustom}
                              title="Pick individual actions" className={`grid h-8 w-8 place-items-center rounded-full transition ${st.level === "off" && !showCustom ? "invisible" : ""} ${showCustom ? "bg-brand-soft text-brand-text" : "text-ink-faint hover:text-ink"}`}>
                              <SlidersHorizontal size={15} aria-label="Customize actions" />
                            </button>
                          </div>
                          {(showCustom || st.mixed) && (
                            <div className="mt-3 rounded-2xl bg-well px-4 py-3">
                              {st.level === "custom" && <p className="mb-2 text-xs text-ink-soft">Custom mix of actions for this area.</p>}
                              {st.mixed && <p className="mb-2 text-xs text-ink-soft">These actions reach different distances; picking a reach above applies it to all of them.</p>}
                              {showCustom && (
                                <div className="flex flex-wrap gap-2">
                                  {actions.map((a) => {
                                    const onA = !!draft[`${k}.${a}`];
                                    return (
                                      <button key={a} type="button" disabled={!editable} aria-pressed={onA}
                                        onClick={() => setDraft(setArea(draft, k, actions, onA ? st.held.filter((x) => x !== a) : [...st.held, a], reach))}
                                        className={`rounded-full px-3 py-1.5 text-xs font-medium ring-1 transition disabled:cursor-not-allowed ${onA ? "bg-brand-fill text-on-brand ring-brand-fill" : "bg-surface text-ink-soft ring-border enabled:hover:ring-brand"}`}>
                                        {ACTION_LABEL[a] ?? a}{onA && draft[`${k}.${a}`] !== reach ? ` · ${draft[`${k}.${a}`]}` : ""}
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>
            );
          })}
        </>
      )}

      {/* Save bar appears only when something changed */}
      {editable && role && dirty && (
        <div className="fixed inset-x-4 bottom-4 z-20 mx-auto flex max-w-xl items-center gap-3 rounded-full bg-surface py-2 pl-5 pr-2 ring-1 ring-border md:left-[276px]">
          <span className="flex-1 text-sm">Unsaved changes to <b className="font-medium">{role.name}</b></span>
          <button className="btn" onClick={() => setDraft(saved)} disabled={saving}>Discard</button>
          <button className="btn-primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
        </div>
      )}
    </div>
  );
}
