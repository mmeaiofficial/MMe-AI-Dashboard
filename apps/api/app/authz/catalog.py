"""Permission catalog and default roles.

A permission is ``<module>.<resource>.<action>``. A grant pairs a permission with a
data scope. ``<module>.<resource>.manage`` implies every other action on that resource.
Modules beyond Milestone 1 are listed now so default roles are complete from day one;
their routes arrive in later milestones.
"""
from __future__ import annotations

ACTIONS = ("view", "create", "edit", "delete", "export", "approve", "manage")
SCOPES = ("own", "team", "department", "all")  # narrow -> wide

RESOURCES: dict[str, str] = {
    # Milestone 1
    "admin.users": "Employee accounts (create, deactivate, reset MFA)",
    "admin.roles": "Roles and permission grants",
    "org.departments": "Departments",
    "org.teams": "Teams and membership",
    "org.employees": "Employee profiles",
    "audit.events": "Audit log",
    "system.settings": "Organization settings, domains, integrations, security",
    # Later milestones
    "crm.leads": "Leads and contacts",
    "sales.deals": "Deals and pipeline",
    "clients.accounts": "Client accounts (360 profile)",
    "billing.subscriptions": "Plans, subscriptions, invoices, payments",
    "work.projects": "Projects and milestones",
    "work.tasks": "Tasks",
    "hr.attendance": "Attendance",
    "hr.leave": "Leave requests",
    "automation.workflows": "Automation workflows and runs",
    "ai.agents": "AI agents, prompts and usage",
    "reports.analytics": "Dashboards, reports and exports",
}

ALL_PERMISSIONS: frozenset[str] = frozenset(f"{r}.{a}" for r in RESOURCES for a in ACTIONS)


def g(resource: str, actions: str, scope: str) -> list[tuple[str, str]]:
    return [(f"{resource}.{a.strip()}", scope) for a in actions.split(",")]


# Default roles from the Stage 1 blueprint ("Default roles" table). Super Admin is a user
# flag (users.is_super_admin), not a role, so it can never be granted through role edits.
DEFAULT_ROLES: dict[str, dict] = {
    "operations_admin": {
        "name": "Operations admin",
        "grants": g("crm.leads", "view", "all") + g("sales.deals", "view", "all")
        + g("clients.accounts", "view,create,edit", "all") + g("billing.subscriptions", "view", "all")
        + g("work.projects", "view,create,edit", "all") + g("work.tasks", "view,create,edit", "all")
        + g("hr.attendance", "view", "all") + g("hr.leave", "view,approve", "all")
        + g("org.employees", "view,edit", "all") + g("org.teams", "view", "all") + g("org.departments", "view", "all")
        + g("reports.analytics", "view", "all") + g("automation.workflows", "view", "all"),
    },
    "sales_manager": {
        "name": "Sales manager",
        "grants": g("crm.leads", "view,create,edit,export", "team") + g("sales.deals", "view,create,edit,export", "team")
        + g("clients.accounts", "view", "team") + g("billing.subscriptions", "view", "team")
        + g("work.tasks", "view,create,edit", "team") + g("work.projects", "view", "team")
        + g("hr.attendance", "view", "team") + g("hr.leave", "view,approve", "team")
        + g("org.employees", "view", "team") + g("org.teams", "view", "team") + g("reports.analytics", "view,export", "team"),
    },
    "sales_executive": {
        "name": "Sales executive",
        "grants": g("crm.leads", "view,create,edit", "own") + g("sales.deals", "view,create,edit", "own")
        + g("clients.accounts", "view", "own") + g("work.tasks", "view,create,edit", "own")
        + g("hr.attendance", "view,create", "own") + g("hr.leave", "view,create", "own")
        + g("org.employees", "view", "team") + g("reports.analytics", "view", "own"),
    },
    "marketing": {
        "name": "Marketing",
        "grants": g("crm.leads", "create", "own") + g("work.projects", "view,create,edit", "team")
        + g("work.tasks", "view,create,edit", "team") + g("hr.attendance", "view,create", "own")
        + g("hr.leave", "view,create", "own") + g("org.employees", "view", "team") + g("reports.analytics", "view", "team"),
    },
    "tech_automation": {
        "name": "Tech and automation",
        "grants": g("clients.accounts", "view", "own") + g("work.projects", "view,create,edit", "team")
        + g("work.tasks", "view,create,edit", "team") + g("automation.workflows", "view,create,edit", "team")
        + g("ai.agents", "view", "team") + g("hr.attendance", "view,create", "own") + g("hr.leave", "view,create", "own")
        + g("org.employees", "view", "team") + g("reports.analytics", "view", "team"),
    },
    "customer_success": {
        "name": "Customer success",
        "grants": g("crm.leads", "view", "own") + g("clients.accounts", "view,edit", "own")
        + g("billing.subscriptions", "view", "own") + g("work.projects", "view,edit", "own") + g("work.tasks", "view,create,edit", "own")
        + g("hr.attendance", "view,create", "own") + g("hr.leave", "view,create", "own")
        + g("org.employees", "view", "team") + g("reports.analytics", "view", "own"),
    },
    "finance": {
        "name": "Finance",
        "grants": g("crm.leads", "view", "all") + g("clients.accounts", "view", "all")
        + g("billing.subscriptions", "view,create,edit,export", "all") + g("hr.attendance", "view,create", "own")
        + g("hr.leave", "view,create", "own") + g("org.employees", "view", "team") + g("reports.analytics", "view,export", "all"),
    },
    "employee": {
        "name": "Employee (base)",
        "grants": g("work.tasks", "view,create,edit", "own") + g("hr.attendance", "view,create", "own")
        + g("hr.leave", "view,create", "own") + g("org.employees", "view", "team") + g("reports.analytics", "view", "own"),
    },
}

# Permissions that require the holder to have MFA confirmed before they take effect.
MFA_REQUIRED_PREFIXES = ("admin.", "system.", "billing.subscriptions.manage")
MFA_REQUIRED_ACTIONS = ("export",)


def validate_catalog() -> None:
    for key, role in DEFAULT_ROLES.items():
        for perm, scope in role["grants"]:
            if perm not in ALL_PERMISSIONS:
                raise ValueError(f"{key}: unknown permission {perm}")
            if scope not in SCOPES:
                raise ValueError(f"{key}: unknown scope {scope}")


validate_catalog()
