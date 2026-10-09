"""Vercel build step for the API: on production deploys, migrate the database and seed the organization.

Preview deploys skip it so a branch can never change the production schema.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if os.environ.get("VERCEL_ENV") != "production":
        print("Not a production deploy: skipping database migrations.")
        return
    if not os.environ.get("DATABASE_URL"):
        sys.exit("DATABASE_URL is not set. Connect a Postgres database to the project before deploying.")
    for cmd in (["-m", "alembic", "upgrade", "head"], ["-m", "scripts.seed"]):
        print("$ python", " ".join(cmd), flush=True)
        subprocess.run([sys.executable, *cmd], cwd=ROOT, check=True)  # noqa: S603  # nosec B603


if __name__ == "__main__":
    main()
