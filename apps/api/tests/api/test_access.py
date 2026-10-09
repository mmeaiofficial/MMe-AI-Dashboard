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
    # The trigger is per row, so the table needs a row for UPDATE/DELETE to be refused.
    with engine.begin() as c:
        c.execute(text("INSERT INTO audit_events (organization_id, action) VALUES (:o, 'test.event')"), {"o": world["org"].id})
    for stmt in ("UPDATE audit_events SET action = 'x.y'", "DELETE FROM audit_events"):
        with pytest.raises(Exception, match="append-only"):
            with engine.begin() as c:
                c.execute(text(stmt))
