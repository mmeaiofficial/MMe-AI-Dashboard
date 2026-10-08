"""The SQL file is the source of truth; the ORM must match its tables and columns."""
from sqlalchemy import inspect

from app.core.db import engine
from app.core.models import Base


def test_models_match_database():
    insp = inspect(engine)
    problems = []
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            problems.append(f"missing table {table.name}")
            continue
        db_cols = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name not in db_cols:
                problems.append(f"{table.name}.{col.name} not in database")
    assert not problems, problems
