"""Shared pieces for the pipeline modules: data-scope filters, auto-assignment and display names."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, false, func, or_, select, true
from sqlalchemy.orm import Session as DbSession

from ...authz import engine as E
from ...core.deps import Caller
from ...core.models import Team, TeamMember, User

OPEN_CALL_STATUSES = ("qualified", "contacted", "callback")

T = TypeVar("T")


def scope_filter(caller: Caller, permission: str, owner_cols: list, team_cols: list) -> ColumnElement[bool]:
    """SQL condition for the records ``caller`` may see under ``permission``.

    ``owner_cols`` are user columns that make a record "theirs" (creator, assignee); ``team_cols`` are the
    team columns that place a record in a team for "team" scope. Raises Forbidden if the permission is missing.
    """
    c = E.criteria(caller.subject, permission)
    if c.all_records:
        return true()
    conds = [col.in_(c.user_ids) for col in owner_cols]
    if c.team_ids:
        conds += [col.in_(c.team_ids) for col in team_cols]
    if c.department_ids:
        dept_users = select(User.id).where(User.department_id.in_(c.department_ids))
        conds += [col.in_(dept_users) for col in owner_cols]
    return or_(*conds) if conds else false()


def fetch(db: DbSession, model: type[T], row_id: uuid.UUID) -> T:
    """A row another record points to (a ticket's project, a meeting's lead); 404 if it has gone."""
    obj = db.get(model, row_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return obj


def require(caller: Caller, permission: str) -> None:
    try:
        E.require(caller.subject, permission)
    except E.Forbidden:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do that.") from None


def first_team(db: DbSession, org_id: uuid.UUID, kind: str, user_id: uuid.UUID | None = None) -> uuid.UUID | None:
    """The team of ``kind`` that ``user_id`` belongs to (or the organization's first such team)."""
    q = select(Team.id).where(Team.organization_id == org_id, Team.kind == kind, Team.deleted_at.is_(None))
    if user_id is not None:
        q = q.join(TeamMember, TeamMember.team_id == Team.id).where(TeamMember.user_id == user_id)
    return db.scalar(q.order_by(Team.name).limit(1))


def pick_least_loaded(db: DbSession, org_id: uuid.UUID, kind: str, load_col, load_where) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Active member of a ``kind`` team with the fewest open items, as (user_id, team_id); (None, None) if nobody.

    ``load_col`` is the assignee column on the work table and ``load_where`` the condition for "open" work.
    """
    members = db.execute(
        select(TeamMember.user_id, TeamMember.team_id)
        .join(Team, Team.id == TeamMember.team_id)
        .join(User, User.id == TeamMember.user_id)
        .where(Team.organization_id == org_id, Team.kind == kind, Team.deleted_at.is_(None), User.status == "active")
        .order_by(Team.name)
    ).all()
    if not members:
        return None, None
    ids = list({u for u, _ in members})
    loads = dict(db.execute(select(load_col, func.count()).where(load_col.in_(ids), load_where).group_by(load_col)).tuples().all())
    user_id, team_id = min(members, key=lambda m: (loads.get(m[0], 0), str(m[0])))
    return user_id, team_id


def names(db: DbSession, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, dict]:
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    rows = db.execute(select(User.id, User.full_name, User.email).where(User.id.in_(wanted))).all()
    return {i: {"id": str(i), "name": n or e} for i, n, e in rows}


def person(people: dict, user_id: uuid.UUID | None) -> dict | None:
    return people.get(user_id) if user_id else None


def iso(v) -> str | None:
    return v.isoformat() if v is not None else None
