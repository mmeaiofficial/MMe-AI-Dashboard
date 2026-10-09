"""The pipeline end to end: lead team -> Sales L1 -> Sales L2 -> tech tickets, with handoffs and data scopes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.db import SessionLocal
from app.core.models import Employee, Team, TeamMember, User, UserRole


def soon(hours=24):
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


@pytest.fixture()
def pipe(world):
    """Adds the pipeline teams and one person per stage (two L1 callers) to the world fixture."""
    db = SessionLocal()
    org, roles = world["org"], world["roles"]
    teams = {}
    for kind, name in [("lead_gen", "Lead team"), ("sales_l1", "Sales L1"), ("sales_l2", "Sales L2")]:
        t = Team(organization_id=org.id, name=name, kind=kind)
        db.add(t)
        db.flush()
        teams[kind] = t
    for key, email, role, kind in [
        ("lg", "leads@mme-ai.com", "lead_generation", "lead_gen"),
        ("l1a", "caller1@mme-ai.com", "sales_l1", "sales_l1"),
        ("l1b", "caller2@mme-ai.com", "sales_l1", "sales_l1"),
        ("l2", "closer@mme-ai.com", "sales_l2", "sales_l2"),
    ]:
        u = User(organization_id=org.id, email=email, full_name=key.upper())
        db.add(u)
        db.flush()
        db.add_all(
            [
                Employee(user_id=u.id, organization_id=org.id),
                UserRole(user_id=u.id, role_id=roles[role].id, organization_id=org.id),
                TeamMember(team_id=teams[kind].id, user_id=u.id, organization_id=org.id),
            ]
        )
        world["users"][key] = u
    db.commit()
    db.close()
    # The world's Tech team has kind "tech" and holds "dev" (Tech and automation role, team scope on tickets).
    return world


def new_lead(c, **kw):
    r = c.send("POST", "/leads", {"contact_name": "Asha Rao", "company": "Rao Realty", "phone": "+91 98765 43210", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def book(c, lead_id, **kw):
    return c.send(
        "POST",
        f"/calls/leads/{lead_id}/log",
        {
            "outcome": "meeting_booked",
            "notes": "Wants WhatsApp follow-ups automated",
            "meeting": {"scheduled_at": soon(), "mode": "google_meet", "link_or_location": "https://meet.example/x"},
            **kw,
        },
    )


def test_full_pipeline(pipe, as_user):
    lg, l1a, l1b, l2, dev = (as_user(k) for k in ("lg", "l1a", "l1b", "l2", "dev"))
    u = pipe["users"]

    # Lead team adds and qualifies two leads: they go to different callers (shortest queue first).
    a, b = new_lead(lg), new_lead(lg, contact_name="Vikram", phone="+91 90000 00001")
    qa = lg.send("POST", f"/leads/{a['id']}/qualify").json()
    qb = lg.send("POST", f"/leads/{b['id']}/qualify").json()
    assert {qa["caller"]["id"], qb["caller"]["id"]} == {str(u["l1a"].id), str(u["l1b"].id)}
    caller_a = l1a if qa["caller"]["id"] == str(u["l1a"].id) else l1b
    other = l1b if caller_a is l1a else l1a

    # Each caller sees only their own lead.
    assert [x["id"] for x in caller_a.get("/calls/queue").json()["items"]] == [a["id"]]
    assert other.send("POST", f"/calls/leads/{a['id']}/log", {"outcome": "no_answer"}).status_code == 404

    # No answer first, then a booked meeting: the lead moves to Sales L2.
    r = caller_a.send("POST", f"/calls/leads/{a['id']}/log", {"outcome": "no_answer"})
    assert r.json()["status"] == "contacted" and r.json()["call_attempts"] == 1
    r = book(caller_a, a["id"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "meeting_booked" and r.json()["closer"]["id"] == str(u["l2"].id)
    assert caller_a.get("/calls/queue").json()["items"] == []
    assert caller_a.get("/meetings").status_code == 403  # L1 has no access to Sales L2's meetings

    # L2 sees the meeting with the caller's notes and call history.
    meetings = l2.get("/meetings").json()["items"]
    assert len(meetings) == 1 and meetings[0]["lead"]["company"] == "Rao Realty"
    mid = meetings[0]["id"]
    detail = l2.get(f"/meetings/{mid}").json()
    assert [c["outcome"] for c in detail["calls"]] == ["meeting_booked", "no_answer"]
    assert detail["agenda"] == "Wants WhatsApp follow-ups automated"

    # Won: the confirmed features become a client, a project and tickets for tech.
    r = l2.send(
        "POST",
        f"/meetings/{mid}/complete",
        {
            "outcome": "won",
            "notes": "Starts next week",
            "deal_value": 25000,
            "project_summary": "Lead follow-up automation",
            "requirements": [
                {"title": "WhatsApp auto-reply", "details": "Reply within 1 minute", "priority": "high"},
                {"title": "Lead dashboard", "priority": "normal"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["tickets"] == 2

    tickets = dev.get("/tickets").json()["items"]
    assert sorted(t["title"] for t in tickets) == ["Lead dashboard", "WhatsApp auto-reply"]
    assert all(t["client"]["name"] == "Rao Realty" and t["status"] == "todo" and t["assignee"] is None for t in tickets)
    t = next(x for x in tickets if x["title"] == "WhatsApp auto-reply")
    full = dev.get(f"/tickets/{t['id']}").json()
    assert full["description"] == "Reply within 1 minute" and full["priority"] == "high"
    assert full["client"]["phone"] == "+91 98765 43210" and full["meeting"]["outcome_notes"] == "Starts next week"
    assert full["project"]["summary"] == "Lead follow-up automation"

    # Tech takes the ticket, moves it, and leaves a note.
    r = dev.send("PATCH", f"/tickets/{t['id']}", {"assignee_id": str(u["dev"].id), "status": "in_progress"})
    assert r.status_code == 200 and r.json()["assignee"]["id"] == str(u["dev"].id)
    assert dev.send("POST", f"/tickets/{t['id']}/notes", {"body": "Using the Cloud API"}).status_code == 201
    assert [x["title"] for x in dev.get("/tickets?mine=true").json()["items"]] == ["WhatsApp auto-reply"]
    assert dev.send("PATCH", f"/tickets/{t['id']}", {"status": "done"}).json()["done_at"] is not None

    # The lead team sees how their lead ended.
    assert next(x for x in lg.get("/leads").json()["items"] if x["id"] == a["id"])["status"] == "won"


def test_won_needs_features_and_no_show_returns_to_caller(pipe, as_user):
    lg, l2 = as_user("lg"), as_user("l2")
    lead = new_lead(lg)
    q = lg.send("POST", f"/leads/{lead['id']}/qualify").json()
    caller = as_user("l1a" if q["caller"]["id"] == str(pipe["users"]["l1a"].id) else "l1b")
    book(caller, lead["id"])
    mid = l2.get("/meetings").json()["items"][0]["id"]
    assert l2.send("POST", f"/meetings/{mid}/complete", {"outcome": "won"}).status_code == 422

    assert l2.send("POST", f"/meetings/{mid}/complete", {"outcome": "no_show"}).status_code == 200
    back = caller.get("/calls/queue").json()["items"]
    assert [x["id"] for x in back] == [lead["id"]] and back[0]["status"] == "callback" and back[0]["due"] is True
    assert l2.send("POST", f"/meetings/{mid}/complete", {"outcome": "lost"}).status_code == 409


def test_unassigned_pool_without_pipeline_teams(world, as_user):
    # No Sales L1 team yet: qualified leads wait in a shared pool and the first caller claims them.
    ops, sales = as_user("ops"), as_user("sales_exec")
    lead = new_lead(as_user("founder"))
    assert as_user("founder").send("POST", f"/leads/{lead['id']}/qualify").json()["caller"] is None
    pool = sales.get("/calls/queue").json()["items"]
    assert pool[0]["id"] == lead["id"] and pool[0]["unassigned"] is True
    r = sales.send("POST", f"/calls/leads/{lead['id']}/log", {"outcome": "callback", "callback_at": soon(2)})
    assert r.status_code == 200 and r.json()["caller"]["id"] == str(world["users"]["sales_exec"].id)
    assert ops.send("POST", f"/calls/leads/{lead['id']}/log", {"outcome": "busy"}).status_code == 403  # view-only on calls


def test_scopes_and_validation(pipe, as_user):
    lg, emp = as_user("lg"), as_user("emp")
    lead = new_lead(lg)
    assert emp.get("/leads").status_code == 403
    assert emp.get("/tickets").json()["items"] == []  # base employees see only tickets of their own
    assert as_user("l1a").get("/leads").status_code == 403
    # Callback needs a future time; a booked meeting needs its date.
    lg.send("POST", f"/leads/{lead['id']}/qualify")
    owner = next(k for k in ("l1a", "l1b") if as_user(k).get("/calls/queue").json()["items"])
    c = as_user(owner)
    assert c.send("POST", f"/calls/leads/{lead['id']}/log", {"outcome": "callback"}).status_code == 422
    assert c.send("POST", f"/calls/leads/{lead['id']}/log", {"outcome": "meeting_booked"}).status_code == 422
    assert lg.send("POST", f"/leads/{lead['id']}/qualify").status_code == 409


def test_import_skips_duplicates(pipe, as_user):
    lg = as_user("lg")
    new_lead(lg, phone="+91 98765 43210")
    r = lg.send(
        "POST",
        "/leads/import",
        {
            "leads": [
                {"contact_name": "Dup by phone", "phone": "098765-43210"},
                {"contact_name": "Neha", "email": "neha@shop.in"},
                {"contact_name": "Dup in file", "email": "NEHA@shop.in"},
                {"contact_name": "Kabir", "phone": "+91 91234 56789"},
            ]
        },
    )
    assert r.json() == {"created": 2, "skipped": 2}
    items = lg.get("/leads?status=new").json()["items"]
    assert {x["contact_name"] for x in items} == {"Asha Rao", "Neha", "Kabir"} and {x["source"] for x in items} == {"manual", "import"}


def test_ticket_only_assignable_to_its_team(pipe, as_user):
    lg, l2, dev = as_user("lg"), as_user("l2"), as_user("dev")
    lead = new_lead(lg)
    q = lg.send("POST", f"/leads/{lead['id']}/qualify").json()
    book(as_user("l1a" if q["caller"]["id"] == str(pipe["users"]["l1a"].id) else "l1b"), lead["id"])
    mid = l2.get("/meetings").json()["items"][0]["id"]
    l2.send("POST", f"/meetings/{mid}/complete", {"outcome": "won", "requirements": [{"title": "CRM sync"}]})
    tid = dev.get("/tickets").json()["items"][0]["id"]
    r = dev.send("PATCH", f"/tickets/{tid}", {"assignee_id": str(pipe["users"]["sales_exec"].id)})
    assert r.status_code == 422
    # Sales L2 created the ticket, so they can follow it; Sales L1 cannot.
    assert len(l2.get("/tickets").json()["items"]) == 1
    assert as_user("l1a").get("/tickets").json()["items"] == []
