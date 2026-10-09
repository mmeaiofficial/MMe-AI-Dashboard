"""The MME-AI pipeline: Leads (lead team) -> Cold calls (Sales L1) -> Meetings (Sales L2) -> tickets.

Handoffs are automatic:
- qualifying a lead assigns it to the Sales L1 caller with the shortest queue;
- logging "meeting booked" creates the meeting and assigns the Sales L2 closer with the fewest meetings;
- marking a meeting "won" with the client's confirmed features creates the client, a project and one
  ticket per feature for the tech team; a no-show sends the lead back to its caller to rebook.
If no team of the right kind exists yet, work waits unassigned and anyone on that stage can claim it.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import record
from ...authz import engine as E
from ...core.db import get_db
from ...core.deps import Caller, requires
from ...core.models import Client, Lead, LeadCall, Meeting, Project, Ticket
from .common import OPEN_CALL_STATUSES, fetch, first_team, iso, names, person, pick_least_loaded, require, scope_filter
from .tickets import create_tickets

router = APIRouter(tags=["pipeline"])

LEAD_SOURCES = Literal["manual", "import", "website", "referral", "social", "cold_list", "event", "other"]
CALL_OUTCOMES = Literal["no_answer", "busy", "wrong_number", "not_interested", "callback", "interested", "meeting_booked"]
MEETING_MODES = Literal["google_meet", "zoom", "phone", "in_person", "other"]
PRIORITIES = Literal["low", "normal", "high", "urgent"]


def _now() -> datetime:
    return datetime.now(UTC)


def _lead_out(lead: Lead, people: dict, last_call: LeadCall | None = None) -> dict:
    out = {
        "id": str(lead.id),
        "contact_name": lead.contact_name,
        "company": lead.company,
        "phone": lead.phone,
        "email": lead.email,
        "city": lead.city,
        "industry": lead.industry,
        "website": lead.website,
        "source": lead.source,
        "notes": lead.notes,
        "status": lead.status,
        "status_reason": lead.status_reason,
        "created_by": person(people, lead.created_by),
        "caller": person(people, lead.caller_id),
        "closer": person(people, lead.closer_id),
        "call_attempts": lead.call_attempts,
        "last_called_at": iso(lead.last_called_at),
        "next_call_at": iso(lead.next_call_at),
        "qualified_at": iso(lead.qualified_at),
        "created_at": iso(lead.created_at),
    }
    if last_call is not None:
        out["last_call"] = {"outcome": last_call.outcome, "notes": last_call.notes, "at": iso(last_call.created_at)}
    return out


def _lead_people(db: DbSession, leads: Sequence[Lead]) -> dict:
    return names(db, [x for lead in leads for x in (lead.created_by, lead.caller_id, lead.closer_id)])


def _get_lead(db: DbSession, caller: Caller, lead_id: uuid.UUID, permission: str, team_col: str, open_pool: bool = False) -> Lead:
    """A lead the caller may act on under ``permission``; ``team_col`` names the stage's team column.
    ``open_pool`` also allows unassigned qualified leads (the shared L1 pool)."""
    lead = db.get(Lead, lead_id)
    if lead is None or lead.organization_id != caller.user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    if open_pool and lead.caller_id is None and lead.status in OPEN_CALL_STATUSES:
        require(caller, permission)
        return lead
    ref = E.RecordRef(
        organization_id=lead.organization_id,
        owner_id=lead.created_by if permission.startswith("crm.") else None,
        team_id=getattr(lead, team_col),
        assignee_ids=frozenset(x for x in (lead.caller_id, lead.closer_id) if x),
    )
    try:
        E.check(caller.subject, permission, ref)
    except E.Forbidden:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do that.") from None
    except E.NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
    return lead


def _norm_phone(p: str | None) -> str | None:
    digits = re.sub(r"\D", "", p or "")
    return digits[-10:] if len(digits) >= 7 else None


# =====================================================================================
# Leads (lead team)
# =====================================================================================
class LeadIn(BaseModel):
    contact_name: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=254)
    city: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=300)
    source: LEAD_SOURCES = "manual"
    notes: str | None = Field(default=None, max_length=4000)


class LeadPatch(BaseModel):
    contact_name: str | None = Field(default=None, min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=254)
    city: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=4000)


class ImportIn(BaseModel):
    leads: list[LeadIn] = Field(min_length=1, max_length=500)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


def _clean(body: BaseModel) -> dict:
    return {
        k: (v.strip() or None) if isinstance(v, str) and k != "contact_name" else (v.strip() if isinstance(v, str) else v)
        for k, v in body.model_dump(exclude_unset=True).items()
    }


@router.get("/leads")
def list_leads(
    status_: str | None = Query(default=None, alias="status", max_length=200),
    q: str | None = Query(default=None, max_length=120),
    caller: Caller = Depends(requires("crm.leads.view")),
    db: DbSession = Depends(get_db),
) -> dict:
    scope = and_(
        Lead.organization_id == caller.user.organization_id,
        scope_filter(caller, "crm.leads.view", [Lead.created_by, Lead.caller_id, Lead.closer_id], [Lead.source_team_id]),
    )
    counts = dict(db.execute(select(Lead.status, func.count()).where(scope).group_by(Lead.status)).tuples().all())
    query = select(Lead).where(scope)
    if status_:
        query = query.where(Lead.status.in_([s for s in status_.split(",") if s]))
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                Lead.contact_name.ilike(like),
                Lead.company.ilike(like),
                Lead.phone.ilike(like),
                Lead.email.ilike(like),
                Lead.city.ilike(like),
            )
        )
    leads = db.scalars(query.order_by(Lead.created_at.desc()).limit(300)).all()
    people = _lead_people(db, leads)
    return {"items": [_lead_out(x, people) for x in leads], "counts": counts}


@router.post("/leads", status_code=201)
def create_lead(body: LeadIn, caller: Caller = Depends(requires("crm.leads.create")), db: DbSession = Depends(get_db)) -> dict:
    org = caller.user.organization_id
    lead = Lead(
        organization_id=org, created_by=caller.user.id, source_team_id=first_team(db, org, "lead_gen", caller.user.id), **_clean(body)
    )
    db.add(lead)
    db.flush()
    record(db, caller.ctx, "crm.lead_created", "lead", lead.id, after={"contact_name": lead.contact_name, "company": lead.company})
    return _lead_out(lead, names(db, [caller.user.id]))


@router.post("/leads/import")
def import_leads(body: ImportIn, caller: Caller = Depends(requires("crm.leads.create")), db: DbSession = Depends(get_db)) -> dict:
    """Bulk add (e.g. a pasted spreadsheet). Rows whose phone or email already exists are skipped."""
    org = caller.user.organization_id
    team = first_team(db, org, "lead_gen", caller.user.id)
    known_phones = {_norm_phone(p) for p in db.scalars(select(Lead.phone).where(Lead.organization_id == org, Lead.phone.is_not(None)))}
    known_emails = {e.lower() for e in db.scalars(select(Lead.email).where(Lead.organization_id == org, Lead.email.is_not(None))) if e}
    created = skipped = 0
    for row in body.leads:
        data = _clean(row)
        phone, email = _norm_phone(data.get("phone")), (data.get("email") or "").lower() or None
        if (phone and phone in known_phones) or (email and email in known_emails):
            skipped += 1
            continue
        data["source"] = row.source if row.source != "manual" else "import"
        db.add(Lead(organization_id=org, created_by=caller.user.id, source_team_id=team, **data))
        if phone:
            known_phones.add(phone)
        if email:
            known_emails.add(email)
        created += 1
    db.flush()
    record(db, caller.ctx, "crm.leads_imported", "lead", None, after={"created": created, "skipped": skipped})
    return {"created": created, "skipped": skipped}


@router.patch("/leads/{lead_id}")
def update_lead(
    lead_id: uuid.UUID, body: LeadPatch, caller: Caller = Depends(requires("crm.leads.edit")), db: DbSession = Depends(get_db)
) -> dict:
    lead = _get_lead(db, caller, lead_id, "crm.leads.edit", "source_team_id")
    for k, v in _clean(body).items():
        setattr(lead, k, v)
    db.flush()
    record(db, caller.ctx, "crm.lead_updated", "lead", lead.id, after=_clean(body))
    return _lead_out(lead, _lead_people(db, [lead]))


@router.post("/leads/{lead_id}/qualify")
def qualify_lead(lead_id: uuid.UUID, caller: Caller = Depends(requires("crm.leads.edit")), db: DbSession = Depends(get_db)) -> dict:
    lead = _get_lead(db, caller, lead_id, "crm.leads.edit", "source_team_id")
    if lead.status not in ("new", "disqualified"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This lead has already moved on from qualification.")
    caller_id, team_id = pick_least_loaded(db, lead.organization_id, "sales_l1", Lead.caller_id, Lead.status.in_(OPEN_CALL_STATUSES))
    lead.status, lead.status_reason, lead.qualified_at, lead.next_call_at = "qualified", None, _now(), _now()
    lead.caller_id, lead.caller_team_id = caller_id, team_id
    db.flush()
    record(db, caller.ctx, "crm.lead_qualified", "lead", lead.id, after={"caller_id": caller_id})
    return _lead_out(lead, _lead_people(db, [lead]))


@router.post("/leads/{lead_id}/disqualify")
def disqualify_lead(
    lead_id: uuid.UUID, body: ReasonIn, caller: Caller = Depends(requires("crm.leads.edit")), db: DbSession = Depends(get_db)
) -> dict:
    lead = _get_lead(db, caller, lead_id, "crm.leads.edit", "source_team_id")
    if lead.status not in ("new", "qualified"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Only new or qualified leads can be rejected here.")
    lead.status, lead.status_reason, lead.caller_id, lead.caller_team_id, lead.next_call_at = (
        "disqualified",
        body.reason.strip(),
        None,
        None,
        None,
    )
    db.flush()
    record(db, caller.ctx, "crm.lead_disqualified", "lead", lead.id, after={"reason": lead.status_reason})
    return _lead_out(lead, _lead_people(db, [lead]))


# =====================================================================================
# Cold calls (Sales L1)
# =====================================================================================
class MeetingIn(BaseModel):
    scheduled_at: AwareDatetime
    duration_minutes: int = Field(default=30, ge=5, le=480)
    mode: MEETING_MODES = "google_meet"
    link_or_location: str | None = Field(default=None, max_length=500)
    agenda: str | None = Field(default=None, max_length=2000)


class CallIn(BaseModel):
    outcome: CALL_OUTCOMES
    notes: str | None = Field(default=None, max_length=2000)
    callback_at: AwareDatetime | None = None
    meeting: MeetingIn | None = None


def _calls_scope(caller: Caller):
    mine = scope_filter(caller, "sales.calls.view", [Lead.caller_id], [Lead.caller_team_id])
    pool = and_(Lead.caller_id.is_(None), Lead.status == "qualified")
    return and_(Lead.organization_id == caller.user.organization_id, or_(mine, pool))


def _last_calls(db: DbSession, lead_ids: list[uuid.UUID]) -> dict[uuid.UUID, LeadCall]:
    if not lead_ids:
        return {}
    latest = (
        select(LeadCall.lead_id, func.max(LeadCall.created_at).label("at"))
        .where(LeadCall.lead_id.in_(lead_ids))
        .group_by(LeadCall.lead_id)
        .subquery()
    )
    rows = db.scalars(select(LeadCall).join(latest, and_(LeadCall.lead_id == latest.c.lead_id, LeadCall.created_at == latest.c.at))).all()
    return {c.lead_id: c for c in rows}


@router.get("/calls/queue")
def call_queue(caller: Caller = Depends(requires("sales.calls.view")), db: DbSession = Depends(get_db)) -> dict:
    leads = db.scalars(
        select(Lead)
        .where(_calls_scope(caller), Lead.status.in_(OPEN_CALL_STATUSES))
        .order_by(Lead.next_call_at.asc().nulls_first(), Lead.qualified_at.asc())
        .limit(300)
    ).all()
    last = _last_calls(db, [x.id for x in leads])
    people = _lead_people(db, leads)
    now = _now()
    me = caller.user.id
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    calls_today = db.scalar(select(func.count()).select_from(LeadCall).where(LeadCall.caller_id == me, LeadCall.created_at >= start)) or 0
    booked_week = (
        db.scalar(select(func.count()).select_from(Meeting).where(Meeting.booked_by == me, Meeting.created_at >= now - timedelta(days=7)))
        or 0
    )
    return {
        "items": [
            _lead_out(x, people, last.get(x.id))
            | {"due": x.next_call_at is None or x.next_call_at <= now, "unassigned": x.caller_id is None}
            for x in leads
        ],
        "stats": {
            "calls_today": calls_today,
            "meetings_booked_7d": booked_week,
            "due_now": sum(1 for x in leads if x.caller_id and (x.next_call_at is None or x.next_call_at <= now)),
        },
    }


def _call_history(db: DbSession, lead_id: uuid.UUID) -> list[dict]:
    calls = db.scalars(select(LeadCall).where(LeadCall.lead_id == lead_id).order_by(LeadCall.created_at.desc()).limit(50)).all()
    people = names(db, [c.caller_id for c in calls])
    return [{"outcome": c.outcome, "notes": c.notes, "at": iso(c.created_at), "by": person(people, c.caller_id)} for c in calls]


@router.get("/calls/leads/{lead_id}")
def call_lead(lead_id: uuid.UUID, caller: Caller = Depends(requires("sales.calls.view")), db: DbSession = Depends(get_db)) -> dict:
    lead = _get_lead(db, caller, lead_id, "sales.calls.view", "caller_team_id", open_pool=True)
    return _lead_out(lead, _lead_people(db, [lead])) | {"calls": _call_history(db, lead.id)}


@router.post("/calls/leads/{lead_id}/log")
def log_call(
    lead_id: uuid.UUID, body: CallIn, caller: Caller = Depends(requires("sales.calls.create")), db: DbSession = Depends(get_db)
) -> dict:
    lead = _get_lead(db, caller, lead_id, "sales.calls.create", "caller_team_id", open_pool=True)
    if lead.status not in OPEN_CALL_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "This lead isn't in the call queue any more.")
    now = _now()
    if body.outcome == "callback" and (body.callback_at is None or body.callback_at <= now):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick a future time for the callback.")
    if body.outcome == "meeting_booked" and (body.meeting is None or body.meeting.scheduled_at <= now - timedelta(hours=1)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Add the meeting's date and time.")
    if lead.caller_id is None:  # calling from the shared pool claims the lead
        lead.caller_id, lead.caller_team_id = caller.user.id, first_team(db, lead.organization_id, "sales_l1", caller.user.id)

    notes = (body.notes or "").strip() or None
    db.add(LeadCall(organization_id=lead.organization_id, lead_id=lead.id, caller_id=caller.user.id, outcome=body.outcome, notes=notes))
    lead.call_attempts += 1
    lead.last_called_at = now
    meeting = None
    if body.outcome in ("no_answer", "busy"):
        lead.status, lead.next_call_at = "contacted", now + timedelta(hours=3)
    elif body.outcome == "wrong_number":
        lead.status, lead.status_reason, lead.next_call_at = "disqualified", "Wrong number", None
    elif body.outcome == "not_interested":
        lead.status, lead.status_reason, lead.next_call_at = "not_interested", notes, None
    elif body.outcome in ("callback", "interested"):
        lead.status, lead.next_call_at = "callback", body.callback_at or now + timedelta(days=1)
    else:  # meeting_booked: hand over to Sales L2
        m = body.meeting
        if m is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick a date and time for the meeting.")
        closer_id, team_id = pick_least_loaded(db, lead.organization_id, "sales_l2", Meeting.closer_id, Meeting.status == "scheduled")
        meeting = Meeting(
            organization_id=lead.organization_id,
            lead_id=lead.id,
            scheduled_at=m.scheduled_at,
            duration_minutes=m.duration_minutes,
            mode=m.mode,
            link_or_location=(m.link_or_location or "").strip() or None,
            agenda=(m.agenda or "").strip() or notes,
            booked_by=caller.user.id,
            closer_id=closer_id,
            closer_team_id=team_id,
        )
        db.add(meeting)
        lead.status, lead.next_call_at, lead.closer_id, lead.closer_team_id = "meeting_booked", None, closer_id, team_id
    db.flush()
    record(db, caller.ctx, "sales.call_logged", "lead", lead.id, after={"outcome": body.outcome})
    if meeting is not None:
        record(db, caller.ctx, "sales.meeting_booked", "meeting", meeting.id, after={"lead_id": lead.id, "closer_id": meeting.closer_id})
    out = _lead_out(lead, _lead_people(db, [lead]))
    if meeting is not None:
        out["meeting_id"] = str(meeting.id)
    return out


# =====================================================================================
# Meetings (Sales L2)
# =====================================================================================
class RescheduleIn(BaseModel):
    scheduled_at: AwareDatetime
    link_or_location: str | None = Field(default=None, max_length=500)


class Requirement(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    details: str | None = Field(default=None, max_length=4000)
    priority: PRIORITIES = "normal"


class CompleteIn(BaseModel):
    outcome: Literal["won", "lost", "no_show"]
    notes: str | None = Field(default=None, max_length=4000)
    deal_value: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999.99"))
    project_name: str | None = Field(default=None, max_length=200)
    project_summary: str | None = Field(default=None, max_length=4000)
    requirements: list[Requirement] = Field(default_factory=list, max_length=50)


def _meetings_scope(caller: Caller):
    mine = scope_filter(caller, "sales.deals.view", [Meeting.closer_id], [Meeting.closer_team_id])
    pool = and_(Meeting.closer_id.is_(None), Meeting.status == "scheduled")
    return and_(Meeting.organization_id == caller.user.organization_id, or_(mine, pool))


def _meeting_out(m: Meeting, lead: Lead, people: dict) -> dict:
    return {
        "id": str(m.id),
        "scheduled_at": iso(m.scheduled_at),
        "duration_minutes": m.duration_minutes,
        "mode": m.mode,
        "link_or_location": m.link_or_location,
        "agenda": m.agenda,
        "status": m.status,
        "outcome": m.outcome,
        "outcome_notes": m.outcome_notes,
        "deal_value": float(m.deal_value) if m.deal_value is not None else None,
        "booked_by": person(people, m.booked_by),
        "closer": person(people, m.closer_id),
        "completed_at": iso(m.completed_at),
        "lead": {
            "id": str(lead.id),
            "contact_name": lead.contact_name,
            "company": lead.company,
            "phone": lead.phone,
            "email": lead.email,
            "city": lead.city,
            "industry": lead.industry,
            "website": lead.website,
            "notes": lead.notes,
        },
    }


def _get_meeting(db: DbSession, caller: Caller, meeting_id: uuid.UUID, permission: str) -> Meeting:
    m = db.get(Meeting, meeting_id)
    if m is None or m.organization_id != caller.user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    if m.closer_id is None and m.status == "scheduled":
        require(caller, permission)
        return m
    try:
        E.check(
            caller.subject,
            permission,
            E.RecordRef(
                organization_id=m.organization_id, team_id=m.closer_team_id, assignee_ids=frozenset({m.closer_id} if m.closer_id else set())
            ),
        )
    except E.Forbidden:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do that.") from None
    except E.NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
    return m


@router.get("/meetings")
def list_meetings(
    when: Literal["upcoming", "past"] = "upcoming", caller: Caller = Depends(requires("sales.deals.view")), db: DbSession = Depends(get_db)
) -> dict:
    q = select(Meeting, Lead).join(Lead, Lead.id == Meeting.lead_id).where(_meetings_scope(caller))
    q = (
        q.where(Meeting.status == "scheduled").order_by(Meeting.scheduled_at.asc())
        if when == "upcoming"
        else q.where(Meeting.status != "scheduled").order_by(Meeting.scheduled_at.desc())
    )
    rows = db.execute(q.limit(200)).all()
    people = names(db, [x for m, _ in rows for x in (m.booked_by, m.closer_id)])
    return {"items": [_meeting_out(m, lead, people) for m, lead in rows]}


@router.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: uuid.UUID, caller: Caller = Depends(requires("sales.deals.view")), db: DbSession = Depends(get_db)) -> dict:
    m = _get_meeting(db, caller, meeting_id, "sales.deals.view")
    lead = fetch(db, Lead, m.lead_id)
    out = _meeting_out(m, lead, names(db, [m.booked_by, m.closer_id])) | {"calls": _call_history(db, lead.id)}
    project = db.scalar(select(Project).where(Project.meeting_id == m.id))
    if project is not None:
        out["project"] = {
            "id": str(project.id),
            "name": project.name,
            "tickets": db.scalar(select(func.count()).select_from(Ticket).where(Ticket.project_id == project.id)),
        }
    return out


@router.post("/meetings/{meeting_id}/reschedule")
def reschedule_meeting(
    meeting_id: uuid.UUID, body: RescheduleIn, caller: Caller = Depends(requires("sales.deals.edit")), db: DbSession = Depends(get_db)
) -> dict:
    m = _get_meeting(db, caller, meeting_id, "sales.deals.edit")
    if m.status != "scheduled":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only upcoming meetings can be rescheduled.")
    before = iso(m.scheduled_at)
    m.scheduled_at = body.scheduled_at
    if body.link_or_location is not None:
        m.link_or_location = body.link_or_location.strip() or None
    if m.closer_id is None:
        m.closer_id, m.closer_team_id = caller.user.id, first_team(db, m.organization_id, "sales_l2", caller.user.id)
    db.flush()
    record(
        db,
        caller.ctx,
        "sales.meeting_rescheduled",
        "meeting",
        m.id,
        before={"scheduled_at": before},
        after={"scheduled_at": iso(m.scheduled_at)},
    )
    return _meeting_out(m, fetch(db, Lead, m.lead_id), names(db, [m.booked_by, m.closer_id]))


@router.post("/meetings/{meeting_id}/complete")
def complete_meeting(
    meeting_id: uuid.UUID, body: CompleteIn, caller: Caller = Depends(requires("sales.deals.edit")), db: DbSession = Depends(get_db)
) -> dict:
    m = _get_meeting(db, caller, meeting_id, "sales.deals.edit")
    if m.status != "scheduled":
        raise HTTPException(status.HTTP_409_CONFLICT, "This meeting has already been closed.")
    if body.outcome == "won" and not body.requirements:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Add at least one feature the client needs, so tech knows what to build."
        )
    lead = fetch(db, Lead, m.lead_id)
    now, notes = _now(), (body.notes or "").strip() or None
    if m.closer_id is None:
        m.closer_id, m.closer_team_id = caller.user.id, first_team(db, m.organization_id, "sales_l2", caller.user.id)
    m.outcome_notes, m.completed_at = notes, now
    result: dict = {"outcome": body.outcome}

    if body.outcome == "no_show":  # back to the caller's queue to rebook
        m.status = "no_show"
        lead.status, lead.next_call_at = "callback", now
    elif body.outcome == "lost":
        m.status, m.outcome = "completed", "lost"
        lead.status, lead.status_reason = "lost", notes
    else:
        m.status, m.outcome, m.deal_value = "completed", "won", body.deal_value
        lead.status = "won"
        client = Client(
            organization_id=m.organization_id,
            lead_id=lead.id,
            name=lead.company or lead.contact_name,
            contact_name=lead.contact_name,
            email=lead.email,
            phone=lead.phone,
            created_by=caller.user.id,
        )
        db.add(client)
        db.flush()
        project = Project(
            organization_id=m.organization_id,
            client_id=client.id,
            meeting_id=m.id,
            name=(body.project_name or "").strip() or f"{client.name} project",
            summary=(body.project_summary or "").strip() or notes,
            created_by=caller.user.id,
        )
        db.add(project)
        db.flush()
        tickets = create_tickets(db, caller, project, client, [r.model_dump() for r in body.requirements])
        result |= {"client_id": str(client.id), "project_id": str(project.id), "tickets": len(tickets)}
        record(db, caller.ctx, "work.project_created", "project", project.id, after={"client": client.name, "tickets": len(tickets)})
    db.flush()
    record(
        db,
        caller.ctx,
        "sales.meeting_completed",
        "meeting",
        m.id,
        after={"outcome": body.outcome, "deal_value": str(body.deal_value) if body.deal_value is not None else None},
    )
    return result
