"""API tests run against a real PostgreSQL (CI service container or docker compose).

TEST_DATABASE_URL must point at an empty database the tests may wipe.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
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
from app.core.models import Employee, Organization, Role, RoleGrant, Session, Team, TeamMember, User, UserRole  # noqa: E402
from app.core.security import new_token, token_hash  # noqa: E402
from app.main import app  # noqa: E402

SQL_DIR = Path(__file__).resolve().parents[2] / "migrations" / "sql"


@pytest.fixture(scope="session", autouse=True)
def schema():
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        for f in sorted(SQL_DIR.glob("*.sql")):
            c.execute(text(f.read_text()))
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
        u = User(
            organization_id=org.id, email=email, full_name=email.split("@")[0].title(), is_super_admin=super_admin, mfa_required=super_admin
        )
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
        db.add(
            Session(
                user_id=user.id,
                organization_id=user.organization_id,
                token_hash=token_hash(raw),
                mfa_passed=mfa,
                expires_at=datetime.now(UTC) + timedelta(hours=2),
                last_seen_at=datetime.now(UTC),
            )
        )
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
