"""Audit writer: adds the event to the SAME database session as the change, so both commit
together (get_db commits once per request) or neither does."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..core.models import AuditEvent

REDACT = {"password", "password_hash", "secret", "secret_enc", "token", "token_hash", "key_hash", "code"}


@dataclass(frozen=True)
class RequestContext:
    organization_id: uuid.UUID
    actor_user_id: Optional[uuid.UUID]
    ip: Optional[str]
    user_agent: Optional[str]
    request_id: Optional[str]


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[redacted]" if k in REDACT else _clean(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_clean(v) for v in value]
    if isinstance(value, (uuid.UUID, datetime, date)):
        return str(value)
    return value


def record_now(ctx: RequestContext, action: str, target_type: Optional[str] = None,
               target_id: Optional[Any] = None, before: Optional[dict] = None, after: Optional[dict] = None) -> None:
    """For security events on a request that is about to fail (failed sign-in, wrong MFA code):
    written in its own transaction so the request's rollback does not erase it."""
    from ..core.db import SessionLocal
    db = SessionLocal()
    try:
        record(db, ctx, action, target_type, target_id, before, after)
        db.commit()
    finally:
        db.close()


def record(db: Session, ctx: RequestContext, action: str, target_type: Optional[str] = None,
           target_id: Optional[Any] = None, before: Optional[dict] = None, after: Optional[dict] = None) -> None:
    db.add(AuditEvent(
        organization_id=ctx.organization_id, actor_user_id=ctx.actor_user_id, action=action,
        target_type=target_type, target_id=str(target_id) if target_id is not None else None,
        before=json.loads(json.dumps(_clean(before))) if before is not None else None,
        after=json.loads(json.dumps(_clean(after))) if after is not None else None,
        ip=ctx.ip, user_agent=(ctx.user_agent or "")[:400], request_id=ctx.request_id,
    ))
