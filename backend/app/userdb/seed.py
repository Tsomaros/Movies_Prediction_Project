"""The demo account and its starting set, kept in demo_seed.json by TMDB id.

    load_seed(path=SEED_FILE)       -> the seed as a dict: username, watched [{movie_id, watched_on, rating}],
                                       plan_to_watch [movie_id], notes [{movie_id, body}] (newest first)
    seed_ids(seed)                  -> every film id the seed uses
    check_ids(sqlite_con, seed)     -> raises ValueError naming the ids missing from the movie database
    restore(conn, user_id, seed)    -> the user's lists and notes become exactly the seed (one transaction)
    reset_if_due(conn, user_id, seed, today, now)
                                    -> True if the nightly reset ran: restore + expired sessions deleted +
                                       last_reset = today; False when it already ran today
    seed(conn, sqlite_con, password, seed, today)
                                    -> creates (or updates) the demo user with that password and restores the seed

    uv run python -m backend.app.userdb.seed   # USER_DATABASE_URL and DEMO_PASSWORD from .env; MOVIES_DB for the check

Entries and notes get their times from their order in the file (the first is the newest, one hour apart),
so "date added" and the notes list show the same order after every reset. The reset runs under
pg_advisory_xact_lock, so two visitors logging in at once after midnight reset only once.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from backend.app.services.platform.auth import hash_password, today_athens
from backend.app.userdb import repo

SEED_FILE = Path(__file__).parent / "demo_seed.json"
RESET_LOCK = 1414_0002  # pg_advisory_xact_lock key for the nightly reset
LAST_RESET = "last_reset"


def load_seed(path: Path = SEED_FILE) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def seed_ids(seed: dict[str, Any]) -> set[int]:
    return ({w["movie_id"] for w in seed["watched"]} | set(seed["plan_to_watch"])
            | {n["movie_id"] for n in seed["notes"]})


def check_ids(sqlite_con: sqlite3.Connection, seed: dict[str, Any]) -> None:
    ids = sorted(seed_ids(seed))
    found = {r[0] for r in sqlite_con.execute(f"SELECT id FROM movies WHERE id IN ({','.join('?' * len(ids))})", ids)}
    missing = [i for i in ids if i not in found]
    if missing:
        raise ValueError(f"demo seed films missing from the movie database: {missing}")


def restore(conn: psycopg.Connection, user_id: int, seed: dict[str, Any]) -> None:
    with conn.transaction():
        conn.execute("DELETE FROM user_movies WHERE user_id = %s", (user_id,))
        conn.execute("DELETE FROM comments WHERE user_id = %s", (user_id,))
        rows = ([(w["movie_id"], "watched", w["watched_on"], w["rating"]) for w in seed["watched"]]
                + [(movie_id, "plan_to_watch", None, None) for movie_id in seed["plan_to_watch"]])
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO user_movies (user_id, movie_id, status, watched_on, rating, added_at, updated_at)
                               VALUES (%s, %s, %s, %s, %s, now() - %s * interval '1 hour', now() - %s * interval '1 hour')""",
                            [(user_id, m, s, d, r, i, i) for i, (m, s, d, r) in enumerate(rows)])
            cur.executemany("""INSERT INTO comments (user_id, movie_id, body, created_at, updated_at)
                               VALUES (%s, %s, %s, now() - %s * interval '1 hour', now() - %s * interval '1 hour')""",
                            [(user_id, n["movie_id"], n["body"], i, i) for i, n in enumerate(seed["notes"])])


def reset_if_due(conn: psycopg.Connection, user_id: int, seed: dict[str, Any], today: date, now: datetime) -> bool:
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (RESET_LOCK,))
        last = repo.get_state(conn, LAST_RESET)
        if last is not None and date.fromisoformat(last) >= today:
            return False
        restore(conn, user_id, seed)
        repo.delete_expired_sessions(conn, now)
        repo.set_state(conn, LAST_RESET, today.isoformat())
    return True


def seed(conn: psycopg.Connection, sqlite_con: sqlite3.Connection, password: str, seed: dict[str, Any],
         today: date) -> int:
    check_ids(sqlite_con, seed)
    with conn.transaction():
        user_id = repo.upsert_user(conn, seed["username"], hash_password(password), is_demo=True)
        restore(conn, user_id, seed)
        repo.set_state(conn, LAST_RESET, today.isoformat())
    return user_id


def main() -> None:
    from backend.app.deps import connect_read_only
    from backend.app.settings import Settings

    load_dotenv()
    settings = Settings.from_env()
    data = load_seed()
    with psycopg.connect(os.environ["USER_DATABASE_URL"], autocommit=True, connect_timeout=10,
                         row_factory=dict_row) as conn:
        sqlite_con = connect_read_only(settings.db_path)
        try:
            user_id = seed(conn, sqlite_con, os.environ["DEMO_PASSWORD"], data, today_athens())
        finally:
            sqlite_con.close()
    print(f"demo user {data['username']!r} (id {user_id}): {len(data['watched'])} watched, "
          f"{len(data['plan_to_watch'])} to watch, {len(data['notes'])} notes")


if __name__ == "__main__":
    main()
