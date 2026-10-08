"""Who may sign in. Pure function so every branch is unit-tested."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional


class Decision(str, Enum):
    SIGN_IN = "sign_in"                    # existing active user
    CREATE_FROM_INVITE = "create_invite"   # new user from an open invitation
    CREATE_FROM_DOMAIN = "create_domain"   # new user on an allowed company domain, base role only
    DENY_DEACTIVATED = "deny_deactivated"
    DENY_NOT_INVITED = "deny_not_invited"
    DENY_SUBJECT_MISMATCH = "deny_subject_mismatch"


@dataclass(frozen=True)
class ExistingUser:
    status: str
    google_subject: Optional[str]


def decide_sign_in(email: str, google_subject: Optional[str], existing: Optional[ExistingUser],
                   has_open_invitation: bool, allowed_domains: Iterable[str]) -> Decision:
    email = email.lower()
    if existing is not None:
        if existing.status != "active":
            return Decision.DENY_DEACTIVATED
        # Once linked, an account only accepts the same Google identity (blocks a recycled address).
        if google_subject and existing.google_subject and existing.google_subject != google_subject:
            return Decision.DENY_SUBJECT_MISMATCH
        return Decision.SIGN_IN
    if has_open_invitation:
        return Decision.CREATE_FROM_INVITE
    domain = email.rsplit("@", 1)[-1]
    if domain and domain in {d.lower().lstrip("@") for d in allowed_domains}:
        return Decision.CREATE_FROM_DOMAIN
    return Decision.DENY_NOT_INVITED


DENIAL_MESSAGES = {
    Decision.DENY_DEACTIVATED: "This account has been deactivated. Contact your administrator.",
    Decision.DENY_NOT_INVITED: "This account isn't invited to MME OS. Ask a Super Admin for an invitation.",
    Decision.DENY_SUBJECT_MISMATCH: "This email is linked to a different Google account. Contact your administrator.",
}
