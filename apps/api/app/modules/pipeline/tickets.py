"""Tickets for the tech team: one per feature a client confirmed in a won meeting.

A ticket carries everything tech needs: the feature, the client and their contact, the project summary,
and the Sales L2 meeting notes. Tickets land in the tech team's queue unassigned; anyone on the team can
take one, move it across To do -> In progress -> Review -> Done, and leave notes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import record
from ...authz import engine as E
from ...core.db import get_db
from ...core.deps import Caller, requires
from ...core.models import Client, Lead, Meeting, Project, TeamMember, Ticket, TicketNote, User
from .common import first_team, iso, names, person, scope_filter

router = APIRouter(tags=["tickets"])

STATUSES = Literal["todo", "in_progress", "review", "done"]
PRIORITIES = Literal["low", "normal", "high", "urgent"]


def create_tickets(db: DbSession, caller: Caller, project: Project, client: Client, requirements: list[dict]) -> list[Ticket]:
    """One ticket per confirmed feature, numbered per organization, queued for the tech team."""
    org = project.organization_id
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"tickets:{org}"})  # serialize numbering
    start = (db.scalar(select(func.max(Ticket.number)).where(Ticket.organization_id == org)) or 0) + 1
    team = first_team(db, org, "tech")
    out = []
    for i, r in enumerate(requirements):
        t = Ticket(
            organization_id=org,
            number=start + i,
            project_id=project.id,
            client_id=client.id,
            title=r["title"].strip(),
            description=(r.get("details") or "").strip() or None,
            priority=r.get("priority") or "normal",
            team_id=team,
            created_by=caller.user.id,
        )
        db.add(t)
        out.append(t)
    db.flush()
    return out


def _ticket_out(t: Ticket, project: Project, client: Client, people: dict) -> dict:
    return {
        "id": str(t.id),
        "number": t.number,
        "title": t.title,
        "description": t.description,
        "priority": t.priority,
        "status": t.status,
        "assignee": person(people, t.assignee_id),
        "created_by": person(people, t.created_by),
        "due_on": iso(t.due_on),
        "done_at": iso(t.done_at),
        "created_at": iso(t.created_at),
        "updated_at": iso(t.updated_at),
        "project": {"id": str(project.id), "name": project.name},
        "client": {"id": str(client.id), "name": client.name},
    }


def _scope(caller: Caller):
    return and_(
        Ticket.organization_id == caller.user.organization_id,
        scope_filter(caller, "work.tasks.view", [Ticket.assignee_id, Ticket.created_by], [Ticket.team_id]),
    )


def _get_ticket(db: DbSession, caller: Caller, ticket_id: uuid.UUID, permission: str) -> Ticket:
    t = db.get(Ticket, ticket_id)
    if t is None or t.organization_id != caller.user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    ref = E.RecordRef(
        organization_id=t.organization_id,
        owner_id=t.created_by,
        team_id=t.team_id,
        assignee_ids=frozenset({t.assignee_id} if t.assignee_id else set()),
    )
    try:
        E.check(caller.subject, permission, ref)
    except E.Forbidden:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do that.") from None
    except E.NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
    return t


@router.get("/tickets")
def list_tickets(
    mine: bool = False,
    project_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, max_length=120),
    caller: Caller = Depends(requires("work.tasks.view")),
    db: DbSession = Depends(get_db),
) -> dict:
    query = (
        select(Ticket, Project, Client)
        .join(Project, Project.id == Ticket.project_id)
        .join(Client, Client.id == Ticket.client_id)
        .where(_scope(caller))
    )
    if mine:
        query = query.where(Ticket.assignee_id == caller.user.id)
    if project_id:
        query = query.where(Ticket.project_id == project_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(Ticket.title.ilike(like), Client.name.ilike(like), Project.name.ilike(like)))
    rows = db.execute(query.order_by(Ticket.number.desc()).limit(500)).all()
    people = names(db, [x for t, _, _ in rows for x in (t.assignee_id, t.created_by)])
    return {"items": [_ticket_out(t, p, c, people) for t, p, c in rows]}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: uuid.UUID, caller: Caller = Depends(requires("work.tasks.view")), db: DbSession = Depends(get_db)) -> dict:
    t = _get_ticket(db, caller, ticket_id, "work.tasks.view")
    project, client = db.get(Project, t.project_id), db.get(Client, t.client_id)
    meeting = db.get(Meeting, project.meeting_id) if project.meeting_id else None
    lead = db.get(Lead, client.lead_id) if client.lead_id else None
    notes = db.scalars(select(TicketNote).where(TicketNote.ticket_id == t.id).order_by(TicketNote.created_at)).all()
    team_ids = [t.team_id] if t.team_id else []
    teammates = (
        db.execute(
            select(User.id, User.full_name, User.email)
            .join(TeamMember, TeamMember.user_id == User.id)
            .where(TeamMember.team_id.in_(team_ids), User.status == "active")
            .order_by(User.full_name)
        ).all()
        if team_ids
        else []
    )
    people = names(db, [t.assignee_id, t.created_by, *(n.author_id for n in notes), meeting.closer_id if meeting else None])
    out = _ticket_out(t, project, client, people)
    out["project"] |= {
        "summary": project.summary,
        "status": project.status,
        "tickets": db.scalar(select(func.count()).select_from(Ticket).where(Ticket.project_id == project.id)),
    }
    out["client"] |= {
        "contact_name": client.contact_name,
        "email": client.email,
        "phone": client.phone,
        "website": lead.website if lead else None,
        "industry": lead.industry if lead else None,
        "city": lead.city if lead else None,
    }
    out["meeting"] = (
        {
            "scheduled_at": iso(meeting.scheduled_at),
            "closer": person(people, meeting.closer_id),
            "agenda": meeting.agenda,
            "outcome_notes": meeting.outcome_notes,
        }
        if meeting
        else None
    )
    out["notes"] = [{"id": str(n.id), "body": n.body, "at": iso(n.created_at), "by": person(people, n.author_id)} for n in notes]
    out["teammates"] = [{"id": str(i), "name": n or e} for i, n, e in teammates]
    return out


class TicketPatch(BaseModel):
    status: STATUSES | None = None
    priority: PRIORITIES | None = None
    due_on: date | None = None
    assignee_id: uuid.UUID | None = None


@router.patch("/tickets/{ticket_id}")
def update_ticket(
    ticket_id: uuid.UUID, body: TicketPatch, caller: Caller = Depends(requires("work.tasks.edit")), db: DbSession = Depends(get_db)
) -> dict:
    t = _get_ticket(db, caller, ticket_id, "work.tasks.edit")
    fields = body.model_dump(exclude_unset=True)
    before = {k: iso(getattr(t, k)) if isinstance(getattr(t, k), date | datetime) else getattr(t, k) for k in fields}
    if "assignee_id" in fields and body.assignee_id is not None and body.assignee_id != caller.user.id:
        on_team = t.team_id is not None and db.get(TeamMember, (t.team_id, body.assignee_id)) is not None
        target = db.get(User, body.assignee_id)
        if not on_team or target is None or target.status != "active":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tickets can be given to people on the ticket's team.")
    for k, v in fields.items():
        setattr(t, k, v)
    if "status" in fields:
        t.done_at = datetime.now(UTC) if t.status == "done" else None
    db.flush()
    db.refresh(t)
    record(db, caller.ctx, "work.ticket_updated", "ticket", t.id, before=before, after=fields)
    people = names(db, [t.assignee_id, t.created_by])
    return _ticket_out(t, db.get(Project, t.project_id), db.get(Client, t.client_id), people)


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@router.post("/tickets/{ticket_id}/notes", status_code=201)
def add_note(
    ticket_id: uuid.UUID, body: NoteIn, caller: Caller = Depends(requires("work.tasks.edit")), db: DbSession = Depends(get_db)
) -> dict:
    t = _get_ticket(db, caller, ticket_id, "work.tasks.edit")
    n = TicketNote(organization_id=t.organization_id, ticket_id=t.id, author_id=caller.user.id, body=body.body.strip())
    db.add(n)
    db.flush()
    record(db, caller.ctx, "work.ticket_noted", "ticket", t.id)
    return {"id": str(n.id), "body": n.body, "at": iso(n.created_at), "by": names(db, [caller.user.id]).get(caller.user.id)}
