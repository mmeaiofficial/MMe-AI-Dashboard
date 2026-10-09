"""Milestone 3 first slice: leads, cold calls, meetings, clients, projects and tickets.

Revision ID: 0002
Revises: 0001
"""
from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[1] / "sql" / "0002_pipeline.sql"

TABLES = ["ticket_notes", "tickets", "projects", "clients", "meetings", "lead_calls", "leads"]


def upgrade() -> None:
    op.execute(SQL.read_text())


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    op.execute("UPDATE teams SET kind = 'custom' WHERE kind IN ('lead_gen', 'sales_l1', 'sales_l2')")
    op.execute("ALTER TABLE teams DROP CONSTRAINT teams_kind_check")
    op.execute("ALTER TABLE teams ADD CONSTRAINT teams_kind_check CHECK (kind IN "
               "('sales', 'marketing', 'tech', 'ai_automation', 'customer_success', 'finance_ops', 'custom'))")
