"""Giving people access by email: job, team, manager flag and per-person screens, with escalation guards."""

from __future__ import annotations

from sqlalchemy import select

from app.audit.writer import RequestContext
from app.core.db import SessionLocal
from app.core.models import Invitation, Role, RoleGrant, TeamMember, User, UserRole
from app.modules.identity import service as S


def role_id(world, key):
    return str(world["roles"][key].id)


def give(c, email, role, **kw):
    return c.send("POST", "/admin/access", {"email": email, "role_id": role, **kw})


def sign_in_as_new_user(world, email):
    """What the Google callback does for a first sign-in with an open invitation."""
    db = SessionLocal()
    org = db.get(type(world["org"]), world["org"].id)
    inv = S.open_invitation(db, org.id, email, None)
    user = S.create_user(db, org, email, "New Person", f"sub-{email}", None, inv, RequestContext(org.id, None, None, None, None))
    db.commit()
    roles = db.scalars(select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)).all()
    teams = db.execute(select(TeamMember.team_id, TeamMember.is_manager).where(TeamMember.user_id == user.id)).all()
    db.close()
    return roles, teams


def test_invite_by_email_gives_job_team_and_manager(world, as_user):
    founder = as_user("founder")
    sales = str(world["teams"]["sales"].id)
    r = give(founder, "Lead.Caller@MME-AI.com", role_id(world, "sales_l1"), team_id=sales, team_manager=True)
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "invited" and r.json()["email"] == "lead.caller@mme-ai.com"

    listed = next(p for p in founder.get("/admin/access").json()["people"] if p["email"] == "lead.caller@mme-ai.com")
    assert listed["status"] == "invited" and listed["roles"][0]["key"] == "sales_l1"
    assert listed["teams"] == [{"id": sales, "name": "Sales", "kind": "sales", "is_manager": True}]
    assert {f["resource"] for f in listed["features"]} >= {"sales.calls"}

    roles, teams = sign_in_as_new_user(world, "lead.caller@mme-ai.com")
    assert [r.key for r in roles] == ["sales_l1"]
    assert [(str(t), m) for t, m in teams] == [(sales, True)]


def test_custom_screens_make_a_personal_role_and_old_ones_are_cleaned_up(world, as_user):
    founder = as_user("founder")
    grants = [{"permission": "crm.leads.view", "scope": "team"}, {"permission": "work.tasks.view", "scope": "own"}]
    r = give(founder, "custom@mme-ai.com", role_id(world, "lead_generation"), grants=grants)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "Lead generation (custom)"
    person = next(p for p in founder.get("/admin/access").json()["people"] if p["email"] == "custom@mme-ai.com")
    assert person["roles"][0]["personal"] is True
    assert {(f["resource"], f["level"], f["reach"]) for f in person["features"]} == {
        ("crm.leads", "view", "team"),
        ("work.tasks", "view", "own"),
    }
    # Personal roles are hidden from job pickers but marked in the roles list.
    assert any(x["personal"] for x in founder.get("/admin/roles").json())

    # Re-giving access (now the plain job) revokes the old invitation and deletes the unused personal role.
    assert give(founder, "custom@mme-ai.com", role_id(world, "lead_generation")).json()["role"] == "Lead generation"
    db = SessionLocal()
    assert db.scalars(select(Role).where(Role.key.startswith("person_"))).all() == []
    assert len(db.scalars(select(Invitation).where(Invitation.email == "custom@mme-ai.com", Invitation.revoked_at.is_(None))).all()) == 1
    db.close()


def test_existing_person_changes_immediately(world, as_user):
    founder = as_user("founder")
    tech = str(world["teams"]["tech"].id)
    r = give(founder, "sales@mme-ai.com", role_id(world, "tech_automation"), team_id=tech)
    assert r.json()["result"] == "updated"
    me = as_user("sales_exec").get("/me").json()
    assert [x["key"] for x in me["roles"]] == ["tech_automation"] and tech in me["team_ids"]


def test_guards(world, as_user):
    founder, ops = as_user("founder"), as_user("ops")
    # Operations admin can't manage roles at all.
    assert give(ops, "x@mme-ai.com", role_id(world, "employee")).status_code == 403
    # Nobody changes their own access.
    assert give(founder, "founder@mme-ai.com", role_id(world, "employee")).status_code == 403
    # Unknown permission names are rejected.
    bad = give(founder, "y@mme-ai.com", role_id(world, "employee"), grants=[{"permission": "crm.leads.fly", "scope": "own"}])
    assert bad.status_code == 422
    # Personal roles can't be picked as a job.
    give(founder, "z@mme-ai.com", role_id(world, "employee"), grants=[{"permission": "work.tasks.view", "scope": "own"}])
    db = SessionLocal()
    personal = db.scalar(select(Role.id).where(Role.key.startswith("person_")))
    db.close()
    assert give(founder, "w@mme-ai.com", str(personal)).status_code == 404


def test_manager_cannot_give_more_than_they_hold(world, as_user):
    # A team manager allowed to hand out access, but who only sees leads of their own team.
    db = SessionLocal()
    org = world["org"].id
    role = Role(organization_id=org, key="team_lead", name="Team lead")
    db.add(role)
    db.flush()
    for p, s in [("admin.roles.manage", "all"), ("admin.users.view", "all"), ("admin.users.create", "all"), ("crm.leads.view", "team")]:
        db.add(RoleGrant(role_id=role.id, organization_id=org, permission=p, scope=s))
    lead = db.scalar(select(User).where(User.email == "salesmgr@mme-ai.com"))
    db.add(UserRole(user_id=lead.id, role_id=role.id, organization_id=org))
    db.commit()
    db.close()
    mgr = as_user("sales_mgr")
    ok = give(mgr, "intern@mme-ai.com", role_id(world, "employee"), grants=[{"permission": "crm.leads.view", "scope": "team"}])
    assert ok.status_code == 200, ok.text
    wider = give(mgr, "intern2@mme-ai.com", role_id(world, "employee"), grants=[{"permission": "crm.leads.view", "scope": "all"}])
    assert wider.status_code == 403 and "can't grant" in wider.json()["detail"]


def test_revoke_invitation(world, as_user):
    founder = as_user("founder")
    give(founder, "gone@mme-ai.com", role_id(world, "employee"), grants=[{"permission": "work.tasks.view", "scope": "own"}])
    inv = next(p for p in founder.get("/admin/access").json()["people"] if p["email"] == "gone@mme-ai.com")
    assert founder.send("POST", f"/admin/access/invitations/{inv['id']}/revoke").status_code == 200
    assert all(p["email"] != "gone@mme-ai.com" for p in founder.get("/admin/access").json()["people"])
    db = SessionLocal()
    assert db.scalars(select(Role).where(Role.key.startswith("person_"))).all() == []
    db.close()
