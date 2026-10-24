"""Numbered SQL migrations, each applied once and recorded in schema_migrations.

    migrate(conn)  -> the names of the files applied now (oldest first); [] when the database is up to date

    uv run python -m backend.app.userdb.migrate     # against USER_DATABASE_URL (.env is read)

Files in migrations/ run in name order (001_init.sql, 002_...), each in its own transaction together with
its schema_migrations row, so a failed file leaves nothing half applied. An advisory lock keeps two runs
from applying the same file at once.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

MIGRATIONS = Path(__file__).parent / "migrations"
LOCK = 1414_0001  # pg_advisory_xact_lock key for migrations


def migrate(conn: psycopg.Connection) -> list[str]:
    applied = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK,))
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                         "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
            if conn.execute("SELECT 1 FROM schema_migrations WHERE name = %s", (path.name,)).fetchone():
                continue
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        applied.append(path.name)
    return applied


def main() -> None:
    load_dotenv()
    with psycopg.connect(os.environ["USER_DATABASE_URL"], autocommit=True, connect_timeout=10) as conn:
        applied = migrate(conn)
    print(f"applied {', '.join(applied)}" if applied else "up to date")


if __name__ == "__main__":
    main()
