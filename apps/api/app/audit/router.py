from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..core.db import get_db
from ..core.deps import Caller, requires
from ..core.models import AuditEvent

router = APIRouter(tags=["audit"])


@router.get("/audit-events")
def list_audit_events(
    action: Optional[str] = Query(default=None, max_length=80),
    actor_user_id: Optional[uuid.UUID] = None,
    target_id: Optional[str] = Query(default=None, max_length=80),
    before_id: Optional[int] = None,
    since: Optional[datetime] = None,
    limit: int = Query(default=50, ge=1, le=100),
    caller: Caller = Depends(requires("audit.events.view")),
    db: DbSession = Depends(get_db),
) -> dict:
    q = select(AuditEvent).where(AuditEvent.organization_id == caller.user.organization_id)
    if action:
        q = q.where(AuditEvent.action.startswith(action))
    if actor_user_id:
        q = q.where(AuditEvent.actor_user_id == actor_user_id)
    if target_id:
        q = q.where(AuditEvent.target_id == target_id)
    if since:
        q = q.where(AuditEvent.created_at >= since)
    if before_id:
        q = q.where(AuditEvent.id < before_id)
    rows = db.scalars(q.order_by(AuditEvent.id.desc()).limit(limit)).all()
    items = [{"id": r.id, "action": r.action, "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
              "target_type": r.target_type, "target_id": r.target_id, "before": r.before, "after": r.after,
              "ip": str(r.ip) if r.ip else None, "created_at": r.created_at.isoformat()} for r in rows]
    return {"items": items, "next_before_id": items[-1]["id"] if len(items) == limit else None}
