"""Request dependencies: who is calling, what they may do, and the per-route permission check.

Every route must declare its access with exactly one of:
    Depends(requires("module.resource.action"))   -> signed-in, MFA-satisfied, holding the permission
    Depends(signed_in)                             -> any signed-in user (e.g. /me)
    public_route(...)                              -> no session (sign-in endpoints, health)
tests/api/test_route_permissions.py fails the build if a route declares none.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..audit.writer import RequestContext
from ..authz import engine as E
from .config import load_settings
from .db import get_db
from .models import RoleGrant, Session, TeamMember, User, UserRole
from .security import token_hash, verify_csrf

SESSION_COOKIE = "mme_session"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

settings = load_settings()

# route path+method -> declared access ("public", "signed_in" or a permission string)
ROUTE_ACCESS: dict[str, str] = {}


@dataclass
class Caller:
    user: User
    session: Session
    subject: E.Subject
    ctx: RequestContext
    raw_token: str


def _ctx(request: Request, org_id: uuid.UUID, user_id: Optional[uuid.UUID]) -> RequestContext:
    return RequestContext(organization_id=org_id, actor_user_id=user_id,
                          ip=request.client.host if request.client else None,
                          user_agent=request.headers.get("user-agent"),
                          request_id=request.headers.get("x-request-id") or getattr(request.state, "request_id", None))


def build_subject(db: DbSession, user: User, mfa_passed: bool) -> E.Subject:
    rows = db.execute(
        select(RoleGrant.permission, RoleGrant.scope)
        .join(UserRole, UserRole.role_id == RoleGrant.role_id)
        .where(UserRole.user_id == user.id, RoleGrant.organization_id == user.organization_id)
    ).all()
    teams = db.execute(select(TeamMember.team_id, TeamMember.is_manager).where(TeamMember.user_id == user.id)).all()
    return E.Subject(
        user_id=user.id, organization_id=user.organization_id,
        grants=tuple(E.Grant(p, s) for p, s in rows),
        team_ids=frozenset(t for t, _ in teams), managed_team_ids=frozenset(t for t, m in teams if m),
        department_id=user.department_id, is_super_admin=user.is_super_admin,
        mfa_passed=mfa_passed, active=user.status == "active",
    )


def _load_caller(request: Request, db: DbSession, allow_mfa_pending: bool) -> Caller:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    sess = db.scalar(select(Session).where(Session.token_hash == token_hash(raw)))
    now = datetime.now(timezone.utc)
    idle = timedelta(minutes=settings.session_idle_minutes)
    if sess is None or sess.revoked_at is not None or sess.expires_at <= now or sess.last_seen_at + idle <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has ended. Sign in again.")
    user = db.get(User, sess.user_id)
    if user is None or user.status != "active":
        sess.revoked_at = now
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account is not active.")
    if request.method not in SAFE_METHODS and not verify_csrf(raw, settings.secret_key, request.headers.get(CSRF_HEADER)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Security check failed. Reload the page and try again.")
    needs_mfa = user.mfa_required or user.is_super_admin
    if needs_mfa and not sess.mfa_passed and not allow_mfa_pending:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Confirm your authenticator code to continue.", headers={"x-mfa-required": "1"})
    if (now - sess.last_seen_at) > timedelta(minutes=1):
        sess.last_seen_at = now
    subject = build_subject(db, user, sess.mfa_passed)
    return Caller(user=user, session=sess, subject=subject, ctx=_ctx(request, user.organization_id, user.id), raw_token=raw)


def signed_in(request: Request, db: DbSession = Depends(get_db)) -> Caller:
    return _load_caller(request, db, allow_mfa_pending=False)


def signed_in_mfa_pending(request: Request, db: DbSession = Depends(get_db)) -> Caller:
    """Only for the MFA setup/verify endpoints themselves."""
    return _load_caller(request, db, allow_mfa_pending=True)


def requires(permission: str) -> Callable[..., Caller]:
    """Route dependency: 403 unless the caller holds ``permission`` at some scope.
    Record-level scope is then enforced in the service with engine.check / engine.criteria."""
    E.scope_for(E.Subject(user_id=uuid.uuid4(), organization_id=uuid.uuid4()), permission)  # validates the name at import

    def dep(caller: Caller = Depends(signed_in)) -> Caller:
        try:
            E.require(caller.subject, permission)
        except E.Forbidden:
            if E.requires_mfa(permission) and not caller.subject.mfa_passed:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "This action needs your authenticator code.", headers={"x-mfa-required": "1"})
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do that.")
        return caller

    dep.__mme_permission__ = permission  # read by the route-permission test
    return dep


def public_context(request: Request, org_id: uuid.UUID) -> RequestContext:
    return _ctx(request, org_id, None)


def public() -> None:
    """Marker dependency for routes that intentionally need no session (sign-in, health)."""
    return None


public.__mme_public__ = True  # type: ignore[attr-defined]
