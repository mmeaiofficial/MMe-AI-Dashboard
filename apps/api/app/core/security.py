"""Passwords, one-time codes, session and CSRF tokens, invitation tokens.

Standard library only (hashlib.scrypt, hmac, secrets), so these primitives are unit-tested
without the web stack.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from typing import Optional
from urllib.parse import quote

# ---------- passwords (scrypt, memory-hard) ----------
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 15, 8, 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024
MIN_PASSWORD_LENGTH = 12


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, maxmem=_SCRYPT_MAXMEM, dklen=32)
    return "scrypt${}${}${}${}${}".format(_SCRYPT_N, _SCRYPT_R, _SCRYPT_P, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        # Burn similar time so missing accounts are not distinguishable by timing.
        hashlib.scrypt(b"x", salt=b"0" * 16, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, maxmem=_SCRYPT_MAXMEM, dklen=32)
        return False
    try:
        _, n, r, p, salt_b64, dk_b64 = stored.split("$")
        dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p), maxmem=_SCRYPT_MAXMEM, dklen=32)
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except (ValueError, TypeError):
        return False


# ---------- TOTP (RFC 6238, SHA-1, 6 digits, 30 s) ----------
TOTP_STEP = 30
TOTP_DIGITS = 6


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _b32decode(secret: str) -> bytes:
    s = secret.upper().replace(" ", "")
    return base64.b32decode(s + "=" * (-len(s) % 8))


def totp_at(secret: str, step: int) -> str:
    digest = hmac.new(_b32decode(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** TOTP_DIGITS)
    return str(code).zfill(TOTP_DIGITS)


def verify_totp(secret: str, code: str, last_used_step: Optional[int], now: Optional[float] = None, window: int = 1) -> Optional[int]:
    """Return the matched time step (to store as last_used_step), or None.

    Accepts ±``window`` steps for clock drift and rejects any step at or before the last
    one used, so a code can't be replayed.
    """
    code = (code or "").strip().replace(" ", "")
    if len(code) != TOTP_DIGITS or not code.isdigit():
        return None
    current = int((time.time() if now is None else now) // TOTP_STEP)
    for step in range(current - window, current + window + 1):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(totp_at(secret, step), code):
            return step
    return None


def totp_uri(secret: str, email: str, issuer: str = "MME OS") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}&digits={TOTP_DIGITS}&period={TOTP_STEP}"


# ---------- opaque tokens (sessions, invitations, API keys) ----------

def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    """Only this hash is stored; a database leak does not reveal live tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_api_key(env: str = "live") -> tuple[str, str]:
    raw = new_token(32)
    key = f"mme_{env}_{raw}"
    return key, key[:13]


# ---------- CSRF (double-submit, bound to the session) ----------

def csrf_token(session_token: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), b"csrf:" + session_token.encode(), hashlib.sha256).hexdigest()


def verify_csrf(session_token: str, secret_key: str, presented: Optional[str]) -> bool:
    if not presented:
        return False
    return hmac.compare_digest(csrf_token(session_token, secret_key), presented)
