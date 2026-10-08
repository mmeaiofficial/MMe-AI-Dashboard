"""Milestones 0 + 1 foundation schema.

Revision ID: 0001
Revises:
"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[1] / "sql" / "0001_foundation.sql"

TABLES = ["outbox_events", "files", "audit_events", "api_keys", "mfa_factors", "sessions", "invitations", "user_roles",
          "role_grants", "roles", "employees", "team_members", "teams", "users", "departments", "organizations"]


def upgrade() -> None:
    op.execute(SQL.read_text())


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    for fn in ("audit_events_immutable", "touch_updated_at", "keep_one_super_admin"):
        op.execute(f"DROP FUNCTION IF EXISTS {fn}() CASCADE")
