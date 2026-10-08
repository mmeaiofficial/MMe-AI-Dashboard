"""Google sign-in (OpenID Connect, authorization code flow with PKCE).

The ID token is verified locally: signature against Google's published keys, issuer,
audience (our client id), expiry, nonce, and a verified email.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlencode

import jwt  # PyJWT

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    name: str
    picture: Optional[str]
    hosted_domain: Optional[str]


@dataclass(frozen=True)
class AuthRequest:
    url: str
    state: str
    nonce: str
    code_verifier: str


def build_auth_request(client_id: str, redirect_uri: str, hosted_domain: Optional[str] = None) -> AuthRequest:
    state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    params = {
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": "openid email profile", "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account",
    }
    if hosted_domain:
        params["hd"] = hosted_domain  # a UI hint only; the server still checks access itself
    return AuthRequest(f"{AUTH_URL}?{urlencode(params)}", state, nonce, verifier)


class InvalidGoogleToken(Exception):
    pass


_jwks_client: Optional[jwt.PyJWKClient] = None


def _default_key_resolver(token: str):
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600)
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_id_token(id_token: str, client_id: str, nonce: str,
                    key_resolver: Callable[[str], object] = _default_key_resolver,
                    leeway: int = 60) -> GoogleIdentity:
    try:
        key = key_resolver(id_token)
        claims = jwt.decode(
            id_token, key=key, algorithms=["RS256"], audience=client_id, leeway=leeway,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except Exception as exc:  # noqa: BLE001 — every failure is the same answer to the caller
        raise InvalidGoogleToken(str(exc)) from exc
    if claims.get("iss") not in ISSUERS:
        raise InvalidGoogleToken("bad issuer")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise InvalidGoogleToken("nonce mismatch")
    if claims.get("email_verified") is not True or not claims.get("email"):
        raise InvalidGoogleToken("email not verified")
    return GoogleIdentity(
        subject=str(claims["sub"]), email=str(claims["email"]).lower(),
        name=str(claims.get("name", ""))[:200], picture=claims.get("picture"), hosted_domain=claims.get("hd"),
    )
