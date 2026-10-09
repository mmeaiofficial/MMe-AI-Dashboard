"""Rekha's tools: read-only views of MME OS data, each gated by the caller's own permissions.

Every tool calls the same functions the API routes use, after the same permission check, so Rekha
can never show someone more than they could open themselves. Out-of-scope records look absent.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from anthropic.types.beta import BetaToolParam
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ...authz import engine as E
from ...authz.catalog import ALL_PERMISSIONS, RESOURCES
from ...core.deps import Caller
from ...core.models import AuditEvent, Role, Team, TeamMember, User, UserRole
from ..access.router import list_roles as _list_roles
from ..org.router import _teams_in_scope
from ..org.router import get_team as _get_team
from ..org.router import list_employees as _list_employees

MAX_ROWS = 50


class ToolError(Exception):
    """Shown to the model as an error tool_result; the message must be safe to repeat to the user."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    permission: str | None
    run: Callable[[Caller, DbSession, dict], Any]

    def spec(self) -> BetaToolParam:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


def _str(args: dict, key: str, max_len: int = 120) -> str:
    v = args.get(key)
    return v.strip()[:max_len] if isinstance(v, str) else ""


def _int(args: dict, key: str, default: int, lo: int, hi: int) -> int:
    v = args.get(key)
    return max(lo, min(hi, v)) if isinstance(v, int) and not isinstance(v, bool) else default


# ---------- tool bodies ----------
def my_profile(caller: Caller, db: DbSession, _: dict) -> dict:
    u, subj = caller.user, caller.subject
    roles = db.scalars(select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == u.id)).all()
    teams = db.execute(select(Team.name, TeamMember.is_manager).join(TeamMember, TeamMember.team_id == Team.id)
                       .where(TeamMember.user_id == u.id).order_by(Team.name)).all()
    access: dict[str, str] = {}
    for perm in sorted(ALL_PERMISSIONS):
        scope = E.scope_for(subj, perm)
        if scope:
            res = perm.rsplit(".", 1)[0]
            if E.RANK[scope] > E.RANK.get(access.get(res, ""), -1):
                access[res] = scope
    return {
        "name": u.full_name or u.email, "email": u.email, "is_super_admin": u.is_super_admin, "roles": list(roles),
        "teams": [{"name": n, "is_manager": m} for n, m in teams],
        "access": [{"area": RESOURCES[r], "widest_scope": s} for r, s in access.items()],
    }


def search_people(caller: Caller, db: DbSession, args: dict) -> dict:
    q = _str(args, "query").lower()
    rows = _list_employees(caller=caller, db=db)
    if q:
        rows = [r for r in rows if q in " ".join(str(r.get(k) or "") for k in ("full_name", "email", "designation", "location")).lower()]
    keep = ("full_name", "email", "designation", "employment_type", "location", "status", "joined_on")
    return {"total": len(rows), "people": [{k: r[k] for k in keep} for r in rows[:MAX_ROWS]]}


def list_teams(caller: Caller, db: DbSession, _: dict) -> dict:
    teams = db.scalars(_teams_in_scope(caller, "org.teams.view").order_by(Team.name)).all()
    counts = dict(db.execute(select(TeamMember.team_id, func.count()).where(TeamMember.team_id.in_([t.id for t in teams]))
                             .group_by(TeamMember.team_id)).tuples().all()) if teams else {}
    return {"teams": [{"name": t.name, "kind": t.kind, "members": counts.get(t.id, 0)} for t in teams]}


def team_members(caller: Caller, db: DbSession, args: dict) -> dict:
    name = _str(args, "team_name").lower()
    if not name:
        raise ToolError("Give the team's name.")
    teams = db.scalars(_teams_in_scope(caller, "org.teams.view")).all()
    match = [t for t in teams if t.name.lower() == name] or [t for t in teams if name in t.name.lower()]
    if not match:
        raise ToolError(f"No team named '{args.get('team_name')}' that this person can see.")
    if len(match) > 1:
        raise ToolError("Several teams match: " + ", ".join(t.name for t in match) + ". Ask which one.")
    t = _get_team(team_id=match[0].id, caller=caller, db=db)
    return {"team": t["name"], "kind": t["kind"],
            "members": [{"name": m["full_name"] or m["email"], "email": m["email"], "is_manager": m["is_manager"]} for m in t["members"]]}


CATEGORY_PREFIX = {"sign_in": "auth.", "access": "admin.", "organization": "org.", "assistant": "ai."}


def recent_activity(caller: Caller, db: DbSession, args: dict) -> dict:
    days = _int(args, "days", 7, 1, 90)
    category = _str(args, "category")
    q = select(AuditEvent, User.full_name, User.email).outerjoin(User, User.id == AuditEvent.actor_user_id).where(
        AuditEvent.organization_id == caller.user.organization_id,
        AuditEvent.created_at >= datetime.now(UTC) - timedelta(days=days))
    if category in CATEGORY_PREFIX:
        q = q.where(AuditEvent.action.startswith(CATEGORY_PREFIX[category]))
    rows = db.execute(q.order_by(AuditEvent.id.desc()).limit(MAX_ROWS)).all()
    return {"days": days, "shown": len(rows), "events": [
        {"when": e.created_at.isoformat(timespec="minutes"), "action": e.action, "by": name or email or "system",
         "target": f"{e.target_type}" if e.target_type else None} for e, name, email in rows]}


def list_roles(caller: Caller, db: DbSession, _: dict) -> dict:
    holders = dict(db.execute(select(UserRole.role_id, func.count()).where(UserRole.organization_id == caller.user.organization_id)
                              .group_by(UserRole.role_id)).tuples().all())
    roles = _list_roles(caller=caller, db=db)
    return {"roles": [{"name": r["name"], "people": holders.get(uuid.UUID(r["id"]), 0), "grants": len(r["grants"])} for r in roles]}


NO_ARGS = {"type": "object", "properties": {}, "additionalProperties": False}

def _obj(props: dict, required: tuple[str, ...] = ()) -> dict:
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


TOOLS: list[Tool] = [
    Tool("get_my_profile",
         "The signed-in person's own profile: name, roles, teams (and whether they manage them), "
         "and which areas of MME OS they can access and how widely.",
         NO_ARGS, None, my_profile),
    Tool("search_people",
         "Search employee profiles the person is allowed to see (name, email, designation, employment type "
         "such as intern, location, status). Leave query empty to list everyone in scope.",
         _obj({"query": {"type": "string", "description": "Text to match in name, email, designation or location"}}),
         "org.employees.view", search_people),
    Tool("list_teams", "List the teams the person can see, with type and member count.", NO_ARGS, "org.teams.view", list_teams),
    Tool("get_team_members", "Members of one team, including who manages it.",
         _obj({"team_name": {"type": "string", "description": "The team's name, e.g. 'Sales L1'"}}, ("team_name",)),
         "org.teams.view", team_members),
    Tool("recent_activity", "Audit log events: sign-ins, access and role changes, team and profile changes, newest first (max 50).",
         {"type": "object", "properties": {
             "days": {"type": "integer", "description": "How many days back, 1-90. Default 7."},
             "category": {"type": "string", "enum": ["all", "sign_in", "access", "organization", "assistant"]}},
          "additionalProperties": False},
         "audit.events.view", recent_activity),
    Tool("list_roles", "The organization's roles, how many people hold each, and how many permission grants each has.",
         NO_ARGS, "admin.roles.view", list_roles),
]
BY_NAME = {t.name: t for t in TOOLS}


def run_tool(caller: Caller, db: DbSession, name: str, args: Any) -> tuple[str, bool]:
    """Returns (JSON or message for the model, is_error)."""
    tool = BY_NAME.get(name)
    if tool is None:
        return f"Unknown tool {name}.", True
    if not isinstance(args, dict):
        return "Tool input must be an object.", True
    if tool.permission:
        try:
            E.require(caller.subject, tool.permission)
        except E.Forbidden:
            return "This person doesn't have access to that information.", True
    try:
        return json.dumps(tool.run(caller, db, args), default=str), False
    except ToolError as exc:
        return str(exc), True
    except (HTTPException, E.NotFound):
        return "Not found, or outside what this person can see.", True
