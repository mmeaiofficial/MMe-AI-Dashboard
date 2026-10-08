from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import record, record_now
from ...authz import engine as E
from ...core import google_oidc as G
from ...core.config import load_settings
from ...core.db import get_db
from ...core.deps import Caller, public, public_context, signed_in_mfa_pending
from ...core.models import MfaFactor, Role, TeamMember, User, UserRole
from ...core.ratelimit import LIMITS, get_limiter
from ...core.security import csrf_token, new_totp_secret, totp_uri, verify_password, verify_totp
from . import service as S
from .policy import DENIAL_MESSAGES, Decision, ExistingUser, decide_sign_in

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["me"])
settings = load_settings()
OAUTH_COOKIE = "mme_oauth"
_signer = URLSafeTimedSerializer(settings.secret_key, salt="google-oauth")


def _limit(name: str, key: str) -> None:
    limit, window = LIMITS[name]
    if not get_limiter().hit(f"{name}:{key}", limit, window):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Wait a few minutes and try again.")


def _safe_next(path: Optional[str]) -> str:
    return path if path and path.startswith("/") and not path.startswith("//") else "/"


def _redirect_web(path: str, error: Optional[str] = None) -> RedirectResponse:
    url = settings.web_origin + path + (("?error=" + quote(error)) if error else "")
    return RedirectResponse(url, status_code=303)


# ---------- Google ----------
@router.get("/google/start", dependencies=[Depends(public)])
def google_start(request: Request, next: Optional[str] = None, invite: Optional[str] = None) -> RedirectResponse:
    _limit("login_ip", request.client.host if request.client else "unknown")
    req = G.build_auth_request(settings.google_client_id, settings.api_origin + "/api/v1/auth/google/callback")
    resp = RedirectResponse(req.url, status_code=303)
    payload = _signer.dumps({"s": req.state, "n": req.nonce, "v": req.code_verifier, "next": _safe_next(next), "invite": invite})
    resp.set_cookie(OAUTH_COOKIE, payload, max_age=600, httponly=True, secure=settings.cookie_secure, samesite="lax",
                    path="/api/v1/auth/google", domain=S.COOKIE_DOMAIN)
    return resp


@router.get("/google/callback", dependencies=[Depends(public)])
def google_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None,
                    db: DbSession = Depends(get_db)) -> RedirectResponse:
    try:
        data = _signer.loads(request.cookies.get(OAUTH_COOKIE, ""), max_age=600)
    except BadSignature:
        return _redirect_web("/sign-in", "Sign-in expired. Try again.")
    if not code or not state or state != data["s"]:
        return _redirect_web("/sign-in", "Sign-in could not be verified. Try again.")
    try:
        r = httpx.post(G.TOKEN_URL, data={
            "code": code, "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
            "redirect_uri": settings.api_origin + "/api/v1/auth/google/callback", "grant_type": "authorization_code",
            "code_verifier": data["v"]}, timeout=10)
        r.raise_for_status()
        ident = G.verify_id_token(r.json()["id_token"], settings.google_client_id, data["n"])
    except (httpx.HTTPError, KeyError, G.InvalidGoogleToken):
        return _redirect_web("/sign-in", "Google sign-in failed. Try again.")

    org = S.default_org(db)
    _limit("login_email", ident.email)
    ctx = public_context(request, org.id)
    user = db.scalar(select(User).where(User.organization_id == org.id, User.email == ident.email))
    invitation = S.open_invitation(db, org.id, ident.email, data.get("invite"))
    bootstrap = ident.email in settings.bootstrap_super_admins and user is None
    decision = Decision.CREATE_FROM_INVITE if bootstrap else decide_sign_in(
        ident.email, ident.subject, ExistingUser(user.status, user.google_subject) if user else None,
        invitation is not None, (org.settings or {}).get("allowed_domains", []))

    if decision in DENIAL_MESSAGES:
        record(db, ctx, "auth.login_failed", "email", ident.email, after={"reason": decision.value})
        return _redirect_web("/sign-in", DENIAL_MESSAGES[decision])
    if user is None:
        user = S.create_user(db, org, ident.email, ident.name, ident.subject, ident.picture,
                             invitation, ctx, super_admin=bootstrap)
    elif user.google_subject is None:
        user.google_subject = ident.subject
    ctx = public_context(request, org.id)
    ctx = ctx.__class__(ctx.organization_id, user.id, ctx.ip, ctx.user_agent, ctx.request_id)
    resp = _redirect_web("/mfa" if (user.mfa_required or user.is_super_admin) else data["next"])
    S.start_session(db, user, resp, ctx)
    resp.delete_cookie(OAUTH_COOKIE, path="/api/v1/auth/google", domain=S.COOKIE_DOMAIN)
    return resp


# ---------- password (fallback for accounts without Google) ----------
class PasswordLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


@router.post("/password/login", dependencies=[Depends(public)])
def password_login(body: PasswordLogin, request: Request, response: Response, db: DbSession = Depends(get_db)) -> dict:
    email = body.email.lower()
    _limit("login_ip", request.client.host if request.client else "unknown")
    _limit("login_email", email)
    org = S.default_org(db)
    user = db.scalar(select(User).where(User.organization_id == org.id, User.email == email))
    ok = verify_password(body.password, user.password_hash if user else None)
    ctx = public_context(request, org.id)
    if not ok or user is None or user.status != "active":
        record_now(ctx, "auth.login_failed", "email", email, after={"reason": "bad_credentials"})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    ctx = ctx.__class__(ctx.organization_id, user.id, ctx.ip, ctx.user_agent, ctx.request_id)
    S.start_session(db, user, response, ctx)
    return {"mfa_required": bool(user.mfa_required or user.is_super_admin)}


# ---------- MFA ----------
class CodeBody(BaseModel):
    code: str = Field(min_length=6, max_length=8)


@router.post("/mfa/setup")
def mfa_setup(caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    factor = db.scalar(select(MfaFactor).where(MfaFactor.user_id == caller.user.id, MfaFactor.kind == "totp"))
    if factor and factor.confirmed_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "An authenticator is already set up. Ask a Super Admin to reset it.")
    secret = new_totp_secret()
    enc = S.cipher().encrypt(secret, f"mfa:{caller.user.id}")
    if factor:
        factor.secret_enc = enc
    else:
        db.add(MfaFactor(user_id=caller.user.id, organization_id=caller.user.organization_id, secret_enc=enc))
    return {"otpauth_uri": totp_uri(secret, caller.user.email), "secret": secret}


def _check_code(caller: Caller, db: DbSession, code: str, confirming: bool) -> None:
    _limit("mfa_user", str(caller.user.id))
    factor = db.scalar(select(MfaFactor).where(MfaFactor.user_id == caller.user.id, MfaFactor.kind == "totp"))
    if factor is None or (factor.confirmed_at is None) != confirming:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Set up your authenticator first." if factor is None else "Use the verify step.")
    secret = S.cipher().decrypt(factor.secret_enc, f"mfa:{caller.user.id}")
    step = verify_totp(secret, code, factor.last_used_step)
    if step is None:
        record_now(caller.ctx, "auth.mfa_failed", "user", caller.user.id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code didn't match. Check your authenticator and try again.")
    factor.last_used_step = step
    if confirming:
        factor.confirmed_at = datetime.now(timezone.utc)
        caller.user.mfa_required = True
        record(db, caller.ctx, "auth.mfa_enrolled", "user", caller.user.id)
    caller.session.mfa_passed = True
    record(db, caller.ctx, "auth.mfa_passed", "user", caller.user.id)


@router.post("/mfa/confirm")
def mfa_confirm(body: CodeBody, caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    _check_code(caller, db, body.code, confirming=True)
    return {"ok": True}


@router.post("/mfa/verify")
def mfa_verify(body: CodeBody, caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    _check_code(caller, db, body.code, confirming=False)
    return {"ok": True}


# ---------- sign out ----------
@router.post("/logout")
def logout(response: Response, caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    S.end_session(db, caller.session, response, caller.ctx)
    return {"ok": True}


@router.post("/logout-all")
def logout_all(response: Response, caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    n = S.revoke_all_sessions(db, caller.user.id)
    response.delete_cookie("mme_session", path="/", domain=S.COOKIE_DOMAIN)
    record(db, caller.ctx, "auth.logout_all", "user", caller.user.id, after={"sessions": n})
    return {"ended": n}


# ---------- me ----------
@me_router.get("/me")
def me(caller: Caller = Depends(signed_in_mfa_pending), db: DbSession = Depends(get_db)) -> dict:
    u, subj = caller.user, caller.subject
    roles = db.execute(select(Role.key, Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == u.id)).all()
    factor = db.scalar(select(MfaFactor).where(MfaFactor.user_id == u.id, MfaFactor.confirmed_at.is_not(None)))
    perms = {}
    if caller.session.mfa_passed or not (u.mfa_required or u.is_super_admin):
        from ...authz.catalog import ALL_PERMISSIONS
        perms = {p: E.scope_for(subj, p) for p in sorted(ALL_PERMISSIONS) if E.scope_for(subj, p)}
    return {
        "id": str(u.id), "email": u.email, "full_name": u.full_name, "avatar_url": u.avatar_url,
        "is_super_admin": u.is_super_admin, "roles": [{"key": k, "name": n} for k, n in roles],
        "team_ids": [str(t) for t in subj.team_ids], "department_id": str(u.department_id) if u.department_id else None,
        "mfa": {"required": bool(u.mfa_required or u.is_super_admin), "enrolled": factor is not None, "passed": caller.session.mfa_passed},
        "permissions": perms,
        "csrf_token": csrf_token(caller.raw_token, settings.secret_key),
    }
