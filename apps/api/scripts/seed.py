"""Create the MME organization, the default roles and the base settings. Safe to run again.

    python -m scripts.seed --org-name "MME AI" --domain mme-ai.com

Super Admins are NOT created here: the emails in BOOTSTRAP_SUPER_ADMINS become Super Admins
the first time they sign in with Google, and must then set up MFA.
"""
from __future__ import annotations

import argparse

from sqlalchemy import delete, select

from app.authz.catalog import DEFAULT_ROLES
from app.core.db import SessionLocal
from app.core.models import Organization, Role, RoleGrant


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org-name", default="MME AI")
    ap.add_argument("--slug", default="mme")
    ap.add_argument("--domain", action="append", default=[], help="Google Workspace domain whose accounts may join (repeatable)")
    ap.add_argument("--reset-default-grants", action="store_true", help="overwrite edited default roles with the catalog")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        org = db.scalar(select(Organization).where(Organization.slug == args.slug))
        if org is None:
            org = Organization(name=args.org_name, slug=args.slug, kind="internal", settings={"allowed_domains": args.domain})
            db.add(org)
            db.flush()
            print(f"created organization {org.name}")
        elif args.domain:
            org.settings = {**(org.settings or {}), "allowed_domains": sorted(set(args.domain))}

        for key, spec in DEFAULT_ROLES.items():
            role = db.scalar(select(Role).where(Role.organization_id == org.id, Role.key == key))
            if role is None:
                role = Role(organization_id=org.id, key=key, name=spec["name"], is_system=True)
                db.add(role)
                db.flush()
            elif not args.reset_default_grants:
                continue
            db.execute(delete(RoleGrant).where(RoleGrant.role_id == role.id))
            for perm, scope in spec["grants"]:
                db.add(RoleGrant(role_id=role.id, organization_id=org.id, permission=perm, scope=scope))
            print(f"role {key}: {len(spec['grants'])} grants")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
