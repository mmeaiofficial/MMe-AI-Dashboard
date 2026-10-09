# MME OS codebase (Milestones 0–1)

Repo: github.com/Vaibhav586/MMe-AI-Dashboard (private) · local: ~/Documents/Projects/MMe_AI_Dashboard · commit b172b49

## File list
- .env.example
- .github/workflows/ci.yml
- .gitignore
- README.md
- apps/api/Dockerfile
- apps/api/alembic.ini
- apps/api/app/__init__.py
- apps/api/app/audit/__init__.py
- apps/api/app/audit/router.py
- apps/api/app/audit/writer.py
- apps/api/app/authz/__init__.py
- apps/api/app/authz/catalog.py
- apps/api/app/authz/engine.py
- apps/api/app/core/__init__.py
- apps/api/app/core/config.py
- apps/api/app/core/crypto.py
- apps/api/app/core/db.py
- apps/api/app/core/deps.py
- apps/api/app/core/google_oidc.py
- apps/api/app/core/models.py
- apps/api/app/core/ratelimit.py
- apps/api/app/core/security.py
- apps/api/app/main.py
- apps/api/app/modules/__init__.py
- apps/api/app/modules/access/__init__.py
- apps/api/app/modules/access/router.py
- apps/api/app/modules/identity/__init__.py
- apps/api/app/modules/identity/policy.py
- apps/api/app/modules/identity/router.py
- apps/api/app/modules/identity/service.py
- apps/api/app/modules/org/__init__.py
- apps/api/app/modules/org/router.py
- apps/api/app/worker/__init__.py
- apps/api/migrations/env.py
- apps/api/migrations/sql/0001_foundation.sql
- apps/api/migrations/versions/0001_foundation.py
- apps/api/pyproject.toml
- apps/api/requirements-dev.txt
- apps/api/requirements.txt
- apps/api/scripts/__init__.py
- apps/api/scripts/seed.py
- apps/api/tests/__init__.py
- apps/api/tests/api/__init__.py
- apps/api/tests/api/conftest.py
- apps/api/tests/api/test_access.py
- apps/api/tests/api/test_schema_parity.py
- apps/api/tests/core/__init__.py
- apps/api/tests/core/test_core.py
- apps/web/app/(os)/admin/roles/page.tsx
- apps/web/app/(os)/admin/users/page.tsx
- apps/web/app/(os)/audit/page.tsx
- apps/web/app/(os)/employees/page.tsx
- apps/web/app/(os)/layout.tsx
- apps/web/app/(os)/page.tsx
- apps/web/app/(os)/teams/page.tsx
- apps/web/app/globals.css
- apps/web/app/layout.tsx
- apps/web/app/mfa/page.tsx
- apps/web/app/sign-in/page.tsx
- apps/web/components/session.tsx
- apps/web/lib/api.ts
- apps/web/next-env.d.ts
- apps/web/next.config.mjs
- apps/web/package.json
- apps/web/postcss.config.mjs
- apps/web/tailwind.config.ts
- apps/web/tsconfig.json
- docs/decisions.md
- docs/security-model.md
- infra/docker-compose.yml

---

## `README.md`

````markdown
# MME OS

MME's internal Business OS: Stage 1 of the plan in the *MME AI Business OS: Stage 1 Blueprint*.
This repository currently delivers **Milestone 0 (foundation) and Milestone 1 (access and organization)**.

| Area | State |
|---|---|
| Google sign-in (OIDC + PKCE), password fallback, sessions in httpOnly cookies, CSRF | built |
| MFA (authenticator app) required for Super Admins and admin/export permissions | built |
| Roles with grants = permission + scope (own / team / department / all), enforced in the API | built |
| Super Admin console: invite, deactivate (ends sessions, hands over teams/reports), roles, Super Admin status, MFA reset | built |
| Departments, teams, membership, employee profiles (scoped) | built |
| Append-only audit log (database-enforced) for sign-ins, access changes and admin actions | built |
| Last Super Admin protection (API rule + database trigger) | built |
| Worker, file storage, n8n, AI layer | Milestones 2–4 |
| CRM, sales, clients, billing, projects/tasks, attendance/leave, dashboard | Milestones 2–5 |

## Run locally

```bash
cp .env.example .env              # fill GOOGLE_CLIENT_ID/SECRET and BOOTSTRAP_SUPER_ADMINS
docker compose -f infra/docker-compose.yml up --build
docker compose -f infra/docker-compose.yml exec api python -m scripts.seed --org-name "MME AI" --domain mme-ai.com
open http://localhost:3000/sign-in
```

The first person in `BOOTSTRAP_SUPER_ADMINS` to sign in with Google becomes Super Admin and must set up an authenticator.
Everyone else needs an invitation (Users and access → Invite), or a Google account on a domain passed to `--domain`, which joins with the base Employee role.

### Google OAuth client
Google Cloud console → APIs & Services → Credentials → Create OAuth client ID → Web application.
Authorized redirect URIs: `http://localhost:8000/api/v1/auth/google/callback` (and the production API origin + the same path).

## Tests

| Suite | Needs | Command |
|---|---|---|
| Core security: permission engine, scopes, anti-escalation, MFA codes, passwords, encryption, Google token checks, sign-in rules, production config | Python only | `cd apps/api && python -m unittest discover -s tests/core -t .` |
| API: every route declares access, authorization matrix per role, scopes, CSRF, audit, deactivation, Super Admin rules, schema parity | PostgreSQL | `cd apps/api && TEST_DATABASE_URL=… pytest tests/api` |
| Web: type check and production build | Node 22 | `cd apps/web && npm run typecheck && npm run build` |

CI (`.github/workflows/ci.yml`) runs all of them plus migrations up/down, `pip-audit`, `bandit`, `npm audit` and `gitleaks` on every pull request.

## Layout

```
apps/api      FastAPI · app/authz (permission engine) · app/core · app/modules/{identity,access,org} · app/audit · migrations · tests
apps/web      Next.js console: sign-in, MFA, home, people, teams, users and access, roles and permissions, audit log
infra         docker-compose for local work
docs          security model, decisions
```

## Production checklist (before staging/production)
- `APP_ENV=production` refuses to start with a weak `SECRET_KEY`, missing encryption keys, missing Google credentials, non-https origins or development database credentials.
- Set `RATE_LIMIT_BACKEND=redis` (memory is refused in production).
- Run the API behind TLS; set `COOKIE_DOMAIN` if web and API are on sibling subdomains.
- Keep the repository private.

````

---

## `docs/security-model.md`

````markdown
# Security model (Milestones 0–1)

## Who can get in
1. `BOOTSTRAP_SUPER_ADMINS` emails become Super Admin on their first Google sign-in.
2. An open, unexpired invitation for that email (created by a Super Admin) creates the account with the invited roles and teams.
3. A verified Google account on an organization `allowed_domains` entry joins with the base Employee role.
4. Everyone else is refused. A deactivated account is refused, and an email already linked to a different Google account is refused.

## Sessions
- Random 256-bit token in an httpOnly, SameSite=Lax cookie (Secure outside development); only its SHA-256 is stored.
- Absolute lifetime `SESSION_HOURS`, idle timeout `SESSION_IDLE_MINUTES`; "sign out everywhere" revokes all.
- Writes need `X-CSRF-Token` = HMAC(secret, session token), returned by `/me`.
- Deactivation, Super Admin changes and MFA resets revoke the person's sessions immediately.

## MFA
- TOTP (RFC 6238), secrets encrypted with AES-256-GCM bound to the user id; a used code can't be replayed.
- Required for Super Admins and anyone after enrolment; `admin.*`, `system.*` and every `*.export` permission only take effect once MFA is passed in the session.

## Authorization
- Permission = `module.resource.action`; grant = permission + scope (`own` < `team` < `department` < `all`); a role = set of grants.
- Effective scope = widest across a person's roles; `resource.manage` implies every action.
- Every route declares its permission (`requires(...)`); a test fails the build if a route declares nothing.
- Lists are filtered by scope in SQL; single records outside scope or in another organization return 404.
- Super Admin is a user flag, not a role, so editing roles can never create one.

## Anti-escalation
- Nobody changes their own roles or Super Admin status.
- Only Super Admins edit roles, and not a role they hold.
- A delegated admin can't grant a permission wider than one they hold.
- The last active Super Admin can't be removed (API rule and database trigger).

## Audit
- `audit_events` is append-only: UPDATE and DELETE raise an error in the database.
- Business changes and their audit event commit in one transaction; failed sign-ins and wrong MFA codes are written in their own transaction so a failed request still leaves a trace.
- Secrets in before/after values are redacted.

## Encryption model (stated plainly)
TLS in transit, provider encryption at rest, plus application-level AES-GCM for secrets (MFA secrets now; integration tokens later). This is not end-to-end encryption: the server reads business data to search, report and automate.

## Known gaps to close in later milestones
- Email delivery of invitations (the link is shown once to the admin for now).
- File uploads, malware scanning and signed URLs arrive with the worker in Milestone 2.
- Row-level security on `organization_id` is planned for Stage 2 as a second wall behind API checks.
- Password sign-in exists for accounts without Google; there is no self-service password reset yet (Super Admin resets).

````

---

## `docs/decisions.md`

````markdown
# Engineering decisions (Milestones 0–1)

| # | Decision | Why |
|---|---|---|
| 1 | The SQL migration file is the schema's source of truth; ORM models mirror it and a test checks parity | Constraints, triggers (append-only audit, last Super Admin) and checks live in the database where they can't be bypassed |
| 2 | Super Admin is a user flag, not a role | Role edits can never mint a Super Admin; changing it has its own rules and audit event |
| 3 | Permission engine is framework-free (`app/authz/engine.py`) | Every rule is unit-tested without a database; the same function computes `/me` permissions and enforces requests |
| 4 | Out-of-scope and other-organization records return 404 | IDs can't be probed |
| 5 | Passwords use scrypt (standard library) | Memory-hard, no extra dependency; Argon2id can replace it behind the same `hash_password` |
| 6 | Sessions are server-side rows, not JWTs | Deactivation and "sign out everywhere" take effect immediately |
| 7 | `organization_id` on every table now, one organization in Stage 1 | Stage 2/3 multi-tenancy without migrating every table |
| 8 | Business change + audit event in one transaction; failed sign-in events in their own | No change without its record; failed attempts still recorded |
| 9 | Google OIDC verified locally (signature, issuer, audience, expiry, nonce, verified email) with PKCE | No third-party auth service needed in Stage 1 |

````

---

## `.env.example`

````text
# Copy to .env for local development. Never commit .env.
APP_ENV=development
SECRET_KEY=change-me-to-64-random-characters
WEB_ORIGIN=http://localhost:3000
API_ORIGIN=http://localhost:8000
# Google Cloud console → APIs & Services → Credentials → OAuth client (Web).
# Authorized redirect URI: http://localhost:8000/api/v1/auth/google/callback
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
# Emails that become Super Admin on first Google sign-in (comma-separated).
BOOTSTRAP_SUPER_ADMINS=
# Field encryption (staging/production): kid:base64-32-bytes ; generate with
#   python -c "import os,base64;print('k1:'+base64.urlsafe_b64encode(os.urandom(32)).decode())"
FIELD_ENCRYPTION_KEYS=
FIELD_ENCRYPTION_ACTIVE_KID=
RATE_LIMIT_BACKEND=redis
# Optional: share the session cookie between os.mme-ai.com and api.mme-ai.com
COOKIE_DOMAIN=

````

---

## `.github/workflows/ci.yml`

````yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]

jobs:
  api:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_USER: mme, POSTGRES_PASSWORD: mme, POSTGRES_DB: mme_os_test }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U mme" --health-interval 5s --health-retries 10
    defaults: { run: { working-directory: apps/api } }
    env:
      TEST_DATABASE_URL: postgresql+psycopg://mme:mme@localhost:5432/mme_os_test
      RATE_LIMIT_BACKEND: memory
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements-dev.txt
      - name: Lint
        run: ruff check .
      - name: Type check
        run: mypy app
      - name: Core security tests (no database)
        run: python -m pytest tests/core -q
      - name: API tests (authorization matrix, scopes, CSRF, audit) on PostgreSQL
        run: python -m pytest tests/api -q
      - name: Migration up/down
        env: { DATABASE_URL: postgresql+psycopg://mme:mme@localhost:5432/mme_os_test }
        run: |
          psql postgresql://mme:mme@localhost:5432/mme_os_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
          alembic upgrade head && alembic downgrade base && alembic upgrade head
      - name: Dependency audit
        run: pip-audit -r requirements.txt
      - name: Static security scan
        run: bandit -q -r app -x app/worker

  web:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: apps/web } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22" }
      - run: npm install
      - run: npm run typecheck
      - run: npm run build
      - run: npm audit --audit-level=high

  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env: { GITHUB_TOKEN: "${{ secrets.GITHUB_TOKEN }}" }

````

---

## `.gitignore`

````text
.env
__pycache__/
*.pyc
.venv/
node_modules/
.next/
.mypy_cache/
.ruff_cache/
.pytest_cache/

````

---

## `apps/api/Dockerfile`

````text
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]

````

---

## `apps/api/alembic.ini`

````ini
[alembic]
script_location = migrations
prepend_sys_path = .

[loggers]
keys = root
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic
[formatter_generic]
format = %(levelname)s %(name)s %(message)s

````

---

## `apps/api/app/__init__.py`

````python

````

---

## `apps/api/app/audit/__init__.py`

````python

````

---

## `apps/api/app/audit/router.py`

````python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..core.db import get_db
from ..core.deps import Caller, requires
from ..core.models import AuditEvent

router = APIRouter(tags=["audit"])


@router.get("/audit-events")
def list_audit_events(
    action: Optional[str] = Query(default=None, max_length=80),
    actor_user_id: Optional[uuid.UUID] = None,
    target_id: Optional[str] = Query(default=None, max_length=80),
    before_id: Optional[int] = None,
    since: Optional[datetime] = None,
    limit: int = Query(default=50, ge=1, le=100),
    caller: Caller = Depends(requires("audit.events.view")),
    db: DbSession = Depends(get_db),
) -> dict:
    q = select(AuditEvent).where(AuditEvent.organization_id == caller.user.organization_id)
    if action:
        q = q.where(AuditEvent.action.startswith(action))
    if actor_user_id:
        q = q.where(AuditEvent.actor_user_id == actor_user_id)
    if target_id:
        q = q.where(AuditEvent.target_id == target_id)
    if since:
        q = q.where(AuditEvent.created_at >= since)
    if before_id:
        q = q.where(AuditEvent.id < before_id)
    rows = db.scalars(q.order_by(AuditEvent.id.desc()).limit(limit)).all()
    items = [{"id": r.id, "action": r.action, "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
              "target_type": r.target_type, "target_id": r.target_id, "before": r.before, "after": r.after,
              "ip": str(r.ip) if r.ip else None, "created_at": r.created_at.isoformat()} for r in rows]
    return {"items": items, "next_before_id": items[-1]["id"] if len(items) == limit else None}

````

---

## `apps/api/app/audit/writer.py`

````python
"""Audit writer: adds the event to the SAME database session as the change, so both commit
together (get_db commits once per request) or neither does."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..core.models import AuditEvent

REDACT = {"password", "password_hash", "secret", "secret_enc", "token", "token_hash", "key_hash", "code"}


@dataclass(frozen=True)
class RequestContext:
    organization_id: uuid.UUID
    actor_user_id: Optional[uuid.UUID]
    ip: Optional[str]
    user_agent: Optional[str]
    request_id: Optional[str]


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[redacted]" if k in REDACT else _clean(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_clean(v) for v in value]
    if isinstance(value, (uuid.UUID, datetime, date)):
        return str(value)
    return value


def record_now(ctx: RequestContext, action: str, target_type: Optional[str] = None,
               target_id: Optional[Any] = None, before: Optional[dict] = None, after: Optional[dict] = None) -> None:
    """For security events on a request that is about to fail (failed sign-in, wrong MFA code):
    written in its own transaction so the request's rollback does not erase it."""
    from ..core.db import SessionLocal
    db = SessionLocal()
    try:
        record(db, ctx, action, target_type, target_id, before, after)
        db.commit()
    finally:
        db.close()


def record(db: Session, ctx: RequestContext, action: str, target_type: Optional[str] = None,
           target_id: Optional[Any] = None, before: Optional[dict] = None, after: Optional[dict] = None) -> None:
    db.add(AuditEvent(
        organization_id=ctx.organization_id, actor_user_id=ctx.actor_user_id, action=action,
        target_type=target_type, target_id=str(target_id) if target_id is not None else None,
        before=json.loads(json.dumps(_clean(before))) if before is not None else None,
        after=json.loads(json.dumps(_clean(after))) if after is not None else None,
        ip=ctx.ip, user_agent=(ctx.user_agent or "")[:400], request_id=ctx.request_id,
    ))

````

---

## `apps/api/app/authz/__init__.py`

````python

````

---

## `apps/api/app/authz/catalog.py`

````python
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

````

---

## `apps/api/app/authz/engine.py`

````python
"""Authorization engine: permissions + data scopes, framework-free so it is unit-tested alone.

Rules
- A subject may do ``permission`` on a record only if it holds a grant for that permission
  (or for ``<resource>.manage``) whose scope covers the record, inside its own organization.
- Several grants for one permission: the widest scope wins.
- Super Admin (a user flag, never a role) passes every check inside its own organization.
- Out-of-scope single records must be answered as "not found" by the API (no ID probing).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional
from uuid import UUID

from .catalog import ACTIONS, ALL_PERMISSIONS, SCOPES, MFA_REQUIRED_ACTIONS, MFA_REQUIRED_PREFIXES

RANK = {s: i for i, s in enumerate(SCOPES)}


class AuthzError(Exception):
    """Base class; the API maps subclasses to HTTP errors."""


class Forbidden(AuthzError):
    """Missing permission → 403."""


class NotFound(AuthzError):
    """Out of scope or other organization → 404 (indistinguishable from absent)."""


class EscalationDenied(AuthzError):
    """A role/permission change the actor is not allowed to make → 403."""


@dataclass(frozen=True)
class Grant:
    permission: str
    scope: str

    def __post_init__(self) -> None:
        if self.permission not in ALL_PERMISSIONS:
            raise ValueError(f"unknown permission {self.permission}")
        if self.scope not in SCOPES:
            raise ValueError(f"unknown scope {self.scope}")


@dataclass(frozen=True)
class Subject:
    user_id: UUID
    organization_id: UUID
    grants: tuple[Grant, ...] = ()
    team_ids: frozenset[UUID] = frozenset()
    managed_team_ids: frozenset[UUID] = frozenset()
    department_id: Optional[UUID] = None
    is_super_admin: bool = False
    mfa_passed: bool = False
    active: bool = True


@dataclass(frozen=True)
class RecordRef:
    """What the engine needs to know about a record to place it in a scope."""
    organization_id: UUID
    owner_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    assignee_ids: frozenset[UUID] = frozenset()


@dataclass(frozen=True)
class ScopeCriteria:
    """A filter the data layer turns into SQL. ``all_records`` means organization-wide."""
    organization_id: UUID
    all_records: bool = False
    user_ids: frozenset[UUID] = frozenset()        # owner_id IN / assignee IN
    team_ids: frozenset[UUID] = frozenset()        # team_id IN
    department_ids: frozenset[UUID] = frozenset()  # department_id IN


def _resource(permission: str) -> str:
    return permission.rsplit(".", 1)[0]


def requires_mfa(permission: str) -> bool:
    return permission.startswith(MFA_REQUIRED_PREFIXES) or permission.rsplit(".", 1)[1] in MFA_REQUIRED_ACTIONS


def effective_grants(grants: Iterable[Grant]) -> dict[str, str]:
    """permission -> widest scope across all of a user's roles."""
    out: dict[str, str] = {}
    for gr in grants:
        cur = out.get(gr.permission)
        if cur is None or RANK[gr.scope] > RANK[cur]:
            out[gr.permission] = gr.scope
    return out


def scope_for(subject: Subject, permission: str) -> Optional[str]:
    """Widest scope the subject holds for ``permission`` (``manage`` implies all actions)."""
    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"unknown permission {permission}")
    if not subject.active:
        return None
    if subject.is_super_admin:
        return "all" if (subject.mfa_passed or not requires_mfa(permission)) else None
    eff = effective_grants(subject.grants)
    candidates = [eff.get(permission), eff.get(_resource(permission) + ".manage")]
    held = [c for c in candidates if c is not None]
    if not held:
        return None
    if requires_mfa(permission) and not subject.mfa_passed:
        return None
    return max(held, key=lambda s: RANK[s])


def has_permission(subject: Subject, permission: str) -> bool:
    return scope_for(subject, permission) is not None


def require(subject: Subject, permission: str) -> str:
    scope = scope_for(subject, permission)
    if scope is None:
        raise Forbidden(permission)
    return scope


def in_scope(subject: Subject, scope: str, record: RecordRef) -> bool:
    if record.organization_id != subject.organization_id:
        return False
    if scope == "all":
        return True
    mine = record.owner_id == subject.user_id or subject.user_id in record.assignee_ids
    if scope == "own":
        return mine
    if scope == "team":
        return mine or (record.team_id is not None and record.team_id in subject.team_ids)
    if scope == "department":
        return mine or (record.team_id is not None and record.team_id in subject.team_ids) or (
            record.department_id is not None and record.department_id == subject.department_id)
    return False


def check(subject: Subject, permission: str, record: RecordRef) -> None:
    """Raise NotFound for out-of-scope / foreign records, Forbidden for missing permission.

    Order matters: a record in another organization is NotFound even if the subject holds
    no permission at all, so existence never leaks across tenants.
    """
    if record.organization_id != subject.organization_id:
        raise NotFound()
    scope = require(subject, permission)
    if not in_scope(subject, scope, record):
        raise NotFound()


def criteria(subject: Subject, permission: str) -> ScopeCriteria:
    """List filter for ``permission``. Raises Forbidden when the permission is not held."""
    scope = require(subject, permission)
    org = subject.organization_id
    if scope == "all":
        return ScopeCriteria(org, all_records=True)
    users = frozenset({subject.user_id})
    if scope == "own":
        return ScopeCriteria(org, user_ids=users)
    if scope == "team":
        return ScopeCriteria(org, user_ids=users, team_ids=subject.team_ids)
    depts = frozenset({subject.department_id}) if subject.department_id else frozenset()
    return ScopeCriteria(org, user_ids=users, team_ids=subject.team_ids, department_ids=depts)


# ---------- role and permission changes (anti-escalation) ----------

def check_role_assignment(actor: Subject, target_user_id: UUID, role_grants: Iterable[Grant]) -> None:
    """Can ``actor`` give ``target_user_id`` a role made of ``role_grants``?

    - Requires admin.roles.manage (Super Admin has it implicitly).
    - Nobody changes their own roles, Super Admin included (a second admin must do it).
    - A non-super-admin cannot hand out a grant wider than one they hold themselves.
    """
    require(actor, "admin.roles.manage")
    if target_user_id == actor.user_id:
        raise EscalationDenied("You can't change your own roles. Ask another admin.")
    if actor.is_super_admin:
        return
    for gr in role_grants:
        held = scope_for(actor, gr.permission)
        if held is None or RANK[held] < RANK[gr.scope]:
            raise EscalationDenied(f"You can't grant {gr.permission} at {gr.scope} scope.")


def check_role_edit(actor: Subject, new_grants: Iterable[Grant], actor_holds_role: bool) -> None:
    """Can ``actor`` change a role's grants to ``new_grants``?

    - Only Super Admin edits role definitions (blueprint: only Super Admin manages roles).
    - Even Super Admin cannot edit a role it holds itself, so nobody widens their own access.
    """
    if not actor.is_super_admin:
        raise EscalationDenied("Only a Super Admin can change what a role allows.")
    if actor_holds_role:
        raise EscalationDenied("You can't edit a role you hold. Ask another Super Admin.")
    for gr in new_grants:
        if not isinstance(gr, Grant):
            raise ValueError("grants must be Grant objects")


def check_super_admin_change(actor: Subject, target_user_id: UUID, make_super_admin: bool, active_super_admins: int) -> None:
    if not actor.is_super_admin:
        raise EscalationDenied("Only a Super Admin can change Super Admin status.")
    if target_user_id == actor.user_id:
        raise EscalationDenied("You can't change your own Super Admin status.")
    if not make_super_admin and active_super_admins <= 1:
        raise EscalationDenied("At least one active Super Admin must remain.")
    if not actor.mfa_passed:
        raise EscalationDenied("Confirm MFA before changing Super Admin status.")

````

---

## `apps/api/app/core/__init__.py`

````python

````

---

## `apps/api/app/core/config.py`

````python
"""Settings from environment variables. Production refuses to start with unsafe values."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

UNSAFE_SECRETS = {"", "change-me", "changeme", "secret", "your-secret-key-change-in-production", "dev-secret"}


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    env: str = "development"                    # development | staging | production
    secret_key: str = "dev-secret"
    database_url: str = "postgresql+psycopg://mme:mme@localhost:5432/mme_os"
    redis_url: str = "redis://localhost:6379/0"
    web_origin: str = "http://localhost:3000"
    api_origin: str = "http://localhost:8000"
    google_client_id: str = ""
    google_client_secret: str = ""
    field_encryption_keys: str = ""             # "kid:base64,kid2:base64"
    field_encryption_active_kid: str = ""
    session_hours: int = 12
    session_idle_minutes: int = 120
    s3_endpoint: str = ""
    s3_bucket: str = "mme-os"
    bootstrap_super_admins: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.env != "development"

    def validate(self) -> None:
        problems = []
        if self.env not in ("development", "staging", "production"):
            problems.append("APP_ENV must be development, staging or production")
        if self.env != "development":
            if self.secret_key in UNSAFE_SECRETS or len(self.secret_key) < 32:
                problems.append("SECRET_KEY must be a random value of at least 32 characters")
            if not self.field_encryption_keys or not self.field_encryption_active_kid:
                problems.append("FIELD_ENCRYPTION_KEYS and FIELD_ENCRYPTION_ACTIVE_KID are required")
            if not self.google_client_id or not self.google_client_secret:
                problems.append("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required")
            if not self.web_origin.startswith("https://") or not self.api_origin.startswith("https://"):
                problems.append("WEB_ORIGIN and API_ORIGIN must use https")
            if "mme:mme@" in self.database_url:
                problems.append("DATABASE_URL still uses the development credentials")
        if problems:
            raise ConfigError("Refusing to start: " + "; ".join(problems))


def load_settings(env: Mapping[str, str] = os.environ) -> Settings:
    s = Settings(
        env=env.get("APP_ENV", "development"),
        secret_key=env.get("SECRET_KEY", "dev-secret"),
        database_url=env.get("DATABASE_URL", Settings.database_url),
        redis_url=env.get("REDIS_URL", Settings.redis_url),
        web_origin=env.get("WEB_ORIGIN", Settings.web_origin),
        api_origin=env.get("API_ORIGIN", Settings.api_origin),
        google_client_id=env.get("GOOGLE_CLIENT_ID", ""),
        google_client_secret=env.get("GOOGLE_CLIENT_SECRET", ""),
        field_encryption_keys=env.get("FIELD_ENCRYPTION_KEYS", ""),
        field_encryption_active_kid=env.get("FIELD_ENCRYPTION_ACTIVE_KID", ""),
        session_hours=int(env.get("SESSION_HOURS", "12")),
        session_idle_minutes=int(env.get("SESSION_IDLE_MINUTES", "120")),
        s3_endpoint=env.get("S3_ENDPOINT", ""),
        s3_bucket=env.get("S3_BUCKET", "mme-os"),
        bootstrap_super_admins=tuple(e.strip().lower() for e in env.get("BOOTSTRAP_SUPER_ADMINS", "").split(",") if e.strip()),
    )
    s.validate()
    return s

````

---

## `apps/api/app/core/crypto.py`

````python
"""Field-level encryption for secrets stored in the database (MFA secrets, integration tokens).

AES-256-GCM with a key id in every ciphertext ("v1.<kid>.<nonce>.<ciphertext>") so keys can
rotate: new writes use the active key, old values still decrypt with retired keys until
re-encrypted. Keys come from the secrets manager via FIELD_ENCRYPTION_KEYS, never the repo.
"""
from __future__ import annotations

import base64
import os
from typing import Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class FieldCipher:
    def __init__(self, keys: Mapping[str, bytes], active_kid: str):
        if active_kid not in keys:
            raise ValueError("active key id missing")
        for kid, key in keys.items():
            if len(key) != 32:
                raise ValueError(f"key {kid} must be 32 bytes")
            if "." in kid:
                raise ValueError("key id may not contain '.'")
        self._keys = dict(keys)
        self._active = active_kid

    @classmethod
    def from_env(cls, spec: str, active_kid: str) -> "FieldCipher":
        """spec = "kid1:base64key,kid2:base64key" """
        keys = {}
        for part in filter(None, (p.strip() for p in spec.split(","))):
            kid, b64 = part.split(":", 1)
            keys[kid] = _b64d(b64)
        return cls(keys, active_kid)

    def encrypt(self, plaintext: str, context: str) -> str:
        """``context`` (e.g. "mfa:<user id>") is bound as associated data: a ciphertext copied
        to another row fails to decrypt."""
        nonce = os.urandom(12)
        ct = AESGCM(self._keys[self._active]).encrypt(nonce, plaintext.encode(), context.encode())
        return f"v1.{self._active}.{_b64e(nonce)}.{_b64e(ct)}"

    def decrypt(self, token: str, context: str) -> str:
        version, kid, nonce, ct = token.split(".")
        if version != "v1" or kid not in self._keys:
            raise ValueError("unknown ciphertext version or key")
        return AESGCM(self._keys[kid]).decrypt(_b64d(nonce), _b64d(ct), context.encode()).decode()

    def needs_rotation(self, token: str) -> bool:
        return token.split(".")[1] != self._active

````

---

## `apps/api/app/core/db.py`

````python
from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import load_settings

_settings = load_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """One transaction per request: the change and its audit event commit together or not at all."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

````

---

## `apps/api/app/core/deps.py`

````python
"""Request dependencies: who is calling, what they may do, and the per-route permission check.

Every route must declare its access with exactly one of:
    Depends(requires("module.resource.action"))   -> signed-in, MFA-satisfied, holding the permission
    Depends(signed_in)                             -> any signed-in user (e.g. /me)
    public_route(...)                              -> no session (sign-in endpoints, health)
tests/api/test_route_permissions.py fails the build if a route declares none.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..audit.writer import RequestContext
from ..authz import engine as E
from .config import load_settings
from .db import get_db
from .models import RoleGrant, Session, TeamMember, User, UserRole
from .security import token_hash, verify_csrf

SESSION_COOKIE = "mme_session"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

settings = load_settings()

# route path+method -> declared access ("public", "signed_in" or a permission string)
ROUTE_ACCESS: dict[str, str] = {}


@dataclass
class Caller:
    user: User
    session: Session
    subject: E.Subject
    ctx: RequestContext
    raw_token: str


def _ctx(request: Request, org_id: uuid.UUID, user_id: Optional[uuid.UUID]) -> RequestContext:
    return RequestContext(organization_id=org_id, actor_user_id=user_id,
                          ip=request.client.host if request.client else None,
                          user_agent=request.headers.get("user-agent"),
                          request_id=request.headers.get("x-request-id") or getattr(request.state, "request_id", None))


def build_subject(db: DbSession, user: User, mfa_passed: bool) -> E.Subject:
    rows = db.execute(
        select(RoleGrant.permission, RoleGrant.scope)
        .join(UserRole, UserRole.role_id == RoleGrant.role_id)
        .where(UserRole.user_id == user.id, RoleGrant.organization_id == user.organization_id)
    ).all()
    teams = db.execute(select(TeamMember.team_id, TeamMember.is_manager).where(TeamMember.user_id == user.id)).all()
    return E.Subject(
        user_id=user.id, organization_id=user.organization_id,
        grants=tuple(E.Grant(p, s) for p, s in rows),
        team_ids=frozenset(t for t, _ in teams), managed_team_ids=frozenset(t for t, m in teams if m),
        department_id=user.department_id, is_super_admin=user.is_super_admin,
        mfa_passed=mfa_passed, active=user.status == "active",
    )


def _load_caller(request: Request, db: DbSession, allow_mfa_pending: bool) -> Caller:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    sess = db.scalar(select(Session).where(Session.token_hash == token_hash(raw)))
    now = datetime.now(timezone.utc)
    idle = timedelta(minutes=settings.session_idle_minutes)
    if sess is None or sess.revoked_at is not None or sess.expires_at <= now or sess.last_seen_at + idle <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has ended. Sign in again.")
    user = db.get(User, sess.user_id)
    if user is None or user.status != "active":
        sess.revoked_at = now
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account is not active.")
    if request.method not in SAFE_METHODS and not verify_csrf(raw, settings.secret_key, request.headers.get(CSRF_HEADER)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Security check failed. Reload the page and try again.")
    needs_mfa = user.mfa_required or user.is_super_admin
    if needs_mfa and not sess.mfa_passed and not allow_mfa_pending:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Confirm your authenticator code to continue.", headers={"x-mfa-required": "1"})
    if (now - sess.last_seen_at) > timedelta(minutes=1):
        sess.last_seen_at = now
    subject = build_subject(db, user, sess.mfa_passed)
    return Caller(user=user, session=sess, subject=subject, ctx=_ctx(request, user.organization_id, user.id), raw_token=raw)


def signed_in(request: Request, db: DbSession = Depends(get_db)) -> Caller:
    return _load_caller(request, db, allow_mfa_pending=False)


def signed_in_mfa_pending(request: Request, db: DbSession = Depends(get_db)) -> Caller:
    """Only for the MFA setup/verify endpoints themselves."""
    return _load_caller(request, db, allow_mfa_pending=True)


def requires(permission: str) -> Callable[..., Caller]:
    """Route dependency: 403 unless the caller holds ``permission`` at some scope.
    Record-level scope is then enforced in the service with engine.check / engine.criteria."""
    E.scope_for(E.Subject(user_id=uuid.uuid4(), organization_id=uuid.uuid4()), permission)  # validates the name at import

    def dep(caller: Caller = Depends(signed_in)) -> Caller:
        try:
            E.require(caller.subject, permission)
        except E.Forbidden:
            if E.requires_mfa(permission) and not caller.subject.mfa_passed:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "This action needs your authenticator code.", headers={"x-mfa-required": "1"})
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do that.")
        return caller

    dep.__mme_permission__ = permission  # read by the route-permission test
    return dep


def public_context(request: Request, org_id: uuid.UUID) -> RequestContext:
    return _ctx(request, org_id, None)


def public() -> None:
    """Marker dependency for routes that intentionally need no session (sign-in, health)."""
    return None


public.__mme_public__ = True  # type: ignore[attr-defined]

````

---

## `apps/api/app/core/google_oidc.py`

````python
"""Google sign-in (OpenID Connect, authorization code flow with PKCE).

The ID token is verified locally: signature against Google's published keys, issuer,
audience (our client id), expiry, nonce, and a verified email.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlencode

import jwt  # PyJWT

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    name: str
    picture: Optional[str]
    hosted_domain: Optional[str]


@dataclass(frozen=True)
class AuthRequest:
    url: str
    state: str
    nonce: str
    code_verifier: str


def build_auth_request(client_id: str, redirect_uri: str, hosted_domain: Optional[str] = None) -> AuthRequest:
    state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    params = {
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": "openid email profile", "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account",
    }
    if hosted_domain:
        params["hd"] = hosted_domain  # a UI hint only; the server still checks access itself
    return AuthRequest(f"{AUTH_URL}?{urlencode(params)}", state, nonce, verifier)


class InvalidGoogleToken(Exception):
    pass


_jwks_client: Optional[jwt.PyJWKClient] = None


def _default_key_resolver(token: str):
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600)
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_id_token(id_token: str, client_id: str, nonce: str,
                    key_resolver: Callable[[str], object] = _default_key_resolver,
                    leeway: int = 60) -> GoogleIdentity:
    try:
        key = key_resolver(id_token)
        claims = jwt.decode(
            id_token, key=key, algorithms=["RS256"], audience=client_id, leeway=leeway,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except Exception as exc:  # noqa: BLE001 — every failure is the same answer to the caller
        raise InvalidGoogleToken(str(exc)) from exc
    if claims.get("iss") not in ISSUERS:
        raise InvalidGoogleToken("bad issuer")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise InvalidGoogleToken("nonce mismatch")
    if claims.get("email_verified") is not True or not claims.get("email"):
        raise InvalidGoogleToken("email not verified")
    return GoogleIdentity(
        subject=str(claims["sub"]), email=str(claims["email"]).lower(),
        name=str(claims.get("name", ""))[:200], picture=claims.get("picture"), hosted_domain=claims.get("hd"),
    )

````

---

## `apps/api/app/core/models.py`

````python
"""SQLAlchemy models mirroring migrations/sql/0001_foundation.sql (the SQL file is the source of truth;
tests/api/test_schema_parity.py checks the two agree)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import ARRAY, BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


def org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text, server_default="internal")
    settings: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = mapped_column(Text)
    head_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    email: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text, server_default="")
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    google_subject: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    is_super_admin: Mapped[bool] = mapped_column(Boolean, server_default="false")
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"))
    mfa_required: Mapped[bool] = mapped_column(Boolean, server_default="false")
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employee: Mapped[Optional["Employee"]] = relationship(back_populates="user", uselist=False, foreign_keys="Employee.user_id")


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, server_default="custom")
    lead_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class TeamMember(Base):
    __tablename__ = "team_members"
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    organization_id: Mapped[uuid.UUID] = org_fk()
    is_manager: Mapped[bool] = mapped_column(Boolean, server_default="false")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Employee(Base):
    __tablename__ = "employees"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    organization_id: Mapped[uuid.UUID] = org_fk()
    employee_code: Mapped[Optional[str]] = mapped_column(Text)
    designation: Mapped[Optional[str]] = mapped_column(Text)
    manager_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    employment_type: Mapped[str] = mapped_column(Text, server_default="full_time")
    joined_on: Mapped[Optional[date]] = mapped_column(Date)
    left_on: Mapped[Optional[date]] = mapped_column(Date)
    phone: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="employee", foreign_keys=[user_id])


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    is_system: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    grants: Mapped[list["RoleGrant"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class RoleGrant(Base):
    __tablename__ = "role_grants"
    id: Mapped[uuid.UUID] = uuid_pk()
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"))
    organization_id: Mapped[uuid.UUID] = org_fk()
    permission: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    organization_id: Mapped[uuid.UUID] = org_fk()
    granted_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_fk()
    email: Mapped[str] = mapped_column(Text)
    role_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}")
    team_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}")
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    organization_id: Mapped[uuid.UUID] = org_fk()
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    mfa_passed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    ip: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class MfaFactor(Base):
    __tablename__ = "mfa_factors"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    organization_id: Mapped[uuid.UUID] = org_fk()
    kind: Mapped[str] = mapped_column(Text, server_default="totp")
    secret_enc: Mapped[str] = mapped_column(Text)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_used_step: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[uuid.UUID] = org_fk()
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[Optional[str]] = mapped_column(Text)
    target_id: Mapped[Optional[str]] = mapped_column(Text)
    before: Mapped[Optional[dict]] = mapped_column(JSONB)
    after: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    request_id: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[uuid.UUID] = org_fk()
    topic: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

````

---

## `apps/api/app/core/ratelimit.py`

````python
"""Fixed-window rate limits in Redis (in-memory fallback for local development and tests)."""
from __future__ import annotations

import threading
import time
from typing import Optional, Protocol


class Limiter(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> bool: ...


class MemoryLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, tuple[int, int]] = {}

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        bucket = int(time.time() // window_seconds)
        with self._lock:
            b, n = self._counts.get(key, (bucket, 0))
            if b != bucket:
                b, n = bucket, 0
            n += 1
            self._counts[key] = (b, n)
            return n <= limit


class RedisLimiter:
    def __init__(self, url: str) -> None:
        import redis  # imported lazily so unit tests don't need the package
        self._r = redis.Redis.from_url(url)

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        bucket = int(time.time() // window_seconds)
        k = f"rl:{key}:{bucket}"
        pipe = self._r.pipeline()
        pipe.incr(k)
        pipe.expire(k, window_seconds + 5)
        count, _ = pipe.execute()
        return int(count) <= limit


_limiter: Optional[Limiter] = None


def get_limiter() -> Limiter:
    global _limiter
    if _limiter is None:
        import os
        from .config import load_settings
        s = load_settings()
        backend = os.environ.get("RATE_LIMIT_BACKEND", "redis")
        if backend == "memory" and s.is_production:
            raise RuntimeError("RATE_LIMIT_BACKEND=memory is not allowed in production")
        _limiter = MemoryLimiter() if backend == "memory" else RedisLimiter(s.redis_url)
    return _limiter


# name: (limit, window seconds)
LIMITS = {
    "login_ip": (20, 300),
    "login_email": (8, 900),
    "mfa_user": (6, 300),
    "invite_user": (30, 3600),
    "export_user": (20, 3600),
    "api_user": (600, 60),
}

````

---

## `apps/api/app/core/security.py`

````python
"""Passwords, one-time codes, session and CSRF tokens, invitation tokens.

Standard library only (hashlib.scrypt, hmac, secrets), so these primitives are unit-tested
without the web stack.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from typing import Optional
from urllib.parse import quote

# ---------- passwords (scrypt, memory-hard) ----------
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 15, 8, 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024
MIN_PASSWORD_LENGTH = 12


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, maxmem=_SCRYPT_MAXMEM, dklen=32)
    return "scrypt${}${}${}${}${}".format(_SCRYPT_N, _SCRYPT_R, _SCRYPT_P, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        # Burn similar time so missing accounts are not distinguishable by timing.
        hashlib.scrypt(b"x", salt=b"0" * 16, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, maxmem=_SCRYPT_MAXMEM, dklen=32)
        return False
    try:
        _, n, r, p, salt_b64, dk_b64 = stored.split("$")
        dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p), maxmem=_SCRYPT_MAXMEM, dklen=32)
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except (ValueError, TypeError):
        return False


# ---------- TOTP (RFC 6238, SHA-1, 6 digits, 30 s) ----------
TOTP_STEP = 30
TOTP_DIGITS = 6


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _b32decode(secret: str) -> bytes:
    s = secret.upper().replace(" ", "")
    return base64.b32decode(s + "=" * (-len(s) % 8))


def totp_at(secret: str, step: int) -> str:
    digest = hmac.new(_b32decode(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** TOTP_DIGITS)
    return str(code).zfill(TOTP_DIGITS)


def verify_totp(secret: str, code: str, last_used_step: Optional[int], now: Optional[float] = None, window: int = 1) -> Optional[int]:
    """Return the matched time step (to store as last_used_step), or None.

    Accepts ±``window`` steps for clock drift and rejects any step at or before the last
    one used, so a code can't be replayed.
    """
    code = (code or "").strip().replace(" ", "")
    if len(code) != TOTP_DIGITS or not code.isdigit():
        return None
    current = int((time.time() if now is None else now) // TOTP_STEP)
    for step in range(current - window, current + window + 1):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(totp_at(secret, step), code):
            return step
    return None


def totp_uri(secret: str, email: str, issuer: str = "MME OS") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}&digits={TOTP_DIGITS}&period={TOTP_STEP}"


# ---------- opaque tokens (sessions, invitations, API keys) ----------

def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    """Only this hash is stored; a database leak does not reveal live tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_api_key(env: str = "live") -> tuple[str, str]:
    raw = new_token(32)
    key = f"mme_{env}_{raw}"
    return key, key[:13]


# ---------- CSRF (double-submit, bound to the session) ----------

def csrf_token(session_token: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), b"csrf:" + session_token.encode(), hashlib.sha256).hexdigest()


def verify_csrf(session_token: str, secret_key: str, presented: Optional[str]) -> bool:
    if not presented:
        return False
    return hmac.compare_digest(csrf_token(session_token, secret_key), presented)

````

---

## `apps/api/app/main.py`

````python
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .audit.router import router as audit_router
from .authz import engine as E
from .core.config import load_settings
from .core.db import engine
from .core.deps import public
from .modules.access.router import router as access_router
from .modules.identity.router import me_router, router as auth_router
from .modules.org.router import router as org_router

settings = load_settings()  # raises ConfigError on unsafe production settings
log = logging.getLogger("mme")

app = FastAPI(
    title="MME OS API", version="0.1.0",
    docs_url="/api/docs" if not settings.is_production else None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware, allow_origins=[settings.web_origin], allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["content-type", "x-csrf-token", "x-request-id", "idempotency-key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    response = await call_next(request)
    response.headers["x-request-id"] = request.state.request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    response.headers["cache-control"] = "no-store"
    if settings.cookie_secure:
        response.headers["strict-transport-security"] = "max-age=63072000; includeSubDomains"
    return response


@app.exception_handler(E.NotFound)
async def _nf(_: Request, __: E.NotFound):
    return JSONResponse({"error": {"code": "not_found", "message": "Not found."}}, status_code=404)


@app.exception_handler(E.Forbidden)
async def _fb(_: Request, __: E.Forbidden):
    return JSONResponse({"error": {"code": "forbidden", "message": "You don't have permission to do that."}}, status_code=403)


@app.exception_handler(E.EscalationDenied)
async def _esc(_: Request, exc: E.EscalationDenied):
    return JSONResponse({"error": {"code": "forbidden", "message": str(exc)}}, status_code=403)


api = APIRouter(prefix="/api/v1")


@api.get("/health", dependencies=[Depends(public)])
def health() -> dict:
    with engine.connect() as c:
        c.execute(text("select 1"))
    return {"ok": True}


api.include_router(auth_router)
api.include_router(me_router)
api.include_router(access_router)
api.include_router(org_router)
api.include_router(audit_router)
app.include_router(api)

````

---

## `apps/api/app/modules/__init__.py`

````python

````

---

## `apps/api/app/modules/access/__init__.py`

````python

````

---

## `apps/api/app/modules/access/router.py`

````python
"""Super Admin control center: employees' accounts, invitations, roles and grants."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import record
from ...authz import engine as E
from ...authz.catalog import ACTIONS, RESOURCES, SCOPES
from ...core.db import get_db
from ...core.deps import Caller, requires
from ...core.models import Employee, Invitation, MfaFactor, Role, RoleGrant, Team, TeamMember, User, UserRole
from ...core.ratelimit import LIMITS, get_limiter
from ...core.security import new_token, token_hash
from ..identity.service import revoke_all_sessions

router = APIRouter(prefix="/admin", tags=["admin"])


def _role_out(r: Role) -> dict:
    return {"id": str(r.id), "key": r.key, "name": r.name, "description": r.description, "is_system": r.is_system,
            "grants": sorted(({"permission": g.permission, "scope": g.scope} for g in r.grants), key=lambda x: x["permission"])}


def _user_out(u: User, roles: list[str]) -> dict:
    return {"id": str(u.id), "email": u.email, "full_name": u.full_name, "status": u.status, "is_super_admin": u.is_super_admin,
            "department_id": str(u.department_id) if u.department_id else None, "roles": roles,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}


def _get_user(db: DbSession, caller: Caller, user_id: uuid.UUID) -> User:
    u = db.get(User, user_id)
    if u is None or u.organization_id != caller.user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return u


def _get_role(db: DbSession, caller: Caller, role_id: uuid.UUID) -> Role:
    r = db.get(Role, role_id)
    if r is None or r.organization_id != caller.user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return r


def _deny(exc: E.EscalationDenied) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


# ---------- catalog ----------
@router.get("/permissions")
def permission_catalog(caller: Caller = Depends(requires("admin.roles.view"))) -> dict:
    return {"resources": [{"key": k, "label": v} for k, v in RESOURCES.items()], "actions": list(ACTIONS), "scopes": list(SCOPES)}


# ---------- users ----------
@router.get("/users")
def list_users(status_: Optional[str] = None, caller: Caller = Depends(requires("admin.users.view")), db: DbSession = Depends(get_db)) -> list[dict]:
    q = select(User).where(User.organization_id == caller.user.organization_id).order_by(User.full_name, User.email)
    if status_ in ("active", "deactivated"):
        q = q.where(User.status == status_)
    users = db.scalars(q).all()
    roles = db.execute(select(UserRole.user_id, Role.key).join(Role, Role.id == UserRole.role_id)
                       .where(UserRole.organization_id == caller.user.organization_id)).all()
    by_user: dict[uuid.UUID, list[str]] = {}
    for uid, key in roles:
        by_user.setdefault(uid, []).append(key)
    return [_user_out(u, sorted(by_user.get(u.id, []))) for u in users]


class InviteBody(BaseModel):
    email: EmailStr
    role_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    team_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    department_id: Optional[uuid.UUID] = None
    expires_in_days: int = Field(default=7, ge=1, le=30)


@router.post("/invitations", status_code=201)
def invite(body: InviteBody, caller: Caller = Depends(requires("admin.users.create")), db: DbSession = Depends(get_db)) -> dict:
    limit, window = LIMITS["invite_user"]
    if not get_limiter().hit(f"invite_user:{caller.user.id}", limit, window):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many invitations this hour.")
    org = caller.user.organization_id
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.organization_id == org, User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This person already has an account.")
    roles = [_get_role(db, caller, rid) for rid in body.role_ids]
    try:
        for r in roles:  # can the inviter hand out these roles? (self-check is n/a: the invitee is someone else)
            E.check_role_assignment(caller.subject, uuid.uuid4(), [E.Grant(g.permission, g.scope) for g in r.grants])
    except E.EscalationDenied as exc:
        raise _deny(exc)
    for tid in body.team_ids:
        t = db.get(Team, tid)
        if t is None or t.organization_id != org:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found.")
    db.execute(update(Invitation).where(Invitation.organization_id == org, Invitation.email == email,
                                        Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None))
               .values(revoked_at=datetime.now(timezone.utc)))
    raw = new_token()
    inv = Invitation(organization_id=org, email=email, role_ids=[r.id for r in roles], team_ids=body.team_ids,
                     department_id=body.department_id, token_hash=token_hash(raw), invited_by=caller.user.id,
                     expires_at=datetime.now(timezone.utc) + timedelta(days=body.expires_in_days))
    db.add(inv)
    db.flush()
    record(db, caller.ctx, "admin.user_invited", "invitation", inv.id, after={"email": email, "roles": [r.key for r in roles]})
    # The link is shown once to the admin (and emailed by the worker in Milestone 2).
    return {"id": str(inv.id), "email": email, "accept_path": f"/sign-in?invite={raw}", "expires_at": inv.expires_at.isoformat()}


class UserPatch(BaseModel):
    status: Optional[Literal["active", "deactivated"]] = None
    department_id: Optional[uuid.UUID] = None
    full_name: Optional[str] = Field(default=None, max_length=200)
    reassign_to: Optional[uuid.UUID] = None  # who takes over their teams and reports when deactivated


@router.patch("/users/{user_id}")
def update_user(user_id: uuid.UUID, body: UserPatch, caller: Caller = Depends(requires("admin.users.edit")), db: DbSession = Depends(get_db)) -> dict:
    u = _get_user(db, caller, user_id)
    before = _user_out(u, [])
    if body.status == "deactivated" and u.status == "active":
        if u.id == caller.user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't deactivate your own account.")
        if u.is_super_admin and not caller.subject.is_super_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a Super Admin can deactivate a Super Admin.")
        if body.reassign_to:
            heir = _get_user(db, caller, body.reassign_to)
            if heir.status != "active" or heir.id == u.id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose an active colleague to take over.")
            db.execute(update(Team).where(Team.lead_user_id == u.id).values(lead_user_id=heir.id))
            db.execute(update(Employee).where(Employee.manager_user_id == u.id).values(manager_user_id=heir.id))
        u.status, u.deactivated_at = "deactivated", datetime.now(timezone.utc)
        ended = revoke_all_sessions(db, u.id)
        record(db, caller.ctx, "admin.user_deactivated", "user", u.id, before=before,
               after={"sessions_ended": ended, "reassigned_to": str(body.reassign_to) if body.reassign_to else None})
    elif body.status == "active" and u.status == "deactivated":
        u.status, u.deactivated_at = "active", None
        record(db, caller.ctx, "admin.user_reactivated", "user", u.id)
    if body.department_id is not None or body.full_name is not None:
        if body.full_name is not None:
            u.full_name = body.full_name.strip()
        if body.department_id is not None:
            u.department_id = body.department_id
        record(db, caller.ctx, "admin.user_updated", "user", u.id, before=before, after=_user_out(u, []))
    db.flush()
    return _user_out(u, [])


class RolesBody(BaseModel):
    role_ids: list[uuid.UUID] = Field(max_length=10)


@router.put("/users/{user_id}/roles")
def set_user_roles(user_id: uuid.UUID, body: RolesBody, caller: Caller = Depends(requires("admin.roles.manage")), db: DbSession = Depends(get_db)) -> dict:
    u = _get_user(db, caller, user_id)
    roles = [_get_role(db, caller, rid) for rid in body.role_ids]
    try:
        E.check_role_assignment(caller.subject, u.id, [E.Grant(g.permission, g.scope) for r in roles for g in r.grants])
    except E.EscalationDenied as exc:
        raise _deny(exc)
    before = sorted(db.scalars(select(Role.key).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == u.id)).all())
    db.execute(delete(UserRole).where(UserRole.user_id == u.id))
    for r in roles:
        db.add(UserRole(user_id=u.id, role_id=r.id, organization_id=u.organization_id, granted_by=caller.user.id))
    record(db, caller.ctx, "admin.user_roles_changed", "user", u.id, before={"roles": before}, after={"roles": sorted(r.key for r in roles)})
    return {"roles": sorted(r.key for r in roles)}


class SuperAdminBody(BaseModel):
    is_super_admin: bool


@router.put("/users/{user_id}/super-admin")
def set_super_admin(user_id: uuid.UUID, body: SuperAdminBody, caller: Caller = Depends(requires("admin.users.manage")), db: DbSession = Depends(get_db)) -> dict:
    u = _get_user(db, caller, user_id)
    count = db.scalar(select(func.count()).select_from(User).where(User.organization_id == u.organization_id, User.is_super_admin, User.status == "active")) or 0
    try:
        E.check_super_admin_change(caller.subject, u.id, body.is_super_admin, count)
    except E.EscalationDenied as exc:
        raise _deny(exc)
    before = u.is_super_admin
    u.is_super_admin = body.is_super_admin
    if body.is_super_admin:
        u.mfa_required = True
    revoke_all_sessions(db, u.id)  # new access level takes effect at next sign-in, with MFA
    record(db, caller.ctx, "admin.super_admin_changed", "user", u.id, before={"is_super_admin": before}, after={"is_super_admin": u.is_super_admin})
    return {"is_super_admin": u.is_super_admin}


@router.delete("/users/{user_id}/mfa")
def reset_mfa(user_id: uuid.UUID, caller: Caller = Depends(requires("admin.users.manage")), db: DbSession = Depends(get_db)) -> dict:
    u = _get_user(db, caller, user_id)
    if u.id == caller.user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ask another admin to reset your authenticator.")
    db.execute(delete(MfaFactor).where(MfaFactor.user_id == u.id))
    revoke_all_sessions(db, u.id)
    record(db, caller.ctx, "admin.mfa_reset", "user", u.id)
    return {"ok": True}


# ---------- roles ----------
class GrantIn(BaseModel):
    permission: str
    scope: Literal["own", "team", "department", "all"]


class RoleIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{2,60}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    grants: list[GrantIn] = Field(default_factory=list, max_length=200)


def _grants(items: list[GrantIn]) -> list[E.Grant]:
    try:
        return [E.Grant(g.permission, g.scope) for g in items]
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/roles")
def list_roles(caller: Caller = Depends(requires("admin.roles.view")), db: DbSession = Depends(get_db)) -> list[dict]:
    return [_role_out(r) for r in db.scalars(select(Role).where(Role.organization_id == caller.user.organization_id).order_by(Role.name)).all()]


@router.post("/roles", status_code=201)
def create_role(body: RoleIn, caller: Caller = Depends(requires("admin.roles.manage")), db: DbSession = Depends(get_db)) -> dict:
    grants = _grants(body.grants)
    try:
        E.check_role_edit(caller.subject, grants, actor_holds_role=False)
    except E.EscalationDenied as exc:
        raise _deny(exc)
    if db.scalar(select(Role.id).where(Role.organization_id == caller.user.organization_id, Role.key == body.key)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A role with this key exists.")
    role = Role(organization_id=caller.user.organization_id, key=body.key, name=body.name, description=body.description)
    db.add(role)
    db.flush()
    for g in grants:
        db.add(RoleGrant(role_id=role.id, organization_id=role.organization_id, permission=g.permission, scope=g.scope))
    db.flush()
    db.refresh(role)
    record(db, caller.ctx, "admin.role_created", "role", role.id, after=_role_out(role))
    return _role_out(role)


@router.put("/roles/{role_id}")
def replace_role(role_id: uuid.UUID, body: RoleIn, caller: Caller = Depends(requires("admin.roles.manage")), db: DbSession = Depends(get_db)) -> dict:
    role = _get_role(db, caller, role_id)
    holds = db.scalar(select(UserRole.user_id).where(UserRole.user_id == caller.user.id, UserRole.role_id == role.id)) is not None
    grants = _grants(body.grants)
    try:
        E.check_role_edit(caller.subject, grants, actor_holds_role=holds)
    except E.EscalationDenied as exc:
        raise _deny(exc)
    before = _role_out(role)
    role.name, role.description = body.name, body.description
    db.execute(delete(RoleGrant).where(RoleGrant.role_id == role.id))
    for g in grants:
        db.add(RoleGrant(role_id=role.id, organization_id=role.organization_id, permission=g.permission, scope=g.scope))
    db.flush()
    db.refresh(role)
    record(db, caller.ctx, "admin.role_changed", "role", role.id, before=before, after=_role_out(role))
    return _role_out(role)


@router.delete("/roles/{role_id}")
def delete_role(role_id: uuid.UUID, caller: Caller = Depends(requires("admin.roles.manage")), db: DbSession = Depends(get_db)) -> dict:
    role = _get_role(db, caller, role_id)
    if role.is_system:
        raise HTTPException(status.HTTP_409_CONFLICT, "Built-in roles can be edited but not deleted.")
    try:
        E.check_role_edit(caller.subject, [], actor_holds_role=False)
    except E.EscalationDenied as exc:
        raise _deny(exc)
    holders = db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id)) or 0
    if holders:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{holders} people still hold this role. Move them first.")
    before = _role_out(role)
    db.delete(role)
    record(db, caller.ctx, "admin.role_deleted", "role", role_id, before=before)
    return {"ok": True}

````

---

## `apps/api/app/modules/identity/__init__.py`

````python

````

---

## `apps/api/app/modules/identity/policy.py`

````python
"""Who may sign in. Pure function so every branch is unit-tested."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional


class Decision(str, Enum):
    SIGN_IN = "sign_in"                    # existing active user
    CREATE_FROM_INVITE = "create_invite"   # new user from an open invitation
    CREATE_FROM_DOMAIN = "create_domain"   # new user on an allowed company domain, base role only
    DENY_DEACTIVATED = "deny_deactivated"
    DENY_NOT_INVITED = "deny_not_invited"
    DENY_SUBJECT_MISMATCH = "deny_subject_mismatch"


@dataclass(frozen=True)
class ExistingUser:
    status: str
    google_subject: Optional[str]


def decide_sign_in(email: str, google_subject: Optional[str], existing: Optional[ExistingUser],
                   has_open_invitation: bool, allowed_domains: Iterable[str]) -> Decision:
    email = email.lower()
    if existing is not None:
        if existing.status != "active":
            return Decision.DENY_DEACTIVATED
        # Once linked, an account only accepts the same Google identity (blocks a recycled address).
        if google_subject and existing.google_subject and existing.google_subject != google_subject:
            return Decision.DENY_SUBJECT_MISMATCH
        return Decision.SIGN_IN
    if has_open_invitation:
        return Decision.CREATE_FROM_INVITE
    domain = email.rsplit("@", 1)[-1]
    if domain and domain in {d.lower().lstrip("@") for d in allowed_domains}:
        return Decision.CREATE_FROM_DOMAIN
    return Decision.DENY_NOT_INVITED


DENIAL_MESSAGES = {
    Decision.DENY_DEACTIVATED: "This account has been deactivated. Contact your administrator.",
    Decision.DENY_NOT_INVITED: "This account isn't invited to MME OS. Ask a Super Admin for an invitation.",
    Decision.DENY_SUBJECT_MISMATCH: "This email is linked to a different Google account. Contact your administrator.",
}

````

---

## `apps/api/app/modules/identity/router.py`

````python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import record, record_now
from ...authz import engine as E
from ...core import google_oidc as G
from ...core.config import load_settings
from ...core.db import get_db
from ...core.deps import Caller, public, public_context, signed_in_mfa_pending
from ...core.models import MfaFactor, Role, TeamMember, User, UserRole
from ...core.ratelimit import LIMITS, get_limiter
from ...core.security import csrf_token, new_totp_secret, totp_uri, verify_password, verify_totp
from . import service as S
from .policy import DENIAL_MESSAGES, Decision, ExistingUser, decide_sign_in

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["me"])
settings = load_settings()
OAUTH_COOKIE = "mme_oauth"
_signer = URLSafeTimedSerializer(settings.secret_key, salt="google-oauth")


def _limit(name: str, key: str) -> None:
    limit, window = LIMITS[name]
    if not get_limiter().hit(f"{name}:{key}", limit, window):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Wait a few minutes and try again.")


def _safe_next(path: Optional[str]) -> str:
    return path if path and path.startswith("/") and not path.startswith("//") else "/"


def _redirect_web(path: str, error: Optional[str] = None) -> RedirectResponse:
    url = settings.web_origin + path + (("?error=" + quote(error)) if error else "")
    return RedirectResponse(url, status_code=303)


# ---------- Google ----------
@router.get("/google/start", dependencies=[Depends(public)])
def google_start(request: Request, next: Optional[str] = None, invite: Optional[str] = None) -> RedirectResponse:
    _limit("login_ip", request.client.host if request.client else "unknown")
    req = G.build_auth_request(settings.google_client_id, settings.api_origin + "/api/v1/auth/google/callback")
    resp = RedirectResponse(req.url, status_code=303)
    payload = _signer.dumps({"s": req.state, "n": req.nonce, "v": req.code_verifier, "next": _safe_next(next), "invite": invite})
    resp.set_cookie(OAUTH_COOKIE, payload, max_age=600, httponly=True, secure=settings.cookie_secure, samesite="lax",
                    path="/api/v1/auth/google", domain=S.COOKIE_DOMAIN)
    return resp


@router.get("/google/callback", dependencies=[Depends(public)])
def google_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None,
                    db: DbSession = Depends(get_db)) -> RedirectResponse:
    try:
        data = _signer.loads(request.cookies.get(OAUTH_COOKIE, ""), max_age=600)
    except BadSignature:
        return _redirect_web("/sign-in", "Sign-in expired. Try again.")
    if not code or not state or state != data["s"]:
        return _redirect_web("/sign-in", "Sign-in could not be verified. Try again.")
    try:
        r = httpx.post(G.TOKEN_URL, data={
            "code": code, "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
            "redirect_uri": settings.api_origin + "/api/v1/auth/google/callback", "grant_type": "authorization_code",
            "code_verifier": data["v"]}, timeout=10)
        r.raise_for_status()
        ident = G.verify_id_token(r.json()["id_token"], settings.google_client_id, data["n"])
    except (httpx.HTTPError, KeyError, G.InvalidGoogleToken):
        return _redirect_web("/sign-in", "Google sign-in failed. Try again.")

    org = S.default_org(db)
    _limit("login_email", ident.email)
    ctx = public_context(request, org.id)
    user = db.scalar(select(User).where(User.organization_id == org.id, User.email == ident.email))
    invitation = S.open_invitation(db, org.id, ident.email, data.get("invite"))
    bootstrap = ident.email in settings.bootstrap_super_admins and user is None
    decision = Decision.CREATE_FROM_INVITE if bootstrap else decide_sign_in(
        ident.email, ident.subject, ExistingUser(user.status, user.google_subject) if user else None,
        invitation is not None, (org.settings or {}).get("allowed_domains", []))

    if decision in DENIAL_MESSAGES:
        record(db, ctx, "auth.login_failed", "email", ident.email, after={"reason": decision.value})
        return _redirect_web("/sign-in", DENIAL_MESSAGES[decision])
    if user is None:
        user = S.create_user(db, org, ident.email, ident.name, ident.subject, ident.picture,
                             invitation, ctx, super_admin=bootstrap)
    elif user.google_subject is None:
        user.google_subject = ident.subject
    ctx = public_context(request, org.id)
    ctx = ctx.__class__(ctx.organization_id, user.id, ctx.ip, ctx.user_agent, ctx.request_id)
    resp = _redirect_web("/mfa" if (user.mfa_required or user.is_super_admin) else data["next"])
    S.start_session(db, user, resp, ctx)
    resp.delete_cookie(OAUTH_COOKIE, path="/api/v1/auth/google", domain=S.COOKIE_DOMAIN)
    return resp


# ---------- password (fallback for accounts without Google) ----------
class PasswordLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


@router.post("/password/login", dependencies=[Depends(public)])
def password_login(body: PasswordLogin, request: Request, response: Response, db: DbSession = Depends(get_db)) -> dict:
    email = body.email.lower()
    _limit("login_ip", request.client.host if request.client else "unknown")
    _limit("login_email", email)
    org = S.default_org(db)
    user = db.scalar(select(User).where(User.organization_id == org.id, User.email == email))
    ok = verify_password(body.password, user.password_hash if user else None)
    ctx = public_context(request, org.id)
    if not ok or user is None or user.status != "active":
        record_now(ctx, "auth.login_failed", "email", email, after={"reason": "bad_credentials"})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    ctx = ctx.__class__(ctx.organization_id, user.id, ctx.ip, ctx.user_agent, ctx.request_id)
    S.start_session(db, user, response, ctx)
    return {"mfa_required": bool(user.mfa_required or user.is_super_admin)}


# ---------- MFA ----------
class CodeBody(BaseModel):
    code: str = Field(min_length=6, max_length=8)


@router.post("/mfa/setup")
def mfa_setup(caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    factor = db.scalar(select(MfaFactor).where(MfaFactor.user_id == caller.user.id, MfaFactor.kind == "totp"))
    if factor and factor.confirmed_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "An authenticator is already set up. Ask a Super Admin to reset it.")
    secret = new_totp_secret()
    enc = S.cipher().encrypt(secret, f"mfa:{caller.user.id}")
    if factor:
        factor.secret_enc = enc
    else:
        db.add(MfaFactor(user_id=caller.user.id, organization_id=caller.user.organization_id, secret_enc=enc))
    return {"otpauth_uri": totp_uri(secret, caller.user.email), "secret": secret}


def _check_code(caller: Caller, db: DbSession, code: str, confirming: bool) -> None:
    _limit("mfa_user", str(caller.user.id))
    factor = db.scalar(select(MfaFactor).where(MfaFactor.user_id == caller.user.id, MfaFactor.kind == "totp"))
    if factor is None or (factor.confirmed_at is None) != confirming:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Set up your authenticator first." if factor is None else "Use the verify step.")
    secret = S.cipher().decrypt(factor.secret_enc, f"mfa:{caller.user.id}")
    step = verify_totp(secret, code, factor.last_used_step)
    if step is None:
        record_now(caller.ctx, "auth.mfa_failed", "user", caller.user.id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code didn't match. Check your authenticator and try again.")
    factor.last_used_step = step
    if confirming:
        factor.confirmed_at = datetime.now(timezone.utc)
        caller.user.mfa_required = True
        record(db, caller.ctx, "auth.mfa_enrolled", "user", caller.user.id)
    caller.session.mfa_passed = True
    record(db, caller.ctx, "auth.mfa_passed", "user", caller.user.id)


@router.post("/mfa/confirm")
def mfa_confirm(body: CodeBody, caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    _check_code(caller, db, body.code, confirming=True)
    return {"ok": True}


@router.post("/mfa/verify")
def mfa_verify(body: CodeBody, caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    _check_code(caller, db, body.code, confirming=False)
    return {"ok": True}


# ---------- sign out ----------
@router.post("/logout")
def logout(response: Response, caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    S.end_session(db, caller.session, response, caller.ctx)
    return {"ok": True}


@router.post("/logout-all")
def logout_all(response: Response, caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    n = S.revoke_all_sessions(db, caller.user.id)
    response.delete_cookie("mme_session", path="/", domain=S.COOKIE_DOMAIN)
    record(db, caller.ctx, "auth.logout_all", "user", caller.user.id, after={"sessions": n})
    return {"ended": n}


# ---------- me ----------
@me_router.get("/me")
def me(caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    u, subj = caller.user, caller.subject
    roles = db.execute(select(Role.key, Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == u.id)).all()
    factor = db.scalar(select(MfaFactor).where(MfaFactor.user_id == u.id, MfaFactor.confirmed_at.is_not(None)))
    perms = {}
    if caller.session.mfa_passed or not (u.mfa_required or u.is_super_admin):
        from ...authz.catalog import ALL_PERMISSIONS
        perms = {p: E.scope_for(subj, p) for p in sorted(ALL_PERMISSIONS) if E.scope_for(subj, p)}
    return {
        "id": str(u.id), "email": u.email, "full_name": u.full_name, "avatar_url": u.avatar_url,
        "is_super_admin": u.is_super_admin, "roles": [{"key": k, "name": n} for k, n in roles],
        "team_ids": [str(t) for t in subj.team_ids], "department_id": str(u.department_id) if u.department_id else None,
        "mfa": {"required": bool(u.mfa_required or u.is_super_admin), "enrolled": factor is not None, "passed": caller.session.mfa_passed},
        "permissions": perms,
        "csrf_token": csrf_token(caller.raw_token, settings.secret_key),
    }

````

---

## `apps/api/app/modules/identity/service.py`

````python
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import RequestContext, record
from ...core.config import load_settings
from ...core.crypto import FieldCipher
from ...core.deps import SESSION_COOKIE
from ...core.models import Employee, Invitation, Organization, Role, Session, TeamMember, User, UserRole
from ...core.security import new_token, token_hash

settings = load_settings()
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN") or None


def cipher() -> FieldCipher:
    if not settings.field_encryption_keys:
        # development only (config.validate refuses this outside development)
        import base64
        return FieldCipher({"dev": base64.urlsafe_b64decode("bW1lLW9zLWRldmVsb3BtZW50LW9ubHkta2V5LTAwMDE=")}, "dev")
    return FieldCipher.from_env(settings.field_encryption_keys, settings.field_encryption_active_kid)


def default_org(db: DbSession) -> Organization:
    org = db.scalar(select(Organization).where(Organization.kind == "internal").order_by(Organization.created_at).limit(1))
    if org is None:
        raise RuntimeError("No organization found. Run scripts/seed.py first.")
    return org


def open_invitation(db: DbSession, org_id: uuid.UUID, email: str, raw_token: Optional[str]) -> Optional[Invitation]:
    q = select(Invitation).where(Invitation.organization_id == org_id, Invitation.email == email,
                                 Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None),
                                 Invitation.expires_at > datetime.now(timezone.utc))
    if raw_token:
        q = q.where(Invitation.token_hash == token_hash(raw_token))
    return db.scalar(q)


def create_user(db: DbSession, org: Organization, email: str, name: str, google_subject: Optional[str],
                avatar: Optional[str], invitation: Optional[Invitation], ctx: RequestContext, super_admin: bool = False) -> User:
    user = User(organization_id=org.id, email=email, full_name=name, google_subject=google_subject,
                avatar_url=avatar if (avatar or "").startswith("https://") else None,
                is_super_admin=super_admin, mfa_required=super_admin,
                department_id=invitation.department_id if invitation else None)
    db.add(user)
    db.flush()
    db.add(Employee(user_id=user.id, organization_id=org.id))
    role_ids = list(invitation.role_ids) if invitation else []
    if not role_ids:
        base = db.scalar(select(Role).where(Role.organization_id == org.id, Role.key == "employee"))
        role_ids = [base.id] if base else []
    for rid in role_ids:
        db.add(UserRole(user_id=user.id, role_id=rid, organization_id=org.id, granted_by=invitation.invited_by if invitation else None))
    for tid in (invitation.team_ids if invitation else []):
        db.add(TeamMember(team_id=tid, user_id=user.id, organization_id=org.id))
    if invitation:
        invitation.accepted_at = datetime.now(timezone.utc)
    record(db, RequestContext(org.id, user.id, ctx.ip, ctx.user_agent, ctx.request_id), "admin.user_created",
           "user", user.id, after={"email": email, "via": "invitation" if invitation else ("bootstrap" if super_admin else "domain"),
                                  "role_ids": role_ids, "super_admin": super_admin})
    return user


def start_session(db: DbSession, user: User, response: Response, ctx: RequestContext) -> str:
    raw = new_token()
    now = datetime.now(timezone.utc)
    db.add(Session(user_id=user.id, organization_id=user.organization_id, token_hash=token_hash(raw), mfa_passed=False,
                   ip=ctx.ip, user_agent=(ctx.user_agent or "")[:400], expires_at=now + timedelta(hours=settings.session_hours),
                   last_seen_at=now))
    user.last_login_at = now
    response.set_cookie(SESSION_COOKIE, raw, max_age=settings.session_hours * 3600, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/", domain=COOKIE_DOMAIN)
    record(db, ctx, "auth.login", "user", user.id)
    return raw


def end_session(db: DbSession, sess: Session, response: Response, ctx: RequestContext) -> None:
    sess.revoked_at = datetime.now(timezone.utc)
    response.delete_cookie(SESSION_COOKIE, path="/", domain=COOKIE_DOMAIN)
    record(db, ctx, "auth.logout", "user", sess.user_id)


def revoke_all_sessions(db: DbSession, user_id: uuid.UUID) -> int:
    res = db.execute(update(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
                     .values(revoked_at=datetime.now(timezone.utc)))
    return res.rowcount or 0

````

---

## `apps/api/app/modules/org/__init__.py`

````python

````

---

## `apps/api/app/modules/org/router.py`

````python
"""Departments, teams, membership and employee profiles, with data scopes applied."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import record
from ...authz import engine as E
from ...core.db import get_db
from ...core.deps import Caller, requires
from ...core.models import Department, Employee, Team, TeamMember, User

router = APIRouter(tags=["organization"])

TEAM_KINDS = Literal["sales", "marketing", "tech", "ai_automation", "customer_success", "finance_ops", "custom"]


def visible_user_ids(caller: Caller, permission: str) -> Select:
    """Subquery of user ids inside the caller's scope for ``permission`` (people records)."""
    c = E.criteria(caller.subject, permission)
    q = select(User.id).where(User.organization_id == c.organization_id)
    if c.all_records:
        return q
    conds = [User.id.in_(c.user_ids)]
    if c.team_ids:
        conds.append(User.id.in_(select(TeamMember.user_id).where(TeamMember.team_id.in_(c.team_ids))))
    if c.department_ids:
        conds.append(User.department_id.in_(c.department_ids))
    return q.where(or_(*conds))


def _org_obj(db: DbSession, caller: Caller, model, obj_id: uuid.UUID):
    obj = db.get(model, obj_id)
    if obj is None or obj.organization_id != caller.user.organization_id or getattr(obj, "deleted_at", None) is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return obj


# ---------- departments ----------
class DepartmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    head_user_id: Optional[uuid.UUID] = None


def _dept_out(d: Department) -> dict:
    return {"id": str(d.id), "name": d.name, "head_user_id": str(d.head_user_id) if d.head_user_id else None}


@router.get("/departments")
def list_departments(caller: Caller = Depends(requires("org.departments.view")), db: DbSession = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Department).where(Department.organization_id == caller.user.organization_id, Department.deleted_at.is_(None)).order_by(Department.name)).all()
    return [_dept_out(d) for d in rows]


@router.post("/departments", status_code=201)
def create_department(body: DepartmentIn, caller: Caller = Depends(requires("org.departments.create")), db: DbSession = Depends(get_db)) -> dict:
    d = Department(organization_id=caller.user.organization_id, name=body.name.strip(), head_user_id=body.head_user_id)
    db.add(d)
    db.flush()
    record(db, caller.ctx, "org.department_created", "department", d.id, after=_dept_out(d))
    return _dept_out(d)


# ---------- teams ----------
class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: TEAM_KINDS = "custom"
    department_id: Optional[uuid.UUID] = None
    lead_user_id: Optional[uuid.UUID] = None


def _team_out(t: Team, members: Optional[list[dict]] = None) -> dict:
    out = {"id": str(t.id), "name": t.name, "kind": t.kind, "department_id": str(t.department_id) if t.department_id else None,
           "lead_user_id": str(t.lead_user_id) if t.lead_user_id else None}
    if members is not None:
        out["members"] = members
    return out


def _teams_in_scope(caller: Caller, permission: str):
    c = E.criteria(caller.subject, permission)
    q = select(Team).where(Team.organization_id == c.organization_id, Team.deleted_at.is_(None))
    if c.all_records:
        return q
    conds = []
    if c.team_ids:
        conds.append(Team.id.in_(c.team_ids))
    if c.department_ids:
        conds.append(Team.department_id.in_(c.department_ids))
    conds.append(Team.lead_user_id.in_(c.user_ids))
    return q.where(or_(*conds))


@router.get("/teams")
def list_teams(caller: Caller = Depends(requires("org.teams.view")), db: DbSession = Depends(get_db)) -> list[dict]:
    return [_team_out(t) for t in db.scalars(_teams_in_scope(caller, "org.teams.view").order_by(Team.name)).all()]


@router.post("/teams", status_code=201)
def create_team(body: TeamIn, caller: Caller = Depends(requires("org.teams.create")), db: DbSession = Depends(get_db)) -> dict:
    t = Team(organization_id=caller.user.organization_id, name=body.name.strip(), kind=body.kind,
             department_id=body.department_id, lead_user_id=body.lead_user_id)
    db.add(t)
    db.flush()
    record(db, caller.ctx, "org.team_created", "team", t.id, after=_team_out(t))
    return _team_out(t)


@router.get("/teams/{team_id}")
def get_team(team_id: uuid.UUID, caller: Caller = Depends(requires("org.teams.view")), db: DbSession = Depends(get_db)) -> dict:
    t = db.scalar(_teams_in_scope(caller, "org.teams.view").where(Team.id == team_id))
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    rows = db.execute(select(User.id, User.full_name, User.email, TeamMember.is_manager)
                      .join(TeamMember, TeamMember.user_id == User.id).where(TeamMember.team_id == t.id).order_by(User.full_name)).all()
    return _team_out(t, [{"user_id": str(i), "full_name": n, "email": e, "is_manager": m} for i, n, e, m in rows])


class MemberIn(BaseModel):
    user_id: uuid.UUID
    is_manager: bool = False


@router.put("/teams/{team_id}/members")
def set_member(team_id: uuid.UUID, body: MemberIn, caller: Caller = Depends(requires("org.teams.edit")), db: DbSession = Depends(get_db)) -> dict:
    t = _org_obj(db, caller, Team, team_id)
    u = _org_obj(db, caller, User, body.user_id)
    m = db.get(TeamMember, (t.id, u.id))
    if m is None:
        db.add(TeamMember(team_id=t.id, user_id=u.id, organization_id=t.organization_id, is_manager=body.is_manager))
    else:
        m.is_manager = body.is_manager
    record(db, caller.ctx, "org.team_member_set", "team", t.id, after={"user_id": str(u.id), "is_manager": body.is_manager})
    return {"ok": True}


@router.delete("/teams/{team_id}/members/{user_id}")
def remove_member(team_id: uuid.UUID, user_id: uuid.UUID, caller: Caller = Depends(requires("org.teams.edit")), db: DbSession = Depends(get_db)) -> dict:
    t = _org_obj(db, caller, Team, team_id)
    m = db.get(TeamMember, (t.id, user_id))
    if m is not None:
        db.delete(m)
        record(db, caller.ctx, "org.team_member_removed", "team", t.id, after={"user_id": str(user_id)})
    return {"ok": True}


# ---------- employees ----------
def _emp_out(u: User, e: Optional[Employee]) -> dict:
    return {"user_id": str(u.id), "email": u.email, "full_name": u.full_name, "avatar_url": u.avatar_url, "status": u.status,
            "department_id": str(u.department_id) if u.department_id else None,
            "designation": e.designation if e else None, "employment_type": e.employment_type if e else None,
            "manager_user_id": str(e.manager_user_id) if e and e.manager_user_id else None,
            "joined_on": e.joined_on.isoformat() if e and e.joined_on else None,
            "phone": e.phone if e else None, "location": e.location if e else None}


@router.get("/employees")
def list_employees(caller: Caller = Depends(requires("org.employees.view")), db: DbSession = Depends(get_db)) -> list[dict]:
    ids = visible_user_ids(caller, "org.employees.view")
    rows = db.execute(select(User, Employee).outerjoin(Employee, Employee.user_id == User.id)
                      .where(User.id.in_(ids)).order_by(User.full_name, User.email)).all()
    return [_emp_out(u, e) for u, e in rows]


@router.get("/employees/{user_id}")
def get_employee(user_id: uuid.UUID, caller: Caller = Depends(requires("org.employees.view")), db: DbSession = Depends(get_db)) -> dict:
    row = db.execute(select(User, Employee).outerjoin(Employee, Employee.user_id == User.id)
                     .where(User.id == user_id, User.id.in_(visible_user_ids(caller, "org.employees.view")))).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return _emp_out(*row)


class EmployeePatch(BaseModel):
    designation: Optional[str] = Field(default=None, max_length=120)
    employment_type: Optional[Literal["full_time", "part_time", "intern", "contract"]] = None
    manager_user_id: Optional[uuid.UUID] = None
    joined_on: Optional[date] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    location: Optional[str] = Field(default=None, max_length=120)


@router.patch("/employees/{user_id}")
def update_employee(user_id: uuid.UUID, body: EmployeePatch, caller: Caller = Depends(requires("org.employees.edit")), db: DbSession = Depends(get_db)) -> dict:
    row = db.execute(select(User, Employee).outerjoin(Employee, Employee.user_id == User.id)
                     .where(User.id == user_id, User.id.in_(visible_user_ids(caller, "org.employees.edit")))).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    u, e = row
    if e is None:
        e = Employee(user_id=u.id, organization_id=u.organization_id)
        db.add(e)
    before = _emp_out(u, e)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("manager_user_id") == u.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Someone can't be their own manager.")
    for k, v in changes.items():
        setattr(e, k, v)
    db.flush()
    record(db, caller.ctx, "org.employee_updated", "user", u.id, before=before, after=_emp_out(u, e))
    return _emp_out(u, e)

````

---

## `apps/api/app/worker/__init__.py`

````python
"""Background worker (Milestone 0 placeholder): outbox delivery, imports, exports, reminders, AI calls.
Run: python -m app.worker  (implemented in Milestone 2 with ARQ on Redis)."""

````

---

## `apps/api/migrations/env.py`

````python
from alembic import context
from sqlalchemy import create_engine

from app.core.config import load_settings

url = load_settings().database_url


def run() -> None:
    if context.is_offline_mode():
        context.configure(url=url, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(url)
    with engine.connect() as conn:
        context.configure(connection=conn, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


run()

````

---

## `apps/api/migrations/sql/0001_foundation.sql`

````sql
-- MME OS · Milestones 0 + 1 · foundation, identity, access, organization, audit
-- Every business table carries organization_id (Stage 2/3 multi-tenancy).
-- Applied by Alembic revision 0001 (migrations/versions/0001_foundation.py).

CREATE TABLE organizations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    slug            text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{2,60}$'),
    kind            text NOT NULL DEFAULT 'internal' CHECK (kind IN ('internal', 'client')),
    -- allowed_domains: Google accounts on these domains may accept invitations / sign in once invited
    settings        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE departments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    head_user_id    uuid,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz,
    UNIQUE (organization_id, name)
);

CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           text NOT NULL CHECK (email = lower(email) AND email LIKE '%_@_%'),
    full_name       text NOT NULL DEFAULT '' CHECK (length(full_name) <= 200),
    avatar_url      text CHECK (avatar_url IS NULL OR avatar_url LIKE 'https://%'),
    google_subject  text,
    password_hash   text,
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deactivated')),
    is_super_admin  boolean NOT NULL DEFAULT false,
    department_id   uuid REFERENCES departments(id) ON DELETE SET NULL,
    mfa_required    boolean NOT NULL DEFAULT false,
    last_login_at   timestamptz,
    deactivated_at  timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, email),
    UNIQUE (google_subject)
);
ALTER TABLE departments ADD CONSTRAINT departments_head_fk FOREIGN KEY (head_user_id) REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX users_org_status_idx ON users (organization_id, status);

CREATE TABLE teams (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    department_id   uuid REFERENCES departments(id) ON DELETE SET NULL,
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    kind            text NOT NULL DEFAULT 'custom' CHECK (kind IN ('sales', 'marketing', 'tech', 'ai_automation', 'customer_success', 'finance_ops', 'custom')),
    lead_user_id    uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz,
    UNIQUE (organization_id, name)
);

CREATE TABLE team_members (
    team_id         uuid NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    is_manager      boolean NOT NULL DEFAULT false,
    added_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (team_id, user_id)
);
CREATE INDEX team_members_user_idx ON team_members (user_id);

-- HR profile for a user (one per user). Business records point at users.
CREATE TABLE employees (
    user_id         uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    employee_code   text,
    designation     text CHECK (length(designation) <= 120),
    manager_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    employment_type text NOT NULL DEFAULT 'full_time' CHECK (employment_type IN ('full_time', 'part_time', 'intern', 'contract')),
    joined_on       date,
    left_on         date,
    phone           text CHECK (length(phone) <= 30),
    location        text CHECK (length(location) <= 120),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, employee_code)
);

-- ---------- access control ----------
CREATE TABLE roles (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    key             text NOT NULL CHECK (key ~ '^[a-z0-9_]{2,60}$'),
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    description     text NOT NULL DEFAULT '',
    is_system       boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, key)
);

CREATE TABLE role_grants (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id         uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    permission      text NOT NULL CHECK (permission ~ '^[a-z_]+\.[a-z_]+\.(view|create|edit|delete|export|approve|manage)$'),
    scope           text NOT NULL CHECK (scope IN ('own', 'team', 'department', 'all')),
    UNIQUE (role_id, permission)
);

CREATE TABLE user_roles (
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    granted_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    granted_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

-- ---------- identity ----------
CREATE TABLE invitations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           text NOT NULL CHECK (email = lower(email)),
    role_ids        uuid[] NOT NULL DEFAULT '{}',
    team_ids        uuid[] NOT NULL DEFAULT '{}',
    department_id   uuid REFERENCES departments(id) ON DELETE SET NULL,
    token_hash      text NOT NULL UNIQUE,
    invited_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    expires_at      timestamptz NOT NULL,
    accepted_at     timestamptz,
    revoked_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX invitations_open_email_idx ON invitations (organization_id, email) WHERE accepted_at IS NULL AND revoked_at IS NULL;

CREATE TABLE sessions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    token_hash      text NOT NULL UNIQUE,           -- sha256 of the cookie value; the raw token is never stored
    mfa_passed      boolean NOT NULL DEFAULT false,
    ip              inet,
    user_agent      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL,
    revoked_at      timestamptz
);
CREATE INDEX sessions_user_idx ON sessions (user_id) WHERE revoked_at IS NULL;

CREATE TABLE mfa_factors (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    kind            text NOT NULL DEFAULT 'totp' CHECK (kind = 'totp'),
    secret_enc      text NOT NULL,                  -- AES-GCM, see core/crypto.py
    confirmed_at    timestamptz,
    last_used_step  bigint,                         -- blocks replay of a used code
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, kind)
);

CREATE TABLE api_keys (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         uuid REFERENCES users(id) ON DELETE CASCADE,
    name            text NOT NULL,
    prefix          text NOT NULL,                  -- shown in lists, e.g. mme_live_ab12
    key_hash        text NOT NULL UNIQUE,
    permissions     text[] NOT NULL DEFAULT '{}',
    expires_at      timestamptz,
    last_used_at    timestamptz,
    revoked_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------- platform ----------
CREATE TABLE audit_events (
    id              bigserial PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    actor_user_id   uuid REFERENCES users(id) ON DELETE SET NULL,
    action          text NOT NULL CHECK (action ~ '^[a-z_]+\.[a-z_.]+$'),
    target_type     text,
    target_id       text,
    before          jsonb,
    after           jsonb,
    ip              inet,
    user_agent      text,
    request_id      text,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_events_org_time_idx ON audit_events (organization_id, created_at DESC);
CREATE INDEX audit_events_target_idx ON audit_events (organization_id, target_type, target_id);

-- Audit log is append-only: block UPDATE and DELETE at the database level.
CREATE FUNCTION audit_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only';
END;
$$;
CREATE TRIGGER audit_events_no_update BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

CREATE TABLE files (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    owner_id        uuid REFERENCES users(id) ON DELETE SET NULL,
    storage_key     text NOT NULL UNIQUE,
    filename        text NOT NULL CHECK (length(filename) <= 255),
    content_type    text NOT NULL,
    size_bytes      bigint NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 26214400),
    sha256          text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz
);

-- Transactional outbox: written with the business change, delivered by the worker (webhooks, n8n).
CREATE TABLE outbox_events (
    id              bigserial PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    topic           text NOT NULL,
    payload         jsonb NOT NULL,
    attempts        int NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    delivered_at    timestamptz,
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX outbox_pending_idx ON outbox_events (next_attempt_at) WHERE delivered_at IS NULL;

-- updated_at maintenance
CREATE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;
CREATE TRIGGER organizations_touch BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER departments_touch BEFORE UPDATE ON departments FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER users_touch BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER teams_touch BEFORE UPDATE ON teams FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER employees_touch BEFORE UPDATE ON employees FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER roles_touch BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- At least one active super admin must remain in each organization.
CREATE FUNCTION keep_one_super_admin() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (OLD.is_super_admin AND OLD.status = 'active')
       AND (NEW.is_super_admin = false OR NEW.status <> 'active') THEN
        IF NOT EXISTS (
            SELECT 1 FROM users
            WHERE organization_id = OLD.organization_id AND id <> OLD.id
              AND is_super_admin AND status = 'active'
        ) THEN
            RAISE EXCEPTION 'cannot remove the last active super admin';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER users_keep_super_admin BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION keep_one_super_admin();

````

---

## `apps/api/migrations/versions/0001_foundation.py`

````python
"""Milestones 0 + 1 foundation schema.

Revision ID: 0001
Revises:
"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[1] / "sql" / "0001_foundation.sql"

TABLES = ["outbox_events", "files", "audit_events", "api_keys", "mfa_factors", "sessions", "invitations", "user_roles",
          "role_grants", "roles", "employees", "team_members", "teams", "users", "departments", "organizations"]


def upgrade() -> None:
    op.execute(SQL.read_text())


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    for fn in ("audit_events_immutable", "touch_updated_at", "keep_one_super_admin"):
        op.execute(f"DROP FUNCTION IF EXISTS {fn}() CASCADE")

````

---

## `apps/api/pyproject.toml`

````toml
[tool.ruff]
line-length = 140
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "B", "S", "UP", "I"]
ignore = ["S101", "B008", "S105"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true

````

---

## `apps/api/requirements-dev.txt`

````text
-r requirements.txt
pytest==8.3.4
ruff==0.8.4
mypy==1.14.1
pip-audit==2.7.3
bandit==1.8.0

````

---

## `apps/api/requirements.txt`

````text
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
psycopg[binary]==3.2.3
alembic==1.14.0
pydantic[email]==2.10.4
httpx==0.28.1
PyJWT[crypto]==2.10.1
cryptography==44.0.0
itsdangerous==2.2.0
redis==5.2.1

````

---

## `apps/api/scripts/__init__.py`

````python

````

---

## `apps/api/scripts/seed.py`

````python
"""Create the MME organization, the default roles and the base settings. Safe to run again.

    python -m scripts.seed --org-name "MME AI" --domain mme-ai.com

Super Admins are NOT created here: the emails in BOOTSTRAP_SUPER_ADMINS become Super Admins
the first time they sign in with Google, and must then set up MFA.
"""
from __future__ import annotations

import argparse

from sqlalchemy import delete, select

from app.authz.catalog import DEFAULT_ROLES
from app.core.db import SessionLocal
from app.core.models import Organization, Role, RoleGrant


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org-name", default="MME AI")
    ap.add_argument("--slug", default="mme")
    ap.add_argument("--domain", action="append", default=[], help="Google Workspace domain whose accounts may join (repeatable)")
    ap.add_argument("--reset-default-grants", action="store_true", help="overwrite edited default roles with the catalog")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        org = db.scalar(select(Organization).where(Organization.slug == args.slug))
        if org is None:
            org = Organization(name=args.org_name, slug=args.slug, kind="internal", settings={"allowed_domains": args.domain})
            db.add(org)
            db.flush()
            print(f"created organization {org.name}")
        elif args.domain:
            org.settings = {**(org.settings or {}), "allowed_domains": sorted(set(args.domain))}

        for key, spec in DEFAULT_ROLES.items():
            role = db.scalar(select(Role).where(Role.organization_id == org.id, Role.key == key))
            if role is None:
                role = Role(organization_id=org.id, key=key, name=spec["name"], is_system=True)
                db.add(role)
                db.flush()
            elif not args.reset_default_grants:
                continue
            db.execute(delete(RoleGrant).where(RoleGrant.role_id == role.id))
            for perm, scope in spec["grants"]:
                db.add(RoleGrant(role_id=role.id, organization_id=org.id, permission=perm, scope=scope))
            print(f"role {key}: {len(spec['grants'])} grants")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()

````

---

## `apps/api/tests/__init__.py`

````python

````

---

## `apps/api/tests/api/__init__.py`

````python

````

---

## `apps/api/tests/api/conftest.py`

````python
"""API tests run against a real PostgreSQL (CI service container or docker compose).

TEST_DATABASE_URL must point at an empty database the tests may wipe.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

os.environ.setdefault("APP_ENV", "development")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://mme:mme@localhost:5432/mme_os_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.authz.catalog import DEFAULT_ROLES  # noqa: E402
from app.core.db import SessionLocal, engine  # noqa: E402
from app.core.deps import SESSION_COOKIE  # noqa: E402
from app.core.models import Organization, Role, RoleGrant, Session, TeamMember, Team, User, UserRole, Employee  # noqa: E402
from app.core.security import new_token, token_hash  # noqa: E402
from app.main import app  # noqa: E402

SQL = Path(__file__).resolve().parents[2] / "migrations" / "sql" / "0001_foundation.sql"


@pytest.fixture(scope="session", autouse=True)
def schema():
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        c.execute(text(SQL.read_text()))
    yield


@pytest.fixture()
def world(schema):
    """An org with default roles, two teams and one user per role."""
    with engine.begin() as c:
        c.execute(text("TRUNCATE organizations CASCADE"))
    db = SessionLocal()
    org = Organization(name="MME", slug="mme", settings={"allowed_domains": ["mme-ai.com"]})
    db.add(org)
    db.flush()
    roles = {}
    for key, spec in DEFAULT_ROLES.items():
        r = Role(organization_id=org.id, key=key, name=spec["name"], is_system=True)
        db.add(r)
        db.flush()
        for p, s in spec["grants"]:
            db.add(RoleGrant(role_id=r.id, organization_id=org.id, permission=p, scope=s))
        roles[key] = r
    sales, tech = Team(organization_id=org.id, name="Sales", kind="sales"), Team(organization_id=org.id, name="Tech", kind="tech")
    db.add_all([sales, tech])
    db.flush()

    def mk(email, role=None, team=None, super_admin=False, manager=False):
        u = User(organization_id=org.id, email=email, full_name=email.split("@")[0].title(), is_super_admin=super_admin, mfa_required=super_admin)
        db.add(u)
        db.flush()
        db.add(Employee(user_id=u.id, organization_id=org.id))
        if role:
            db.add(UserRole(user_id=u.id, role_id=roles[role].id, organization_id=org.id))
        if team:
            db.add(TeamMember(team_id=team.id, user_id=u.id, organization_id=org.id, is_manager=manager))
        return u

    users = {
        "founder": mk("founder@mme-ai.com", super_admin=True),
        "founder2": mk("cofounder@mme-ai.com", super_admin=True),
        "ops": mk("ops@mme-ai.com", "operations_admin"),
        "sales_mgr": mk("salesmgr@mme-ai.com", "sales_manager", sales, manager=True),
        "sales_exec": mk("sales@mme-ai.com", "sales_executive", sales),
        "dev": mk("dev@mme-ai.com", "tech_automation", tech),
        "emp": mk("emp@mme-ai.com", "employee", tech),
    }
    db.commit()
    w = {"org": org, "roles": roles, "teams": {"sales": sales, "tech": tech}, "users": users}
    yield w
    db.close()


class Client:
    def __init__(self, user: User, mfa: bool = True):
        raw = new_token()
        db = SessionLocal()
        db.add(Session(user_id=user.id, organization_id=user.organization_id, token_hash=token_hash(raw), mfa_passed=mfa,
                       expires_at=datetime.now(timezone.utc) + timedelta(hours=2), last_seen_at=datetime.now(timezone.utc)))
        db.commit()
        db.close()
        self.http = TestClient(app)
        self.http.cookies.set(SESSION_COOKIE, raw)
        me = self.http.get("/api/v1/me")
        self.csrf = me.json().get("csrf_token") if me.status_code == 200 else None

    def get(self, path, **kw):
        return self.http.get("/api/v1" + path, **kw)

    def send(self, method, path, json=None, csrf=True):
        headers = {"x-csrf-token": self.csrf} if csrf and self.csrf else {}
        return self.http.request(method, "/api/v1" + path, json=json, headers=headers)


@pytest.fixture()
def as_user(world):
    def make(key: str, mfa: bool = True) -> Client:
        return Client(world["users"][key], mfa=mfa)
    return make

````

---

## `apps/api/tests/api/test_access.py`

````python
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import text

from app.core.db import engine
from app.core.deps import public, signed_in, signed_in_mfa_pending
from app.main import app


def _declared(route: APIRoute) -> str | None:
    def walk(dep):
        call = dep.call
        if getattr(call, "__mme_permission__", None):
            return call.__mme_permission__
        if call in (signed_in, signed_in_mfa_pending):
            return "signed_in"
        if getattr(call, "__mme_public__", False):
            return "public"
        for d in dep.dependencies:
            found = walk(d)
            if found:
                return found
        return None
    return walk(route.dependant)


def test_every_route_declares_access():
    missing = [f"{sorted(r.methods)} {r.path}" for r in app.routes
               if isinstance(r, APIRoute) and r.path.startswith("/api/v1") and not _declared(r)]
    assert not missing, f"routes without an access declaration: {missing}"


def test_public_routes_are_only_sign_in_and_health():
    public_paths = {r.path for r in app.routes if isinstance(r, APIRoute) and _declared(r) == "public"}
    assert public_paths <= {"/api/v1/health", "/api/v1/auth/google/start", "/api/v1/auth/google/callback", "/api/v1/auth/password/login"}


# role -> expected status for admin and org endpoints
MATRIX = [
    ("GET", "/admin/users", {"founder": 200, "ops": 403, "sales_mgr": 403, "sales_exec": 403, "dev": 403, "emp": 403}),
    ("GET", "/admin/roles", {"founder": 200, "ops": 403, "sales_mgr": 403, "emp": 403}),
    ("GET", "/audit-events", {"founder": 200, "ops": 403, "sales_mgr": 403, "emp": 403}),
    ("GET", "/employees", {"founder": 200, "ops": 200, "sales_mgr": 200, "sales_exec": 200, "dev": 200, "emp": 200}),
    ("GET", "/departments", {"founder": 200, "ops": 200, "sales_mgr": 403, "emp": 403}),
]


@pytest.mark.parametrize("method,path,expect", MATRIX)
def test_authorization_matrix(as_user, method, path, expect):
    for who, code in expect.items():
        r = as_user(who).send(method, path) if method != "GET" else as_user(who).get(path)
        assert r.status_code == code, f"{who} {method} {path} -> {r.status_code} {r.text}"


def test_super_admin_without_mfa_is_blocked(as_user):
    r = as_user("founder", mfa=False).get("/admin/users")
    assert r.status_code == 403 and r.headers.get("x-mfa-required") == "1"


def test_signed_out_is_401():
    from fastapi.testclient import TestClient
    assert TestClient(app).get("/api/v1/me").status_code == 401


def test_writes_need_csrf(as_user, world):
    c = as_user("founder")
    r = c.send("POST", "/departments", {"name": "Sales"}, csrf=False)
    assert r.status_code == 403
    assert c.send("POST", "/departments", {"name": "Sales"}).status_code == 201


def test_employee_scope_team_only(as_user, world):
    names = {e["email"] for e in as_user("sales_exec").get("/employees").json()}
    assert names == {"salesmgr@mme-ai.com", "sales@mme-ai.com"}
    names = {e["email"] for e in as_user("emp").get("/employees").json()}
    assert names == {"dev@mme-ai.com", "emp@mme-ai.com"}
    assert len(as_user("ops").get("/employees").json()) == len(world["users"])


def test_out_of_scope_employee_is_404(as_user, world):
    dev_id = str(world["users"]["dev"].id)
    assert as_user("sales_exec").get(f"/employees/{dev_id}").status_code == 404


def test_cannot_change_own_roles(as_user, world):
    me = world["users"]["founder"]
    r = as_user("founder").send("PUT", f"/admin/users/{me.id}/roles", {"role_ids": [str(world["roles"]["employee"].id)]})
    assert r.status_code == 403


def test_super_admin_assigns_roles_and_audit_records_it(as_user, world):
    target = world["users"]["emp"]
    r = as_user("founder").send("PUT", f"/admin/users/{target.id}/roles", {"role_ids": [str(world["roles"]["sales_executive"].id)]})
    assert r.status_code == 200, r.text
    events = as_user("founder").get("/audit-events", params={"action": "admin.user_roles_changed"}).json()["items"]
    assert events and events[0]["after"] == {"roles": ["sales_executive"]} and events[0]["before"] == {"roles": ["employee"]}


def test_only_super_admin_edits_roles(as_user):
    body = {"key": "x_role", "name": "X", "grants": [{"permission": "crm.leads.view", "scope": "all"}]}
    assert as_user("ops").send("POST", "/admin/roles", body).status_code == 403
    assert as_user("founder").send("POST", "/admin/roles", body).status_code == 201


def test_unknown_permission_rejected(as_user):
    body = {"key": "bad_role", "name": "Bad", "grants": [{"permission": "crm.leads.teleport", "scope": "all"}]}
    assert as_user("founder").send("POST", "/admin/roles", body).status_code == 422


def test_deactivation_ends_sessions(as_user, world):
    victim = as_user("sales_exec")
    assert victim.get("/me").status_code == 200
    r = as_user("founder").send("PATCH", f"/admin/users/{world['users']['sales_exec'].id}", {"status": "deactivated"})
    assert r.status_code == 200, r.text
    assert victim.get("/me").status_code == 401


def test_cannot_demote_self_or_last_super_admin(as_user, world):
    f, f2 = world["users"]["founder"], world["users"]["founder2"]
    assert as_user("founder").send("PUT", f"/admin/users/{f.id}/super-admin", {"is_super_admin": False}).status_code == 403
    assert as_user("founder").send("PUT", f"/admin/users/{f2.id}/super-admin", {"is_super_admin": False}).status_code == 200
    # founder is now the last one: founder2 is no longer admin, so nobody else can demote founder
    assert as_user("founder").send("PUT", f"/admin/users/{f.id}/super-admin", {"is_super_admin": False}).status_code == 403


def test_audit_log_is_append_only(world):
    with pytest.raises(Exception):
        with engine.begin() as c:
            c.execute(text("UPDATE audit_events SET action = 'x.y'"))

````

---

## `apps/api/tests/api/test_schema_parity.py`

````python
"""The SQL file is the source of truth; the ORM must match its tables and columns."""
from sqlalchemy import inspect

from app.core.db import engine
from app.core.models import Base


def test_models_match_database():
    insp = inspect(engine)
    problems = []
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            problems.append(f"missing table {table.name}")
            continue
        db_cols = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name not in db_cols:
                problems.append(f"{table.name}.{col.name} not in database")
    assert not problems, problems

````

---

## `apps/api/tests/core/__init__.py`

````python

````

---

## `apps/api/tests/core/test_core.py`

````python
"""Core security tests. Standard library only: run with `python -m unittest discover -s tests/core`
from apps/api. They also run under pytest in CI."""
import base64
import os
import time
import unittest
import uuid

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from app.authz import engine as E
from app.authz.catalog import ALL_PERMISSIONS, DEFAULT_ROLES, validate_catalog
from app.core import security as SEC
from app.core.config import ConfigError, load_settings
from app.core.crypto import FieldCipher
from app.core.google_oidc import InvalidGoogleToken, build_auth_request, verify_id_token
from app.modules.identity.policy import Decision, ExistingUser, decide_sign_in

ORG, OTHER_ORG = uuid.uuid4(), uuid.uuid4()
ME, PEER, STRANGER = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
TEAM_A, TEAM_B, DEPT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def role_grants(key):
    return tuple(E.Grant(p, s) for p, s in DEFAULT_ROLES[key]["grants"])


def subject(*roles, **kw):
    grants = tuple(g for r in roles for g in role_grants(r))
    base = dict(user_id=ME, organization_id=ORG, grants=grants, team_ids=frozenset({TEAM_A}), department_id=DEPT)
    base.update(kw)
    return E.Subject(**base)


class CatalogTests(unittest.TestCase):
    def test_default_roles_valid(self):
        validate_catalog()
        self.assertIn("crm.leads.view", ALL_PERMISSIONS)

    def test_no_default_role_can_manage_access(self):
        for key, role in DEFAULT_ROLES.items():
            for perm, _ in role["grants"]:
                self.assertFalse(perm.startswith(("admin.", "system.")), f"{key} grants {perm}")


class ScopeTests(unittest.TestCase):
    def lead(self, owner=None, team=None, dept=None, org=ORG, assignees=()):
        return E.RecordRef(organization_id=org, owner_id=owner, team_id=team, department_id=dept, assignee_ids=frozenset(assignees))

    def test_sales_exec_sees_only_own_leads(self):
        s = subject("sales_executive")
        E.check(s, "crm.leads.view", self.lead(owner=ME))
        with self.assertRaises(E.NotFound):
            E.check(s, "crm.leads.view", self.lead(owner=PEER, team=TEAM_A))

    def test_assignee_counts_as_own(self):
        E.check(subject("sales_executive"), "crm.leads.view", self.lead(owner=PEER, assignees=[ME]))

    def test_sales_manager_sees_team_not_other_team(self):
        s = subject("sales_manager")
        E.check(s, "crm.leads.view", self.lead(owner=PEER, team=TEAM_A))
        with self.assertRaises(E.NotFound):
            E.check(s, "crm.leads.view", self.lead(owner=PEER, team=TEAM_B))

    def test_widest_scope_wins_across_roles(self):
        s = subject("sales_executive", "sales_manager")
        self.assertEqual(E.scope_for(s, "crm.leads.view"), "team")

    def test_missing_permission_is_forbidden(self):
        with self.assertRaises(E.Forbidden):
            E.check(subject("employee"), "crm.leads.view", self.lead(owner=ME))

    def test_other_org_is_not_found_even_without_permission(self):
        with self.assertRaises(E.NotFound):
            E.check(subject("employee"), "crm.leads.view", self.lead(owner=ME, org=OTHER_ORG))
        with self.assertRaises(E.NotFound):
            E.check(subject(is_super_admin=True, mfa_passed=True), "crm.leads.view", self.lead(owner=ME, org=OTHER_ORG))

    def test_manage_implies_other_actions(self):
        s = E.Subject(user_id=ME, organization_id=ORG, grants=(E.Grant("work.tasks.manage", "team"),), team_ids=frozenset({TEAM_A}))
        self.assertEqual(E.scope_for(s, "work.tasks.delete"), "team")

    def test_department_scope(self):
        s = E.Subject(user_id=ME, organization_id=ORG, grants=(E.Grant("hr.leave.approve", "department"),), department_id=DEPT)
        E.check(s, "hr.leave.approve", self.lead(owner=PEER, dept=DEPT))
        with self.assertRaises(E.NotFound):
            E.check(s, "hr.leave.approve", self.lead(owner=PEER, dept=uuid.uuid4()))

    def test_deactivated_user_has_nothing(self):
        s = subject("operations_admin", active=False)
        self.assertIsNone(E.scope_for(s, "crm.leads.view"))

    def test_criteria_shapes(self):
        c = E.criteria(subject("sales_manager"), "crm.leads.view")
        self.assertFalse(c.all_records)
        self.assertEqual(c.team_ids, frozenset({TEAM_A}))
        self.assertEqual(c.user_ids, frozenset({ME}))
        self.assertTrue(E.criteria(subject("operations_admin"), "crm.leads.view").all_records)
        with self.assertRaises(E.Forbidden):
            E.criteria(subject("employee"), "crm.leads.view")

    def test_export_needs_mfa(self):
        s = subject("sales_manager")
        self.assertIsNone(E.scope_for(s, "crm.leads.export"))
        self.assertEqual(E.scope_for(subject("sales_manager", mfa_passed=True), "crm.leads.export"), "team")

    def test_super_admin_admin_actions_need_mfa(self):
        self.assertIsNone(E.scope_for(subject(is_super_admin=True), "admin.roles.manage"))
        self.assertEqual(E.scope_for(subject(is_super_admin=True, mfa_passed=True), "admin.roles.manage"), "all")
        self.assertEqual(E.scope_for(subject(is_super_admin=True), "crm.leads.view"), "all")


class EscalationTests(unittest.TestCase):
    def test_nobody_changes_own_roles(self):
        admin = subject(is_super_admin=True, mfa_passed=True)
        with self.assertRaises(E.EscalationDenied):
            E.check_role_assignment(admin, ME, role_grants("employee"))

    def test_employee_cannot_assign_roles(self):
        with self.assertRaises(E.Forbidden):
            E.check_role_assignment(subject("operations_admin", mfa_passed=True), PEER, role_grants("employee"))

    def test_delegated_admin_cannot_grant_wider_than_held(self):
        delegate = E.Subject(user_id=ME, organization_id=ORG, mfa_passed=True,
                             grants=(E.Grant("admin.roles.manage", "all"), E.Grant("crm.leads.view", "team")))
        E.check_role_assignment(delegate, PEER, (E.Grant("crm.leads.view", "own"),))
        with self.assertRaises(E.EscalationDenied):
            E.check_role_assignment(delegate, PEER, (E.Grant("crm.leads.view", "all"),))
        with self.assertRaises(E.EscalationDenied):
            E.check_role_assignment(delegate, PEER, (E.Grant("billing.subscriptions.view", "own"),))

    def test_only_super_admin_edits_roles_and_not_own(self):
        with self.assertRaises(E.EscalationDenied):
            E.check_role_edit(subject("operations_admin", mfa_passed=True), role_grants("employee"), actor_holds_role=False)
        with self.assertRaises(E.EscalationDenied):
            E.check_role_edit(subject(is_super_admin=True, mfa_passed=True), role_grants("employee"), actor_holds_role=True)
        E.check_role_edit(subject(is_super_admin=True, mfa_passed=True), role_grants("employee"), actor_holds_role=False)

    def test_super_admin_status_rules(self):
        sa = subject(is_super_admin=True, mfa_passed=True)
        with self.assertRaises(E.EscalationDenied):
            E.check_super_admin_change(sa, ME, False, 3)
        with self.assertRaises(E.EscalationDenied):
            E.check_super_admin_change(sa, PEER, False, 1)
        with self.assertRaises(E.EscalationDenied):
            E.check_super_admin_change(subject(is_super_admin=True), PEER, True, 1)
        with self.assertRaises(E.EscalationDenied):
            E.check_super_admin_change(subject("operations_admin", mfa_passed=True), PEER, True, 1)
        E.check_super_admin_change(sa, PEER, True, 1)


class SecurityTests(unittest.TestCase):
    def test_password_roundtrip_and_rejects(self):
        h = SEC.hash_password("correct horse battery")
        self.assertTrue(SEC.verify_password("correct horse battery", h))
        self.assertFalse(SEC.verify_password("wrong horse battery", h))
        self.assertFalse(SEC.verify_password("anything", None))
        self.assertNotEqual(h, SEC.hash_password("correct horse battery"))
        with self.assertRaises(ValueError):
            SEC.hash_password("short")

    def test_totp_rfc6238_vector(self):
        secret = base64.b32encode(b"12345678901234567890").decode()
        self.assertEqual(SEC.totp_at(secret, 59 // 30), "287082")
        self.assertEqual(SEC.totp_at(secret, 1111111109 // 30), "081804")

    def test_totp_verify_window_and_replay(self):
        secret = SEC.new_totp_secret()
        now = 1_800_000_000
        code = SEC.totp_at(secret, now // 30)
        step = SEC.verify_totp(secret, code, None, now=now)
        self.assertEqual(step, now // 30)
        self.assertIsNone(SEC.verify_totp(secret, code, step, now=now), "replay must fail")
        self.assertIsNotNone(SEC.verify_totp(secret, SEC.totp_at(secret, now // 30 - 1), None, now=now))
        self.assertIsNone(SEC.verify_totp(secret, SEC.totp_at(secret, now // 30 - 3), None, now=now))
        self.assertIsNone(SEC.verify_totp(secret, "12ab56", None, now=now))

    def test_tokens_and_csrf(self):
        t = SEC.new_token()
        self.assertEqual(len(SEC.token_hash(t)), 64)
        c = SEC.csrf_token(t, "k" * 32)
        self.assertTrue(SEC.verify_csrf(t, "k" * 32, c))
        self.assertFalse(SEC.verify_csrf(SEC.new_token(), "k" * 32, c))
        self.assertFalse(SEC.verify_csrf(t, "k" * 32, None))
        key, prefix = SEC.new_api_key()
        self.assertTrue(key.startswith(prefix) and prefix.startswith("mme_live_"))


class CryptoTests(unittest.TestCase):
    def setUp(self):
        self.k1, self.k2 = os.urandom(32), os.urandom(32)

    def test_roundtrip_context_and_tamper(self):
        c = FieldCipher({"k1": self.k1}, "k1")
        ct = c.encrypt("JBSWY3DPEHPK3PXP", "mfa:user-1")
        self.assertEqual(c.decrypt(ct, "mfa:user-1"), "JBSWY3DPEHPK3PXP")
        with self.assertRaises(Exception):
            c.decrypt(ct, "mfa:user-2")
        parts = ct.split(".")
        parts[3] = parts[3][:-2] + ("AA" if parts[3][-2:] != "AA" else "BB")
        with self.assertRaises(Exception):
            c.decrypt(".".join(parts), "mfa:user-1")

    def test_rotation(self):
        old = FieldCipher({"k1": self.k1}, "k1").encrypt("s", "ctx")
        new = FieldCipher({"k1": self.k1, "k2": self.k2}, "k2")
        self.assertEqual(new.decrypt(old, "ctx"), "s")
        self.assertTrue(new.needs_rotation(old))
        self.assertFalse(new.needs_rotation(new.encrypt("s", "ctx")))

    def test_from_env(self):
        spec = "k1:" + base64.urlsafe_b64encode(self.k1).decode()
        c = FieldCipher.from_env(spec, "k1")
        self.assertEqual(c.decrypt(c.encrypt("x", "y"), "y"), "x")


class GoogleTests(unittest.TestCase):
    CLIENT = "client-123.apps.googleusercontent.com"

    def setUp(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.pub = self.key.public_key()

    def token(self, **over):
        now = int(time.time())
        claims = {"iss": "https://accounts.google.com", "aud": self.CLIENT, "sub": "1234", "iat": now, "exp": now + 600,
                  "email": "Neha@MME-AI.com", "email_verified": True, "nonce": "n1", "name": "Neha", "hd": "mme-ai.com"}
        claims.update(over)
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "k"})

    def verify(self, tok, nonce="n1", key=None):
        return verify_id_token(tok, self.CLIENT, nonce, key_resolver=lambda _t: key or self.pub)

    def test_valid(self):
        ident = self.verify(self.token())
        self.assertEqual(ident.email, "neha@mme-ai.com")
        self.assertEqual(ident.hosted_domain, "mme-ai.com")

    def test_rejections(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
        cases = [
            (self.token(aud="someone-else"), "n1", None),
            (self.token(iss="https://evil.example"), "n1", None),
            (self.token(exp=int(time.time()) - 3600), "n1", None),
            (self.token(), "different-nonce", None),
            (self.token(email_verified=False), "n1", None),
            (self.token(), "n1", other),
        ]
        for tok, nonce, key in cases:
            with self.assertRaises(InvalidGoogleToken):
                self.verify(tok, nonce, key)

    def test_auth_request_has_pkce_and_state(self):
        req = build_auth_request(self.CLIENT, "https://api.example/auth/google/callback")
        self.assertIn("code_challenge_method=S256", req.url)
        self.assertIn(req.state, req.url)
        self.assertNotIn(req.code_verifier, req.url)


class SignInPolicyTests(unittest.TestCase):
    def test_branches(self):
        active = ExistingUser("active", "g1")
        self.assertEqual(decide_sign_in("a@x.com", "g1", active, False, []), Decision.SIGN_IN)
        self.assertEqual(decide_sign_in("a@x.com", "g2", active, False, []), Decision.DENY_SUBJECT_MISMATCH)
        self.assertEqual(decide_sign_in("a@x.com", "g1", ExistingUser("deactivated", "g1"), True, ["x.com"]), Decision.DENY_DEACTIVATED)
        self.assertEqual(decide_sign_in("a@x.com", "g1", None, True, []), Decision.CREATE_FROM_INVITE)
        self.assertEqual(decide_sign_in("A@MME-AI.com", "g1", None, False, ["mme-ai.com"]), Decision.CREATE_FROM_DOMAIN)
        self.assertEqual(decide_sign_in("a@gmail.com", "g1", None, False, ["mme-ai.com"]), Decision.DENY_NOT_INVITED)


class ConfigTests(unittest.TestCase):
    def test_dev_defaults_load(self):
        self.assertEqual(load_settings({}).env, "development")

    def test_production_refuses_unsafe_values(self):
        with self.assertRaises(ConfigError):
            load_settings({"APP_ENV": "production"})
        with self.assertRaises(ConfigError):
            load_settings({"APP_ENV": "production", "SECRET_KEY": "your-secret-key-change-in-production"})

    def test_production_ok_when_configured(self):
        env = {"APP_ENV": "production", "SECRET_KEY": "x" * 48, "FIELD_ENCRYPTION_KEYS": "k1:" + base64.urlsafe_b64encode(os.urandom(32)).decode(),
               "FIELD_ENCRYPTION_ACTIVE_KID": "k1", "GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "s",
               "WEB_ORIGIN": "https://os.mme-ai.com", "API_ORIGIN": "https://api.mme-ai.com", "DATABASE_URL": "postgresql+psycopg://app:pw@db:5432/mme",
               "BOOTSTRAP_SUPER_ADMINS": "A@B.com, c@d.com"}
        s = load_settings(env)
        self.assertTrue(s.cookie_secure)
        self.assertEqual(s.bootstrap_super_admins, ("a@b.com", "c@d.com"))


if __name__ == "__main__":
    unittest.main()

````

---

## `apps/web/app/(os)/admin/roles/page.tsx`

````tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "@/components/session";
import { api, ApiError, Scope } from "@/lib/api";

interface Grant { permission: string; scope: Scope; }
interface Role { id: string; key: string; name: string; description: string; is_system: boolean; grants: Grant[]; }
interface Catalog { resources: { key: string; label: string }[]; actions: string[]; scopes: Scope[]; }

export default function RolesPage() {
  const { me } = useSession();
  const [roles, setRoles] = useState<Role[]>([]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, Scope | "">>({});
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, c] = await Promise.all([api.get<Role[]>("/admin/roles"), api.get<Catalog>("/admin/permissions")]);
      setRoles(r); setCatalog(c); setSelected((s) => s ?? r[0]?.id ?? null);
    } catch (e) { setMsg((e as ApiError).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const role = useMemo(() => roles.find((r) => r.id === selected) || null, [roles, selected]);
  useEffect(() => { setDraft(Object.fromEntries((role?.grants || []).map((g) => [g.permission, g.scope]))); }, [role]);

  if (!me || !catalog) return msg ? <p className="text-sm">{msg}</p> : null;
  const editable = me.is_super_admin;

  async function save() {
    if (!role) return;
    setMsg(null);
    const grants = Object.entries(draft).filter(([, s]) => s).map(([permission, scope]) => ({ permission, scope }));
    try {
      await api.put(`/admin/roles/${role.id}`, { key: role.key, name: role.name, description: role.description, grants });
      setMsg("Saved. Changes apply on each person's next request.");
      await load();
    } catch (e) { setMsg((e as ApiError).message); }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Roles and permissions</h1>
      <p className="max-w-3xl text-sm text-slate-600">Each cell sets how far a role reaches: <b>own</b> (records they own or are assigned), <b>team</b>, <b>department</b> or <b>all</b>. Empty means no access. The API enforces this on every request; nobody can edit a role they hold.</p>
      {msg && <p role="status" className="rounded-lg bg-slate-100 px-3 py-2 text-sm">{msg}</p>}
      <div className="flex flex-wrap gap-2">
        {roles.map((r) => (
          <button key={r.id} onClick={() => setSelected(r.id)} className={`btn ${r.id === selected ? "border-brand text-brand" : ""}`}>{r.name}</button>
        ))}
      </div>
      {role && (
        <section className="card overflow-x-auto p-0">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="p-3">Area</th>{catalog.actions.map((a) => <th key={a} className="p-3">{a}</th>)}</tr>
            </thead>
            <tbody>
              {catalog.resources.map((res) => (
                <tr key={res.key} className="border-t border-slate-100">
                  <td className="p-3"><div className="font-medium">{res.label}</div><div className="font-mono text-xs text-slate-400">{res.key}</div></td>
                  {catalog.actions.map((a) => {
                    const p = `${res.key}.${a}`;
                    return (
                      <td key={a} className="p-2">
                        <select aria-label={`${res.label} ${a}`} className="input px-1 py-1 text-xs" disabled={!editable}
                          value={draft[p] || ""} onChange={(e) => setDraft({ ...draft, [p]: e.target.value as Scope | "" })}>
                          <option value="">—</option>
                          {catalog.scopes.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {editable && role && <button className="btn-primary" onClick={save}>Save {role.name}</button>}
    </div>
  );
}

````

---

## `apps/web/app/(os)/admin/users/page.tsx`

````tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "@/components/session";
import { api, ApiError, can } from "@/lib/api";

interface UserRow { id: string; email: string; full_name: string; status: string; is_super_admin: boolean; roles: string[]; last_login_at: string | null; }
interface RoleRow { id: string; key: string; name: string; }

export default function UsersPage() {
  const { me } = useSession();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [roleId, setRoleId] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [picked, setPicked] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      setUsers(await api.get<UserRow[]>("/admin/users"));
      setRoles(await api.get<RoleRow[]>("/admin/roles"));
    } catch (e) { setMsg((e as ApiError).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  if (!me) return null;
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    try { await fn(); setMsg(ok); await load(); } catch (e) { setMsg((e as ApiError).message); }
  };

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-2xl font-semibold">Users and access</h1>
      {msg && <p role="status" className="rounded-lg bg-slate-100 px-3 py-2 text-sm">{msg}</p>}

      {can(me, "admin.users.create") && (
        <section className="card space-y-3">
          <h2 className="font-semibold">Invite an employee</h2>
          <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); void run(async () => {
              const r = await api.post<{ accept_path: string }>("/admin/invitations", { email, role_ids: roleId ? [roleId] : [] });
              setLink(window.location.origin + r.accept_path); setEmail("");
            }, "Invitation created. Send the link below to the person."); }}>
            <div className="min-w-64 flex-1"><label className="label" htmlFor="inv-email">Google account email</label>
              <input id="inv-email" className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
            <div><label className="label" htmlFor="inv-role">Role</label>
              <select id="inv-role" className="input" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
                <option value="">Employee (base)</option>
                {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select></div>
            <button className="btn-primary">Create invitation</button>
          </form>
          {link && <p className="break-all rounded-lg bg-slate-100 p-3 font-mono text-xs">{link}</p>}
        </section>
      )}

      <section className="card overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="p-3">Person</th><th className="p-3">Roles</th><th className="p-3">Status</th><th className="p-3">Last sign-in</th><th className="p-3"></th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-slate-100">
                <td className="p-3"><div className="font-medium">{u.full_name || u.email}</div><div className="text-xs text-slate-500">{u.email}</div></td>
                <td className="p-3">{u.is_super_admin && <span className="pill mr-1 bg-brand-soft text-brand">super admin</span>}{u.roles.map((r) => <span key={r} className="pill mr-1">{r}</span>)}</td>
                <td className="p-3">{u.status === "active" ? <span className="pill bg-emerald-50 text-emerald-700">active</span> : <span className="pill bg-red-50 text-red-700">deactivated</span>}</td>
                <td className="p-3 text-xs text-slate-500">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}</td>
                <td className="space-x-2 whitespace-nowrap p-3 text-right">
                  {u.id !== me.id && can(me, "admin.roles.manage") && <button className="btn" onClick={() => { setEditing(u); setPicked(roles.filter((r) => u.roles.includes(r.key)).map((r) => r.id)); }}>Roles</button>}
                  {u.id !== me.id && can(me, "admin.users.edit") && (u.status === "active"
                    ? <button className="btn" onClick={() => run(() => api.patch(`/admin/users/${u.id}`, { status: "deactivated" }), "Deactivated. Their sessions have ended.")}>Deactivate</button>
                    : <button className="btn" onClick={() => run(() => api.patch(`/admin/users/${u.id}`, { status: "active" }), "Reactivated.")}>Reactivate</button>)}
                  {u.id !== me.id && me.is_super_admin && (
                    <button className="btn" onClick={() => run(() => api.put(`/admin/users/${u.id}/super-admin`, { is_super_admin: !u.is_super_admin }),
                      u.is_super_admin ? "Super Admin removed." : "Now a Super Admin. They must set up MFA at next sign-in.")}>
                      {u.is_super_admin ? "Remove super admin" : "Make super admin"}
                    </button>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {editing && (
        <div className="fixed inset-0 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true">
          <div className="card w-full max-w-md space-y-3">
            <h3 className="font-semibold">Roles for {editing.full_name || editing.email}</h3>
            {roles.map((r) => (
              <label key={r.id} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={picked.includes(r.id)} onChange={(e) => setPicked(e.target.checked ? [...picked, r.id] : picked.filter((x) => x !== r.id))} />
                {r.name}
              </label>
            ))}
            <div className="flex justify-end gap-2">
              <button className="btn" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn-primary" onClick={() => { const u = editing; setEditing(null); void run(() => api.put(`/admin/users/${u.id}/roles`, { role_ids: picked }), "Roles updated."); }}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

````

---

## `apps/web/app/(os)/audit/page.tsx`

````tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

interface Ev { id: number; action: string; actor_user_id: string | null; target_type: string | null; target_id: string | null; before: unknown; after: unknown; ip: string | null; created_at: string; }

export default function AuditPage() {
  const [items, setItems] = useState<Ev[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [action, setAction] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async (before?: number) => {
    try {
      const qs = new URLSearchParams({ limit: "50" });
      if (action) qs.set("action", action);
      if (before) qs.set("before_id", String(before));
      const r = await api.get<{ items: Ev[]; next_before_id: number | null }>(`/audit-events?${qs}`);
      setItems((cur) => (before ? [...cur, ...r.items] : r.items));
      setNext(r.next_before_id);
    } catch (e) { setMsg((e as ApiError).message); }
  }, [action]);
  useEffect(() => { void load(); }, [load]);

  return (
    <div className="max-w-5xl space-y-4">
      <h1 className="text-2xl font-semibold">Audit log</h1>
      <p className="text-sm text-slate-600">Every sign-in, access change and admin action. Entries can't be edited or deleted.</p>
      {msg && <p role="status" className="text-sm">{msg}</p>}
      <select aria-label="Filter by type" className="input max-w-xs" value={action} onChange={(e) => setAction(e.target.value)}>
        <option value="">All events</option><option value="auth.">Sign-in and MFA</option><option value="admin.">Access and users</option><option value="org.">Teams and people</option>
      </select>
      <div className="card divide-y divide-slate-100 p-0">
        {items.map((e) => (
          <details key={e.id} className="p-3 text-sm">
            <summary className="flex cursor-pointer flex-wrap justify-between gap-2">
              <span className="font-mono">{e.action}</span>
              <span className="text-xs text-slate-500">{new Date(e.created_at).toLocaleString()} · {e.ip || "—"}</span>
            </summary>
            <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify({ actor: e.actor_user_id, target: `${e.target_type}:${e.target_id}`, before: e.before, after: e.after }, null, 2)}</pre>
          </details>
        ))}
        {items.length === 0 && <p className="p-4 text-sm text-slate-500">No events yet.</p>}
      </div>
      {next && <button className="btn" onClick={() => load(next)}>Load older</button>}
    </div>
  );
}

````

---

## `apps/web/app/(os)/employees/page.tsx`

````tsx
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

````

---

## `apps/web/app/(os)/layout.tsx`

````tsx
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

````

---

## `apps/web/app/(os)/page.tsx`

````tsx
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

````

---

## `apps/web/app/(os)/teams/page.tsx`

````tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "@/components/session";
import { api, ApiError, can } from "@/lib/api";

interface Team { id: string; name: string; kind: string; members?: { user_id: string; full_name: string; email: string; is_manager: boolean }[]; }
interface Person { user_id: string; full_name: string; email: string; }
const KINDS = [["sales", "Sales"], ["marketing", "Marketing"], ["tech", "Tech / Development"], ["ai_automation", "AI / Automation"], ["customer_success", "Customer Success"], ["finance_ops", "Finance / Operations"], ["custom", "Custom"]];

export default function TeamsPage() {
  const { me } = useSession();
  const [teams, setTeams] = useState<Team[]>([]);
  const [open, setOpen] = useState<Team | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("custom");
  const [addId, setAddId] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setTeams(await api.get<Team[]>("/teams")); setPeople(await api.get<Person[]>("/employees")); } catch (e) { setMsg((e as ApiError).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const openTeam = async (id: string) => { try { setOpen(await api.get<Team>(`/teams/${id}`)); } catch (e) { setMsg((e as ApiError).message); } };
  if (!me) return null;
  const editable = can(me, "org.teams.edit");

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-2xl font-semibold">Teams</h1>
      {msg && <p role="status" className="rounded-lg bg-slate-100 px-3 py-2 text-sm">{msg}</p>}
      {can(me, "org.teams.create") && (
        <form className="card flex flex-wrap items-end gap-3" onSubmit={async (e) => { e.preventDefault(); try { await api.post("/teams", { name, kind }); setName(""); await load(); } catch (err) { setMsg((err as ApiError).message); } }}>
          <div className="min-w-56 flex-1"><label className="label" htmlFor="t-name">New team</label><input id="t-name" className="input" required value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div><label className="label" htmlFor="t-kind">Type</label><select id="t-kind" className="input" value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
          <button className="btn-primary">Create team</button>
        </form>
      )}
      <div className="grid gap-4 md:grid-cols-[280px_1fr]">
        <div className="card space-y-1 p-2">
          {teams.length === 0 && <p className="p-3 text-sm text-slate-500">No teams yet.</p>}
          {teams.map((t) => (
            <button key={t.id} onClick={() => openTeam(t.id)} className={`block w-full rounded-lg px-3 py-2 text-left text-sm ${open?.id === t.id ? "bg-brand-soft text-brand" : "hover:bg-slate-100"}`}>
              {t.name}<span className="ml-2 text-xs text-slate-400">{t.kind}</span>
            </button>
          ))}
        </div>
        {open && (
          <div className="card space-y-3">
            <h2 className="font-semibold">{open.name}</h2>
            <ul className="divide-y divide-slate-100 text-sm">
              {(open.members || []).map((m) => (
                <li key={m.user_id} className="flex items-center justify-between py-2">
                  <span>{m.full_name || m.email}{m.is_manager && <span className="pill ml-2">manager</span>}</span>
                  {editable && <button className="text-xs text-slate-500 underline" onClick={async () => { await api.del(`/teams/${open.id}/members/${m.user_id}`); await openTeam(open.id); }}>Remove</button>}
                </li>
              ))}
            </ul>
            {editable && (
              <div className="flex gap-2">
                <select aria-label="Add member" className="input" value={addId} onChange={(e) => setAddId(e.target.value)}>
                  <option value="">Add a person…</option>
                  {people.filter((p) => !(open.members || []).some((m) => m.user_id === p.user_id)).map((p) => <option key={p.user_id} value={p.user_id}>{p.full_name || p.email}</option>)}
                </select>
                <button className="btn" disabled={!addId} onClick={async () => { await api.put(`/teams/${open.id}/members`, { user_id: addId }); setAddId(""); await openTeam(open.id); }}>Add</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

````

---

## `apps/web/app/globals.css`

````css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root { color-scheme: light; }
body { @apply bg-slate-50 text-slate-900 antialiased; }
.card { @apply rounded-xl border border-slate-200 bg-white p-5; }
.btn { @apply inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:border-brand disabled:opacity-50; }
.btn-primary { @apply btn border-brand bg-brand text-white; }
.input { @apply w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm; }
.label { @apply text-xs font-medium uppercase tracking-wide text-slate-500; }
.pill { @apply inline-block rounded-full bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600; }

````

---

## `apps/web/app/layout.tsx`

````tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "MME OS", description: "MME internal Business OS" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

````

---

## `apps/web/app/mfa/page.tsx`

````tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SessionProvider, useSession } from "@/components/session";
import { api, ApiError } from "@/lib/api";

function Mfa() {
  const { me, refresh, signOut } = useSession();
  const router = useRouter();
  const [setup, setSetup] = useState<{ otpauth_uri: string; secret: string } | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!me) return null;
  const enrolling = !me.mfa.enrolled;

  async function begin() {
    setError(null);
    try { setSetup(await api.post("/auth/mfa/setup")); } catch (e) { setError((e as ApiError).message); }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await api.post(enrolling ? "/auth/mfa/confirm" : "/auth/mfa/verify", { code });
      await refresh();
      router.replace("/");
    } catch (err) { setError((err as ApiError).message); } finally { setBusy(false); }
  }

  return (
    <main className="grid min-h-screen place-items-center px-4">
      <div className="card w-full max-w-md space-y-4">
        <h1 className="text-xl font-semibold">{enrolling ? "Set up your authenticator" : "Enter your authenticator code"}</h1>
        {enrolling && !setup && (
          <>
            <p className="text-sm text-slate-600">Your account can change access or company settings, so it needs a second step. Use Google Authenticator, Microsoft Authenticator or 1Password.</p>
            <button className="btn-primary" onClick={begin}>Start setup</button>
          </>
        )}
        {enrolling && setup && (
          <div className="space-y-2 text-sm">
            <p>In your authenticator app, add an account with this key:</p>
            <code className="block break-all rounded-lg bg-slate-100 p-3 font-mono">{setup.secret}</code>
            <p className="text-slate-500">On a phone with the app installed, you can <a className="text-brand underline" href={setup.otpauth_uri}>open this link</a> instead.</p>
          </div>
        )}
        {(!enrolling || setup) && (
          <form onSubmit={submit} className="space-y-3">
            <label className="label" htmlFor="code">6-digit code</label>
            <input id="code" className="input font-mono tracking-widest" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
              value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} autoFocus />
            {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
            <button className="btn-primary" disabled={busy || code.length !== 6}>{enrolling ? "Confirm" : "Continue"}</button>
          </form>
        )}
        <button className="text-xs text-slate-500 underline" onClick={signOut}>Sign out</button>
      </div>
    </main>
  );
}

export default function Page() {
  return <SessionProvider requireMfa={false}><Mfa /></SessionProvider>;
}

````

---

## `apps/web/app/sign-in/page.tsx`

````tsx
"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { googleSignInUrl } from "@/lib/api";

function SignIn() {
  const params = useSearchParams();
  const error = params.get("error");
  const invite = params.get("invite");
  return (
    <main className="grid min-h-screen place-items-center px-4">
      <div className="card w-full max-w-sm space-y-5">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand font-bold text-white">M</span>
          <div><div className="font-semibold">MME OS</div><div className="text-xs text-slate-500">Internal Business OS</div></div>
        </div>
        <h1 className="text-2xl font-semibold">Sign in</h1>
        <p className="text-sm text-slate-600">
          {invite ? "You've been invited to MME OS. Sign in with the Google account the invitation was sent to." : "Use your MME Google account."}
        </p>
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {/* A full-page navigation: the API sets the session cookie on its callback. */}
        <a className="btn w-full justify-center py-2.5" href={googleSignInUrl("/", invite)}>Sign in with Google</a>
        <p className="text-xs text-slate-500">Access is by invitation. Admin accounts also need an authenticator app.</p>
      </div>
    </main>
  );
}

export default function Page() {
  return <Suspense><SignIn /></Suspense>;
}

````

---

## `apps/web/components/session.tsx`

````tsx
"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Me, setCsrf } from "@/lib/api";

interface SessionValue { me: Me | null; loading: boolean; refresh: () => Promise<void>; signOut: () => Promise<void>; }
const Ctx = createContext<SessionValue>({ me: null, loading: true, refresh: async () => {}, signOut: async () => {} });

export function SessionProvider({ children, requireMfa = true }: { children: React.ReactNode; requireMfa?: boolean }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refresh = useCallback(async () => {
    try {
      const m = await api.get<Me>("/me");
      setCsrf(m.csrf_token);
      setMe(m);
      if (requireMfa && m.mfa.required && !m.mfa.passed) router.replace("/mfa");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/sign-in");
    } finally {
      setLoading(false);
    }
  }, [router, requireMfa]);

  const signOut = useCallback(async () => {
    try { await api.post("/auth/logout"); } finally { router.replace("/sign-in"); }
  }, [router]);

  useEffect(() => { void refresh(); }, [refresh]);
  return <Ctx.Provider value={{ me, loading, refresh, signOut }}>{children}</Ctx.Provider>;
}

export const useSession = () => useContext(Ctx);

````

---

## `apps/web/lib/api.ts`

````tsx
// Thin client for the MME OS API. The session lives in an httpOnly cookie set by the API;
// the CSRF token comes from /me and is sent on every write.

export const API = (process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000") + "/api/v1";

export type Scope = "own" | "team" | "department" | "all";

export interface Me {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  is_super_admin: boolean;
  roles: { key: string; name: string }[];
  team_ids: string[];
  department_id: string | null;
  mfa: { required: boolean; enrolled: boolean; passed: boolean };
  permissions: Record<string, Scope>;
  csrf_token: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public mfaRequired = false) {
    super(message);
  }
}

let csrf: string | null = null;
export const setCsrf = (token: string) => { csrf = token; };

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  if (method !== "GET" && csrf) headers["x-csrf-token"] = csrf;
  const res = await fetch(API + path, { method, headers, credentials: "include", body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    let message = "Something went wrong. Try again.";
    try {
      const data = await res.json();
      message = data?.detail?.[0]?.msg || data?.detail || data?.error?.message || message;
    } catch { /* keep default */ }
    throw new ApiError(res.status, typeof message === "string" ? message : "Request failed.", res.headers.get("x-mfa-required") === "1");
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  get: <T>(p: string) => call<T>("GET", p),
  post: <T>(p: string, b?: unknown) => call<T>("POST", p, b ?? {}),
  put: <T>(p: string, b?: unknown) => call<T>("PUT", p, b ?? {}),
  patch: <T>(p: string, b?: unknown) => call<T>("PATCH", p, b ?? {}),
  del: <T>(p: string) => call<T>("DELETE", p),
};

// UI hint only: the server computed `permissions` with the same engine that enforces every request.
export const can = (me: Me | null, permission: string) => !!me && permission in me.permissions;

export const googleSignInUrl = (next = "/", invite?: string | null) =>
  `${API}/auth/google/start?next=${encodeURIComponent(next)}${invite ? `&invite=${encodeURIComponent(invite)}` : ""}`;

````

---

## `apps/web/next-env.d.ts`

````tsx
/// <reference types="next" />
/// <reference types="next/image-types/global" />

````

---

## `apps/web/next.config.mjs`

````javascript
const api = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";
const csp = [
  "default-src 'self'",
  `connect-src 'self' ${api}`,
  "img-src 'self' https://lh3.googleusercontent.com data:",
  "style-src 'self' 'unsafe-inline'",
  "script-src 'self' 'unsafe-inline'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  `form-action 'self' ${api}`,
].join("; ");

/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "Content-Security-Policy", value: csp },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    }];
  },
};

````

---

## `apps/web/package.json`

````json
{
  "name": "@mme-os/web",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "15.1.3",
    "react": "19.0.0",
    "react-dom": "19.0.0"
  },
  "devDependencies": {
    "@types/node": "22.10.2",
    "@types/react": "19.0.2",
    "@types/react-dom": "19.0.2",
    "autoprefixer": "10.4.20",
    "eslint": "9.17.0",
    "eslint-config-next": "15.1.3",
    "postcss": "8.4.49",
    "tailwindcss": "3.4.17",
    "typescript": "5.7.2"
  }
}

````

---

## `apps/web/postcss.config.mjs`

````javascript
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };

````

---

## `apps/web/tailwind.config.ts`

````tsx
import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: { colors: { brand: { DEFAULT: "#3d5cf5", soft: "#e4e9ff" } } } },
  plugins: [],
} satisfies Config;

````

---

## `apps/web/tsconfig.json`

````json
{
  "compilerOptions": {
    "target": "ES2022", "lib": ["dom", "dom.iterable", "ES2022"], "allowJs": false, "skipLibCheck": true,
    "strict": true, "noEmit": true, "esModuleInterop": true, "module": "esnext", "moduleResolution": "bundler",
    "resolveJsonModule": true, "isolatedModules": true, "jsx": "preserve", "incremental": true,
    "plugins": [{ "name": "next" }], "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}

````

---

## `infra/docker-compose.yml`

````yaml
# Local development: Postgres, Redis, MinIO (S3), n8n, API and web.
#   docker compose -f infra/docker-compose.yml up --build
services:
  db:
    image: postgres:16
    environment: { POSTGRES_USER: mme, POSTGRES_PASSWORD: mme, POSTGRES_DB: mme_os }
    ports: ["5432:5432"]
    volumes: [dbdata:/var/lib/postgresql/data]
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U mme"], interval: 5s, retries: 10 }
  redis:
    image: redis:7
    ports: ["6379:6379"]
  minio:
    image: minio/minio:RELEASE.2024-12-18T13-15-44Z
    command: server /data --console-address ":9001"
    environment: { MINIO_ROOT_USER: mme, MINIO_ROOT_PASSWORD: mme-dev-password }
    ports: ["9000:9000", "9001:9001"]
  n8n:
    image: n8nio/n8n:1.72.1
    ports: ["5678:5678"]
    environment: { N8N_SECURE_COOKIE: "false" }
  api:
    build: ../apps/api
    env_file: ../.env
    environment:
      DATABASE_URL: postgresql+psycopg://mme:mme@db:5432/mme_os
      REDIS_URL: redis://redis:6379/0
    ports: ["8000:8000"]
    depends_on: { db: { condition: service_healthy }, redis: { condition: service_started } }
  web:
    image: node:22
    working_dir: /web
    command: sh -c "npm install && npm run dev"
    environment: { NEXT_PUBLIC_API_ORIGIN: "http://localhost:8000" }
    volumes: ["../apps/web:/web"]
    ports: ["3000:3000"]
volumes: { dbdata: {} }

````
