"""Invitations remember team-manager flags.

Revision ID: 0003
Revises: 0002
"""
from pathlib import Path

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[1] / "sql" / "0003_invite_managers.sql"


def upgrade() -> None:
    op.execute(SQL.read_text())


def downgrade() -> None:
    op.execute("ALTER TABLE invitations DROP COLUMN IF EXISTS manager_team_ids")
