from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import RequestContext, record
from ...core.config import load_settings
from ...core.crypto import FieldCipher
from ...core.deps import SESSION_COOKIE
from ...core.models import Employee, Invitation, Organization, Role, Session, TeamMember, User, UserRole
from ...core.security import new_token, token_hash

settings = load_settings()
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN") or None


def cipher() -> FieldCipher:
    if not settings.field_encryption_keys:
        # development only (config.validate refuses this outside development)
        import base64
        return FieldCipher({"dev": base64.urlsafe_b64decode("bW1lLW9zLWRldmVsb3BtZW50LW9ubHkta2V5LTAwMDE=")}, "dev")
    return FieldCipher.from_env(settings.field_encryption_keys, settings.field_encryption_active_kid)


def default_org(db: DbSession) -> Organization:
    org = db.scalar(select(Organization).where(Organization.kind == "internal").order_by(Organization.created_at).limit(1))
    if org is None:
        raise RuntimeError("No organization found. Run scripts/seed.py first.")
    return org


def open_invitation(db: DbSession, org_id: uuid.UUID, email: str, raw_token: Optional[str]) -> Optional[Invitation]:
    q = select(Invitation).where(Invitation.organization_id == org_id, Invitation.email == email,
                                 Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None),
                                 Invitation.expires_at > datetime.now(timezone.utc))
    if raw_token:
        q = q.where(Invitation.token_hash == token_hash(raw_token))
    return db.scalar(q)


def create_user(db: DbSession, org: Organization, email: str, name: str, google_subject: Optional[str],
                avatar: Optional[str], invitation: Optional[Invitation], ctx: RequestContext, super_admin: bool = False) -> User:
    user = User(organization_id=org.id, email=email, full_name=name, google_subject=google_subject,
                avatar_url=avatar if (avatar or "").startswith("https://") else None,
                is_super_admin=super_admin, mfa_required=super_admin,
                department_id=invitation.department_id if invitation else None)
    db.add(user)
    db.flush()
    db.add(Employee(user_id=user.id, organization_id=org.id))
    role_ids = list(invitation.role_ids) if invitation else []
    if not role_ids:
        base = db.scalar(select(Role).where(Role.organization_id == org.id, Role.key == "employee"))
        role_ids = [base.id] if base else []
    for rid in role_ids:
        db.add(UserRole(user_id=user.id, role_id=rid, organization_id=org.id, granted_by=invitation.invited_by if invitation else None))
    for tid in (invitation.team_ids if invitation else []):
        db.add(TeamMember(team_id=tid, user_id=user.id, organization_id=org.id))
    if invitation:
        invitation.accepted_at = datetime.now(timezone.utc)
    record(db, RequestContext(org.id, user.id, ctx.ip, ctx.user_agent, ctx.request_id), "admin.user_created",
           "user", user.id, after={"email": email, "via": "invitation" if invitation else ("bootstrap" if super_admin else "domain"),
                                  "role_ids": role_ids, "super_admin": super_admin})
    return user


def start_session(db: DbSession, user: User, response: Response, ctx: RequestContext) -> str:
    raw = new_token()
    now = datetime.now(timezone.utc)
    db.add(Session(user_id=user.id, organization_id=user.organization_id, token_hash=token_hash(raw), mfa_passed=False,
                   ip=ctx.ip, user_agent=(ctx.user_agent or "")[:400], expires_at=now + timedelta(hours=settings.session_hours),
                   last_seen_at=now))
    user.last_login_at = now
    response.set_cookie(SESSION_COOKIE, raw, max_age=settings.session_hours * 3600, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/", domain=COOKIE_DOMAIN)
    record(db, ctx, "auth.login", "user", user.id)
    return raw


def end_session(db: DbSession, sess: Session, response: Response, ctx: RequestContext) -> None:
    sess.revoked_at = datetime.now(timezone.utc)
    response.delete_cookie(SESSION_COOKIE, path="/", domain=COOKIE_DOMAIN)
    record(db, ctx, "auth.logout", "user", sess.user_id)


def revoke_all_sessions(db: DbSession, user_id: uuid.UUID) -> int:
    res = db.execute(update(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
                     .values(revoked_at=datetime.now(timezone.utc)))
    return res.rowcount or 0
