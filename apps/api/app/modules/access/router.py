"""Super Admin control center: employees' accounts, invitations, roles and grants."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import record
from ...authz import engine as E
from ...authz.catalog import ACTIONS, RESOURCES, SCOPES
from ...core.db import get_db
from ...core.deps import Caller, requires
from ...core.models import Employee, Invitation, MfaFactor, Role, RoleGrant, Team, User, UserRole
from ...core.ratelimit import LIMITS, get_limiter
from ...core.security import new_token, token_hash
from ..identity.service import revoke_all_sessions

# Roles made for one person by "Give someone access" when their screens differ from their job.
PERSONAL_PREFIX = "person_"

router = APIRouter(prefix="/admin", tags=["admin"])


def _role_out(r: Role) -> dict:
    return {
        "id": str(r.id),
        "key": r.key,
        "name": r.name,
        "description": r.description,
        "is_system": r.is_system,
        "personal": r.key.startswith(PERSONAL_PREFIX),
        "grants": sorted(({"permission": g.permission, "scope": g.scope} for g in r.grants), key=lambda x: x["permission"]),
    }


def _user_out(u: User, roles: list[str]) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "full_name": u.full_name,
        "status": u.status,
        "is_super_admin": u.is_super_admin,
        "department_id": str(u.department_id) if u.department_id else None,
        "roles": roles,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


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
def list_users(
    status_: str | None = None, caller: Caller = Depends(requires("admin.users.view")), db: DbSession = Depends(get_db)
) -> list[dict]:
    q = select(User).where(User.organization_id == caller.user.organization_id).order_by(User.full_name, User.email)
    if status_ in ("active", "deactivated"):
        q = q.where(User.status == status_)
    users = db.scalars(q).all()
    roles = db.execute(
        select(UserRole.user_id, Role.key)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.organization_id == caller.user.organization_id)
    ).all()
    by_user: dict[uuid.UUID, list[str]] = {}
    for uid, key in roles:
        by_user.setdefault(uid, []).append(key)
    return [_user_out(u, sorted(by_user.get(u.id, []))) for u in users]


class InviteBody(BaseModel):
    email: EmailStr
    role_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    team_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    department_id: uuid.UUID | None = None
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
        raise _deny(exc) from exc
    for tid in body.team_ids:
        t = db.get(Team, tid)
        if t is None or t.organization_id != org:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found.")
    db.execute(
        update(Invitation)
        .where(
            Invitation.organization_id == org, Invitation.email == email, Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None)
        )
        .values(revoked_at=datetime.now(UTC))
    )
    raw = new_token()
    inv = Invitation(
        organization_id=org,
        email=email,
        role_ids=[r.id for r in roles],
        team_ids=body.team_ids,
        department_id=body.department_id,
        token_hash=token_hash(raw),
        invited_by=caller.user.id,
        expires_at=datetime.now(UTC) + timedelta(days=body.expires_in_days),
    )
    db.add(inv)
    db.flush()
    record(db, caller.ctx, "admin.user_invited", "invitation", inv.id, after={"email": email, "roles": [r.key for r in roles]})
    # The link is shown once to the admin (and emailed by the worker in Milestone 2).
    return {"id": str(inv.id), "email": email, "accept_path": f"/sign-in?invite={raw}", "expires_at": inv.expires_at.isoformat()}


class UserPatch(BaseModel):
    status: Literal["active", "deactivated"] | None = None
    department_id: uuid.UUID | None = None
    full_name: str | None = Field(default=None, max_length=200)
    reassign_to: uuid.UUID | None = None  # who takes over their teams and reports when deactivated


@router.patch("/users/{user_id}")
def update_user(
    user_id: uuid.UUID, body: UserPatch, caller: Caller = Depends(requires("admin.users.edit")), db: DbSession = Depends(get_db)
) -> dict:
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
        u.status, u.deactivated_at = "deactivated", datetime.now(UTC)
        ended = revoke_all_sessions(db, u.id)
        record(
            db,
            caller.ctx,
            "admin.user_deactivated",
            "user",
            u.id,
            before=before,
            after={"sessions_ended": ended, "reassigned_to": str(body.reassign_to) if body.reassign_to else None},
        )
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
def set_user_roles(
    user_id: uuid.UUID, body: RolesBody, caller: Caller = Depends(requires("admin.roles.manage")), db: DbSession = Depends(get_db)
) -> dict:
    u = _get_user(db, caller, user_id)
    roles = [_get_role(db, caller, rid) for rid in body.role_ids]
    try:
        E.check_role_assignment(caller.subject, u.id, [E.Grant(g.permission, g.scope) for r in roles for g in r.grants])
    except E.EscalationDenied as exc:
        raise _deny(exc) from exc
    before = sorted(db.scalars(select(Role.key).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == u.id)).all())
    db.execute(delete(UserRole).where(UserRole.user_id == u.id))
    for r in roles:
        db.add(UserRole(user_id=u.id, role_id=r.id, organization_id=u.organization_id, granted_by=caller.user.id))
    record(
        db, caller.ctx, "admin.user_roles_changed", "user", u.id, before={"roles": before}, after={"roles": sorted(r.key for r in roles)}
    )
    return {"roles": sorted(r.key for r in roles)}


class SuperAdminBody(BaseModel):
    is_super_admin: bool


@router.put("/users/{user_id}/super-admin")
def set_super_admin(
    user_id: uuid.UUID, body: SuperAdminBody, caller: Caller = Depends(requires("admin.users.manage")), db: DbSession = Depends(get_db)
) -> dict:
    u = _get_user(db, caller, user_id)
    count = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.organization_id == u.organization_id, User.is_super_admin, User.status == "active")
        )
        or 0
    )
    try:
        E.check_super_admin_change(caller.subject, u.id, body.is_super_admin, count)
    except E.EscalationDenied as exc:
        raise _deny(exc) from exc
    before = u.is_super_admin
    u.is_super_admin = body.is_super_admin
    if body.is_super_admin:
        u.mfa_required = True
    revoke_all_sessions(db, u.id)  # new access level takes effect at next sign-in, with MFA
    record(
        db,
        caller.ctx,
        "admin.super_admin_changed",
        "user",
        u.id,
        before={"is_super_admin": before},
        after={"is_super_admin": u.is_super_admin},
    )
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
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get("/roles")
def list_roles(caller: Caller = Depends(requires("admin.roles.view")), db: DbSession = Depends(get_db)) -> list[dict]:
    return [
        _role_out(r) for r in db.scalars(select(Role).where(Role.organization_id == caller.user.organization_id).order_by(Role.name)).all()
    ]


@router.post("/roles", status_code=201)
def create_role(body: RoleIn, caller: Caller = Depends(requires("admin.roles.manage")), db: DbSession = Depends(get_db)) -> dict:
    grants = _grants(body.grants)
    try:
        E.check_role_edit(caller.subject, grants, actor_holds_role=False)
    except E.EscalationDenied as exc:
        raise _deny(exc) from exc
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
def replace_role(
    role_id: uuid.UUID, body: RoleIn, caller: Caller = Depends(requires("admin.roles.manage")), db: DbSession = Depends(get_db)
) -> dict:
    role = _get_role(db, caller, role_id)
    holds = db.scalar(select(UserRole.user_id).where(UserRole.user_id == caller.user.id, UserRole.role_id == role.id)) is not None
    grants = _grants(body.grants)
    try:
        E.check_role_edit(caller.subject, grants, actor_holds_role=holds)
    except E.EscalationDenied as exc:
        raise _deny(exc) from exc
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
        raise _deny(exc) from exc
    holders = db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id)) or 0
    if holders:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{holders} people still hold this role. Move them first.")
    before = _role_out(role)
    db.delete(role)
    record(db, caller.ctx, "admin.role_deleted", "role", role_id, before=before)
    return {"ok": True}
