"""Field-level encryption for secrets stored in the database (MFA secrets, integration tokens).

AES-256-GCM with a key id in every ciphertext ("v1.<kid>.<nonce>.<ciphertext>") so keys can
rotate: new writes use the active key, old values still decrypt with retired keys until
re-encrypted. Keys come from the secrets manager via FIELD_ENCRYPTION_KEYS, never the repo.
"""
from __future__ import annotations

import base64
import os
from collections.abc import Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class FieldCipher:
    def __init__(self, keys: Mapping[str, bytes], active_kid: str):
        if active_kid not in keys:
            raise ValueError("active key id missing")
        for kid, key in keys.items():
            if len(key) != 32:
                raise ValueError(f"key {kid} must be 32 bytes")
            if "." in kid:
                raise ValueError("key id may not contain '.'")
        self._keys = dict(keys)
        self._active = active_kid

    @classmethod
    def from_env(cls, spec: str, active_kid: str) -> FieldCipher:
        """spec = "kid1:base64key,kid2:base64key" """
        keys = {}
        for part in filter(None, (p.strip() for p in spec.split(","))):
            kid, b64 = part.split(":", 1)
            keys[kid] = _b64d(b64)
        return cls(keys, active_kid)

    def encrypt(self, plaintext: str, context: str) -> str:
        """``context`` (e.g. "mfa:<user id>") is bound as associated data: a ciphertext copied
        to another row fails to decrypt."""
        nonce = os.urandom(12)
        ct = AESGCM(self._keys[self._active]).encrypt(nonce, plaintext.encode(), context.encode())
        return f"v1.{self._active}.{_b64e(nonce)}.{_b64e(ct)}"

    def decrypt(self, token: str, context: str) -> str:
        version, kid, nonce, ct = token.split(".")
        if version != "v1" or kid not in self._keys:
            raise ValueError("unknown ciphertext version or key")
        return AESGCM(self._keys[kid]).decrypt(_b64d(nonce), _b64d(ct), context.encode()).decode()

    def needs_rotation(self, token: str) -> bool:
        return token.split(".")[1] != self._active
