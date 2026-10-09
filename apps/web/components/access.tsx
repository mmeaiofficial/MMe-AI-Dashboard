"use client";

// Shared plain-language access model: 7 actions x 4 reaches shown as Off/View/Edit/Full and Own/Team/Dept/All.
// Used by "Roles and permissions" (per person) and "Edit jobs" (per role).
import type { Scope } from "@/lib/api";

export type Draft = Record<string, Scope>; // permission -> scope; absent means no access

export type Level = "off" | "view" | "add" | "edit" | "full" | "custom";
export const LEVELS: { id: Exclude<Level, "custom">; label: string; hint: string; actions: string[] }[] = [
  { id: "off", label: "Off", hint: "No access", actions: [] },
  { id: "view", label: "View", hint: "Can look, can't change", actions: ["view"] },
  { id: "add", label: "Add", hint: "View and add new (log a call, check in, request leave), can't change existing", actions: ["view", "create"] },
  { id: "edit", label: "Edit", hint: "View, add and change", actions: ["view", "create", "edit"] },
  { id: "full", label: "Full", hint: "Everything, including delete, export and approve", actions: ["manage"] },
];
export const REACH: { id: Scope; label: string; hint: string }[] = [
  { id: "own", label: "Own", hint: "Only records they own or are assigned" },
  { id: "team", label: "Team", hint: "Records of their teams" },
  { id: "department", label: "Dept", hint: "Records of their department" },
  { id: "all", label: "All", hint: "The whole company" },
];
export const RANK: Record<Scope, number> = { own: 0, team: 1, department: 2, all: 3 };
export const ACTION_LABEL: Record<string, string> = { view: "View", create: "Add", edit: "Change", delete: "Delete", export: "Export", approve: "Approve", manage: "Everything" };

export const AREAS: Record<string, [string, string]> = {
  "org.employees": ["Employee profiles", "Names, designations and contact details"],
  "org.teams": ["Teams", "Teams and who is in them"],
  "org.departments": ["Departments", "Department list and heads"],
  "admin.users": ["User accounts", "Invite, deactivate, reset authenticators"],
  "admin.roles": ["Roles and permissions", "This page: who can do what"],
  "audit.events": ["Audit log", "Record of sign-ins and access changes"],
  "system.settings": ["Company settings", "Domains, integrations and security"],
  "crm.leads": ["Leads", "Add, qualify and reject leads"],
  "sales.calls": ["Cold calls", "Call queue and call log (Sales L1)"],
  "sales.deals": ["Meetings and deals", "Booked meetings and closing (Sales L2)"],
  "clients.accounts": ["Clients", "Client profiles"],
  "billing.subscriptions": ["Billing", "Plans, invoices and payments"],
  "work.projects": ["Projects", "Projects and milestones"],
  "work.tasks": ["Tasks and tickets", "Client tickets for the tech team"],
  "hr.attendance": ["Attendance", "Check-ins and attendance"],
  "hr.leave": ["Leave", "Leave requests and approvals"],
  "automation.workflows": ["Automations", "Automated workflows and their runs"],
  "ai.agents": ["AI agents", "Rekha and other AI tools"],
  "reports.analytics": ["Reports", "Dashboards, reports and exports"],
};
export const LIVE = new Set(["org.employees", "org.teams", "org.departments", "admin.users", "admin.roles", "audit.events",
  "crm.leads", "sales.calls", "sales.deals", "work.tasks"]);
export const GROUPS: { label: string; keys: string[] }[] = [
  { label: "People and teams", keys: ["org.employees", "org.teams", "org.departments"] },
  { label: "Admin and security", keys: ["admin.users", "admin.roles", "audit.events", "system.settings"] },
  { label: "Pipeline", keys: ["crm.leads", "sales.calls", "sales.deals", "work.tasks"] },
  { label: "Clients and work", keys: ["clients.accounts", "billing.subscriptions", "work.projects"] },
  { label: "Attendance and leave", keys: ["hr.attendance", "hr.leave"] },
  { label: "Automation, AI and reports", keys: ["automation.workflows", "ai.agents", "reports.analytics"] },
];

export function areaState(draft: Draft, res: string, actions: string[]) {
  const held = actions.filter((a) => draft[`${res}.${a}`]);
  const scopes = [...new Set(held.map((a) => draft[`${res}.${a}`]))];
  const key = [...held].sort().join(",");
  const level: Level = held.length === 0 ? "off" : held.includes("manage") && held.length === 1 ? "full"
    : (LEVELS.find((l) => l.id !== "off" && [...l.actions].sort().join(",") === key)?.id ?? "custom");
  const reach = scopes.sort((a, b) => RANK[b] - RANK[a])[0] as Scope | undefined;
  return { held, level, reach, mixed: scopes.length > 1 };
}

export function setArea(draft: Draft, res: string, allActions: string[], actions: string[], reach: Scope): Draft {
  const next = { ...draft };
  for (const a of allActions) delete next[`${res}.${a}`];
  for (const a of actions) next[`${res}.${a}`] = reach;
  return next;
}

export function Segmented<T extends string>({ label, value, options, onChange, disabled }: {
  label: string; value: T | undefined; options: { id: T; label: string; hint: string }[]; onChange: (v: T) => void; disabled?: boolean;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-grid auto-cols-fr grid-flow-col gap-0.5 rounded-full bg-well p-0.5">
      {options.map((o) => (
        <button key={o.id} type="button" role="radio" aria-checked={value === o.id} title={o.hint} disabled={disabled} onClick={() => onChange(o.id)}
          className={`rounded-full px-3 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed ${value !== o.id ? "text-ink-soft enabled:hover:text-ink" : o.id === "off" ? "bg-surface text-ink ring-1 ring-border" : "bg-brand-fill text-on-brand"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

