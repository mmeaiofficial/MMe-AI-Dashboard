"""Authorization engine: permissions + data scopes, framework-free so it is unit-tested alone.

Rules
- A subject may do ``permission`` on a record only if it holds a grant for that permission
  (or for ``<resource>.manage``) whose scope covers the record, inside its own organization.
- Several grants for one permission: the widest scope wins.
- Super Admin (a user flag, never a role) passes every check inside its own organization.
- Out-of-scope single records must be answered as "not found" by the API (no ID probing).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from .catalog import ALL_PERMISSIONS, MFA_REQUIRED_ACTIONS, MFA_REQUIRED_PREFIXES, SCOPES

RANK = {s: i for i, s in enumerate(SCOPES)}


class AuthzError(Exception):
    """Base class; the API maps subclasses to HTTP errors."""


class Forbidden(AuthzError):
    """Missing permission → 403."""


class NotFound(AuthzError):
    """Out of scope or other organization → 404 (indistinguishable from absent)."""


class EscalationDenied(AuthzError):
    """A role/permission change the actor is not allowed to make → 403."""


@dataclass(frozen=True)
class Grant:
    permission: str
    scope: str

    def __post_init__(self) -> None:
        if self.permission not in ALL_PERMISSIONS:
            raise ValueError(f"unknown permission {self.permission}")
        if self.scope not in SCOPES:
            raise ValueError(f"unknown scope {self.scope}")


@dataclass(frozen=True)
class Subject:
    user_id: UUID
    organization_id: UUID
    grants: tuple[Grant, ...] = ()
    team_ids: frozenset[UUID] = frozenset()
    managed_team_ids: frozenset[UUID] = frozenset()
    department_id: UUID | None = None
    is_super_admin: bool = False
    mfa_passed: bool = False
    active: bool = True


@dataclass(frozen=True)
class RecordRef:
    """What the engine needs to know about a record to place it in a scope."""
    organization_id: UUID
    owner_id: UUID | None = None
    team_id: UUID | None = None
    department_id: UUID | None = None
    assignee_ids: frozenset[UUID] = frozenset()


@dataclass(frozen=True)
class ScopeCriteria:
    """A filter the data layer turns into SQL. ``all_records`` means organization-wide."""
    organization_id: UUID
    all_records: bool = False
    user_ids: frozenset[UUID] = frozenset()        # owner_id IN / assignee IN
    team_ids: frozenset[UUID] = frozenset()        # team_id IN
    department_ids: frozenset[UUID] = frozenset()  # department_id IN


def _resource(permission: str) -> str:
    return permission.rsplit(".", 1)[0]


def requires_mfa(permission: str) -> bool:
    return permission.startswith(MFA_REQUIRED_PREFIXES) or permission.rsplit(".", 1)[1] in MFA_REQUIRED_ACTIONS


def effective_grants(grants: Iterable[Grant]) -> dict[str, str]:
    """permission -> widest scope across all of a user's roles."""
    out: dict[str, str] = {}
    for gr in grants:
        cur = out.get(gr.permission)
        if cur is None or RANK[gr.scope] > RANK[cur]:
            out[gr.permission] = gr.scope
    return out


def scope_for(subject: Subject, permission: str) -> str | None:
    """Widest scope the subject holds for ``permission`` (``manage`` implies all actions)."""
    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"unknown permission {permission}")
    if not subject.active:
        return None
    if subject.is_super_admin:
        return "all" if (subject.mfa_passed or not requires_mfa(permission)) else None
    eff = effective_grants(subject.grants)
    candidates = [eff.get(permission), eff.get(_resource(permission) + ".manage")]
    held = [c for c in candidates if c is not None]
    if not held:
        return None
    if requires_mfa(permission) and not subject.mfa_passed:
        return None
    return max(held, key=lambda s: RANK[s])


def has_permission(subject: Subject, permission: str) -> bool:
    return scope_for(subject, permission) is not None


def require(subject: Subject, permission: str) -> str:
    scope = scope_for(subject, permission)
    if scope is None:
        raise Forbidden(permission)
    return scope


def in_scope(subject: Subject, scope: str, record: RecordRef) -> bool:
    if record.organization_id != subject.organization_id:
        return False
    if scope == "all":
        return True
    mine = record.owner_id == subject.user_id or subject.user_id in record.assignee_ids
    if scope == "own":
        return mine
    if scope == "team":
        return mine or (record.team_id is not None and record.team_id in subject.team_ids)
    if scope == "department":
        return mine or (record.team_id is not None and record.team_id in subject.team_ids) or (
            record.department_id is not None and record.department_id == subject.department_id)
    return False


def check(subject: Subject, permission: str, record: RecordRef) -> None:
    """Raise NotFound for out-of-scope / foreign records, Forbidden for missing permission.

    Order matters: a record in another organization is NotFound even if the subject holds
    no permission at all, so existence never leaks across tenants.
    """
    if record.organization_id != subject.organization_id:
        raise NotFound()
    scope = require(subject, permission)
    if not in_scope(subject, scope, record):
        raise NotFound()


def criteria(subject: Subject, permission: str) -> ScopeCriteria:
    """List filter for ``permission``. Raises Forbidden when the permission is not held."""
    scope = require(subject, permission)
    org = subject.organization_id
    if scope == "all":
        return ScopeCriteria(org, all_records=True)
    users = frozenset({subject.user_id})
    if scope == "own":
        return ScopeCriteria(org, user_ids=users)
    if scope == "team":
        return ScopeCriteria(org, user_ids=users, team_ids=subject.team_ids)
    depts = frozenset({subject.department_id}) if subject.department_id else frozenset()
    return ScopeCriteria(org, user_ids=users, team_ids=subject.team_ids, department_ids=depts)


# ---------- role and permission changes (anti-escalation) ----------

def check_role_assignment(actor: Subject, target_user_id: UUID, role_grants: Iterable[Grant]) -> None:
    """Can ``actor`` give ``target_user_id`` a role made of ``role_grants``?

    - Requires admin.roles.manage (Super Admin has it implicitly).
    - Nobody changes their own roles, Super Admin included (a second admin must do it).
    - A non-super-admin cannot hand out a grant wider than one they hold themselves.
    """
    require(actor, "admin.roles.manage")
    if target_user_id == actor.user_id:
        raise EscalationDenied("You can't change your own roles. Ask another admin.")
    if actor.is_super_admin:
        return
    for gr in role_grants:
        held = scope_for(actor, gr.permission)
        if held is None or RANK[held] < RANK[gr.scope]:
            raise EscalationDenied(f"You can't grant {gr.permission} at {gr.scope} scope.")


def check_role_edit(actor: Subject, new_grants: Iterable[Grant], actor_holds_role: bool) -> None:
    """Can ``actor`` change a role's grants to ``new_grants``?

    - Only Super Admin edits role definitions (blueprint: only Super Admin manages roles).
    - Even Super Admin cannot edit a role it holds itself, so nobody widens their own access.
    """
    if not actor.is_super_admin:
        raise EscalationDenied("Only a Super Admin can change what a role allows.")
    if actor_holds_role:
        raise EscalationDenied("You can't edit a role you hold. Ask another Super Admin.")
    for gr in new_grants:
        if not isinstance(gr, Grant):
            raise ValueError("grants must be Grant objects")


def check_super_admin_change(actor: Subject, target_user_id: UUID, make_super_admin: bool, active_super_admins: int) -> None:
    if not actor.is_super_admin:
        raise EscalationDenied("Only a Super Admin can change Super Admin status.")
    if target_user_id == actor.user_id:
        raise EscalationDenied("You can't change your own Super Admin status.")
    if not make_super_admin and active_super_admins <= 1:
        raise EscalationDenied("At least one active Super Admin must remain.")
    if not actor.mfa_passed:
        raise EscalationDenied("Confirm MFA before changing Super Admin status.")
