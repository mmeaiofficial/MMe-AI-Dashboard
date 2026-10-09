"""Give people access by email: one job (role), one team, and the screens they can open.

- If the email already has an account, their job and team change right away.
- Otherwise an invitation is stored; the person gets exactly this access the first time they sign in
  with Google using that email (no link needed, though one is returned to share).
- When the chosen screens differ from the job's defaults, a personal role (key ``person_…``) is made for
  that one person, so editing their access never changes anyone else's. Unused personal roles are removed.
The usual guards apply: you can't change your own access, and you can't give more than you hold.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import record
from ...authz import engine as E
from ...authz.catalog import RESOURCES
from ...core.db import get_db
from ...core.deps import Caller, requires
from ...core.models import Invitation, Role, RoleGrant, Team, TeamMember, User, UserRole
from ...core.ratelimit import LIMITS, get_limiter
from ...core.security import new_token, token_hash
from .router import PERSONAL_PREFIX

router = APIRouter(prefix="/admin", tags=["admin"])

RANK = {"own": 0, "team": 1, "department": 2, "all": 3}
# Action sets the UI names; anything else is shown as a custom mix.
LEVELS = {
    frozenset({"view"}): "view",
    frozenset({"view", "create"}): "add",
    frozenset({"view", "create", "edit"}): "edit",
    frozenset({"manage"}): "full",
}


def _features(grants: list[tuple[str, str]]) -> list[dict]:
    """Plain summary per area: level (view / edit / full / custom) and the widest reach."""
    by_res: dict[str, dict[str, str]] = {}
    for perm, scope in grants:
        res, action = perm.rsplit(".", 1)
        by_res.setdefault(res, {})[action] = scope
    out = []
    for res in RESOURCES:
        acts = by_res.get(res)
        if not acts:
            continue
        held = set(acts)
        level = LEVELS.get(frozenset(held), "custom")
        out.append({"resource": res, "level": level, "reach": max(acts.values(), key=RANK.__getitem__)})
    return out


def _role_grants(db: DbSession, role_ids: list[uuid.UUID]) -> list[tuple[str, str]]:
    if not role_ids:
        return []
    return list(db.execute(select(RoleGrant.permission, RoleGrant.scope).where(RoleGrant.role_id.in_(role_ids))).tuples().all())


@router.get("/access")
def list_access(caller: Caller = Depends(requires("admin.users.view")), db: DbSession = Depends(get_db)) -> dict:
    org = caller.user.organization_id
    roles = {r.id: r for r in db.scalars(select(Role).where(Role.organization_id == org))}
    teams = {t.id: t for t in db.scalars(select(Team).where(Team.organization_id == org, Team.deleted_at.is_(None)))}
    held: dict[uuid.UUID, list[uuid.UUID]] = {}
    for uid, rid in db.execute(select(UserRole.user_id, UserRole.role_id).where(UserRole.organization_id == org)).all():
        held.setdefault(uid, []).append(rid)
    member: dict[uuid.UUID, list[dict]] = {}
    for tid, uid, mgr in db.execute(
        select(TeamMember.team_id, TeamMember.user_id, TeamMember.is_manager).where(TeamMember.organization_id == org)
    ):
        if tid in teams:
            member.setdefault(uid, []).append({"id": str(tid), "name": teams[tid].name, "kind": teams[tid].kind, "is_manager": mgr})

    def role_info(rids: list[uuid.UUID]) -> list[dict]:
        return [
            {"id": str(r.id), "key": r.key, "name": r.name, "personal": r.key.startswith(PERSONAL_PREFIX)}
            for r in (roles.get(x) for x in rids)
            if r
        ]

    people = []
    for u in db.scalars(select(User).where(User.organization_id == org).order_by(User.full_name, User.email)):
        rids = held.get(u.id, [])
        people.append(
            {
                "kind": "user",
                "id": str(u.id),
                "email": u.email,
                "name": u.full_name,
                "status": u.status,
                "is_super_admin": u.is_super_admin,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "roles": role_info(rids),
                "teams": member.get(u.id, []),
                "features": _features(_role_grants(db, rids)),
            }
        )
    now = datetime.now(UTC)
    invites = db.scalars(
        select(Invitation)
        .where(
            Invitation.organization_id == org,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at > now,
        )
        .order_by(Invitation.created_at.desc())
    ).all()
    for inv in invites:
        managed = set(inv.manager_team_ids or [])
        people.append(
            {
                "kind": "invite",
                "id": str(inv.id),
                "email": inv.email,
                "name": "",
                "status": "invited",
                "is_super_admin": False,
                "expires_at": inv.expires_at.isoformat(),
                "roles": role_info(list(inv.role_ids or [])),
                "teams": [
                    {"id": str(t), "name": teams[t].name, "kind": teams[t].kind, "is_manager": t in managed}
                    for t in inv.team_ids or []
                    if t in teams
                ],
                "features": _features(_role_grants(db, list(inv.role_ids or []))),
            }
        )
    return {"people": people}


class GrantIn(BaseModel):
    permission: str
    scope: Literal["own", "team", "department", "all"]


class AllocateIn(BaseModel):
    email: EmailStr
    role_id: uuid.UUID
    grants: list[GrantIn] | None = Field(default=None, max_length=200)  # None = exactly the job's screens
    team_id: uuid.UUID | None = None
    team_manager: bool = False


def _prune_personal_roles(db: DbSession, org: uuid.UUID) -> None:
    """Delete personal roles nobody holds and no open invitation will hand out."""
    personal = db.scalars(select(Role.id).where(Role.organization_id == org, Role.key.startswith(PERSONAL_PREFIX))).all()
    if not personal:
        return
    used = set(db.scalars(select(UserRole.role_id).where(UserRole.role_id.in_(personal))).all())
    open_invites = db.scalars(
        select(Invitation.role_ids).where(
            Invitation.organization_id == org, Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None)
        )
    ).all()
    used |= {rid for ids in open_invites for rid in ids or []}
    unused = [rid for rid in personal if rid not in used]
    if unused:
        db.execute(delete(Role).where(Role.id.in_(unused)))


def _require_invite(caller: Caller) -> None:
    """Inviting a new person also needs the invite permission, not just role management."""
    try:
        E.require(caller.subject, "admin.users.create")
    except E.Forbidden:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can change existing people's access, but not invite new people.") from None


@router.post("/access")
def allocate(body: AllocateIn, caller: Caller = Depends(requires("admin.roles.manage")), db: DbSession = Depends(get_db)) -> dict:
    org = caller.user.organization_id
    email = body.email.lower()
    job = db.get(Role, body.role_id)
    if job is None or job.organization_id != org or job.key.startswith(PERSONAL_PREFIX):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    team = None
    if body.team_id:
        team = db.get(Team, body.team_id)
        if team is None or team.organization_id != org or team.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found.")
    if body.team_manager and team is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick the team they manage.")

    job_grants = {(g.permission, g.scope) for g in job.grants}
    chosen = {(g.permission, g.scope) for g in body.grants} if body.grants is not None else job_grants
    try:
        grants = [E.Grant(p, s) for p, s in sorted(chosen)]
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    if len({g.permission for g in grants}) != len(grants):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Each permission can have only one reach.")

    user = db.scalar(select(User).where(User.organization_id == org, User.email == email))
    if user is not None and user.is_super_admin and not caller.subject.is_super_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a Super Admin can change a Super Admin's access.")
    try:  # no changing your own access, no giving more than you hold
        E.check_role_assignment(caller.subject, user.id if user else uuid.uuid4(), grants)
    except E.EscalationDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    if user is None:
        _require_invite(caller)

    custom = {(g.permission, g.scope) for g in grants} != job_grants
    role = job
    if custom:
        role = Role(
            organization_id=org,
            key=f"{PERSONAL_PREFIX}{uuid.uuid4().hex[:12]}",
            name=f"{job.name} (custom)",
            description=f"Personal access for {email}, based on {job.name}.",
        )
        db.add(role)
        db.flush()
        for g in grants:
            db.add(RoleGrant(role_id=role.id, organization_id=org, permission=g.permission, scope=g.scope))

    summary = {
        "email": email,
        "job": job.key,
        "custom": custom,
        "team": team.name if team else None,
        "team_manager": body.team_manager,
        "grants": sorted(f"{g.permission}:{g.scope}" for g in grants) if custom else None,
    }
    if user is not None:
        before = sorted(db.scalars(select(Role.key).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)).all())
        db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        db.add(UserRole(user_id=user.id, role_id=role.id, organization_id=org, granted_by=caller.user.id))
        if team is not None:
            m = db.get(TeamMember, (team.id, user.id))
            if m is None:
                db.add(TeamMember(team_id=team.id, user_id=user.id, organization_id=org, is_manager=body.team_manager))
            else:
                m.is_manager = body.team_manager
        db.flush()
        _prune_personal_roles(db, org)
        record(db, caller.ctx, "admin.access_changed", "user", user.id, before={"roles": before}, after=summary)
        return {"result": "updated", "email": email, "role": role.name}

    limit, window = LIMITS["invite_user"]
    if not get_limiter().hit(f"invite_user:{caller.user.id}", limit, window):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many invitations this hour.")
    now = datetime.now(UTC)
    db.execute(
        update(Invitation)
        .where(
            Invitation.organization_id == org, Invitation.email == email, Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None)
        )
        .values(revoked_at=now)
    )
    raw = new_token()
    inv = Invitation(
        organization_id=org,
        email=email,
        role_ids=[role.id],
        team_ids=[team.id] if team else [],
        manager_team_ids=[team.id] if team and body.team_manager else [],
        token_hash=token_hash(raw),
        invited_by=caller.user.id,
        expires_at=now + timedelta(days=30),
    )
    db.add(inv)
    db.flush()
    _prune_personal_roles(db, org)
    record(db, caller.ctx, "admin.user_invited", "invitation", inv.id, after=summary)
    return {
        "result": "invited",
        "email": email,
        "role": role.name,
        "accept_path": f"/sign-in?invite={raw}",
        "expires_at": inv.expires_at.isoformat(),
    }


@router.post("/access/invitations/{invitation_id}/revoke")
def revoke_invitation(
    invitation_id: uuid.UUID, caller: Caller = Depends(requires("admin.users.create")), db: DbSession = Depends(get_db)
) -> dict:
    inv = db.get(Invitation, invitation_id)
    if inv is None or inv.organization_id != caller.user.organization_id or inv.accepted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    if inv.revoked_at is None:
        inv.revoked_at = datetime.now(UTC)
        db.flush()
        _prune_personal_roles(db, inv.organization_id)
        record(db, caller.ctx, "admin.invitation_revoked", "invitation", inv.id, after={"email": inv.email})
    return {"ok": True}
