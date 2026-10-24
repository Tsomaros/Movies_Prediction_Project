"""Plain SQL for the user database. Every function takes a connection from the pool (autocommit, dict rows).

Users and sessions
    user_by_name(conn, username)                 -> the user row, or None
    upsert_user(conn, username, hash, is_demo)   -> the user's id (a new password hash replaces the old one)
    demo_user(conn)                              -> the demo user's row, or None before the seed has run
    create_session(conn, user_id, token_hash, expires_at)
    session_user(conn, token_hash, now)          -> the user of an unexpired session, or None
    delete_session(conn, token_hash)
    delete_expired_sessions(conn, now)           -> how many were deleted
    get_state(conn, key) / set_state(conn, key, value)

Lists (user_movies)
    lock_user(conn, user_id)                     -> FOR UPDATE on the user's row: caps are checked one write at a time
    entries(conn, user_id)                       -> every list entry of the user (at most MAX_ENTRIES)
    entry(conn, user_id, movie_id)               -> one entry, or None
    statuses(conn, user_id, movie_ids)           -> the entries among those films
    count_entries(conn, user_id)
    set_entry(conn, user_id, movie_id, status, watched_on, rating) -> the entry after the upsert
    delete_entry(conn, user_id, movie_id)        -> whether there was one
    counts(conn, user_id)                        -> {"watched", "plan_to_watch", "notes"}

Notes (comments)
    notes_for(conn, user_id, movie_id)           -> the notes on one film, newest first
    notes_page(conn, user_id, limit, offset)     -> (one page of all notes, newest first; the total)
    count_notes(conn, user_id)
    add_note(conn, user_id, movie_id, body)      -> the new note
    update_note(conn, user_id, note_id, body)    -> the note after the edit, or None if it isn't the user's
    delete_note(conn, user_id, note_id)          -> whether the user had that note

Every query filters by user_id, so one user's id can never reach another user's rows.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Optional

import psycopg

Row = dict[str, Any]
ENTRY = "movie_id, status, watched_on, rating, added_at, updated_at"
NOTE = "id, movie_id, body, created_at, updated_at"


def user_by_name(conn: psycopg.Connection, username: str) -> Optional[Row]:
    return conn.execute("SELECT * FROM users WHERE username = %s", (username.lower(),)).fetchone()


def upsert_user(conn: psycopg.Connection, username: str, password_hash: str, is_demo: bool) -> int:
    return conn.execute("""INSERT INTO users (username, password_hash, is_demo) VALUES (%s, %s, %s)
                           ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash,
                                                                is_demo = EXCLUDED.is_demo
                           RETURNING id""", (username.lower(), password_hash, is_demo)).fetchone()["id"]


def demo_user(conn: psycopg.Connection) -> Optional[Row]:
    return conn.execute("SELECT * FROM users WHERE is_demo ORDER BY id LIMIT 1").fetchone()


def create_session(conn: psycopg.Connection, user_id: int, token_hash: bytes, expires_at: datetime) -> None:
    conn.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                 (token_hash, user_id, expires_at))


def session_user(conn: psycopg.Connection, token_hash: bytes, now: datetime) -> Optional[Row]:
    return conn.execute("""SELECT u.id, u.username, u.is_demo FROM sessions s JOIN users u ON u.id = s.user_id
                           WHERE s.token_hash = %s AND s.expires_at > %s""", (token_hash, now)).fetchone()


def delete_session(conn: psycopg.Connection, token_hash: bytes) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))


def delete_expired_sessions(conn: psycopg.Connection, now: datetime) -> int:
    return conn.execute("DELETE FROM sessions WHERE expires_at <= %s", (now,)).rowcount


def get_state(conn: psycopg.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM app_state WHERE key = %s", (key,)).fetchone()
    return row["value"] if row else None


def set_state(conn: psycopg.Connection, key: str, value: str) -> None:
    conn.execute("INSERT INTO app_state (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                 (key, value))


def lock_user(conn: psycopg.Connection, user_id: int) -> None:
    conn.execute("SELECT 1 FROM users WHERE id = %s FOR UPDATE", (user_id,))


def entries(conn: psycopg.Connection, user_id: int) -> list[Row]:
    return conn.execute(f"SELECT {ENTRY} FROM user_movies WHERE user_id = %s", (user_id,)).fetchall()


def entry(conn: psycopg.Connection, user_id: int, movie_id: int) -> Optional[Row]:
    return conn.execute(f"SELECT {ENTRY} FROM user_movies WHERE user_id = %s AND movie_id = %s",
                        (user_id, movie_id)).fetchone()


def statuses(conn: psycopg.Connection, user_id: int, movie_ids: Iterable[int]) -> list[Row]:
    return conn.execute(f"SELECT {ENTRY} FROM user_movies WHERE user_id = %s AND movie_id = ANY(%s) ORDER BY movie_id",
                        (user_id, list(movie_ids))).fetchall()


def count_entries(conn: psycopg.Connection, user_id: int) -> int:
    return conn.execute("SELECT count(*) AS n FROM user_movies WHERE user_id = %s", (user_id,)).fetchone()["n"]


def set_entry(conn: psycopg.Connection, user_id: int, movie_id: int, status: str, watched_on: Optional[date],
              rating: Optional[int]) -> Row:
    """A film that changes list counts as newly added (for the "date added" sort); a rating change doesn't."""
    return conn.execute(f"""
        INSERT INTO user_movies (user_id, movie_id, status, watched_on, rating) VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id, movie_id) DO UPDATE SET
            added_at = CASE WHEN user_movies.status = EXCLUDED.status THEN user_movies.added_at ELSE now() END,
            status = EXCLUDED.status, watched_on = EXCLUDED.watched_on, rating = EXCLUDED.rating, updated_at = now()
        RETURNING {ENTRY}""", (user_id, movie_id, status, watched_on, rating)).fetchone()


def delete_entry(conn: psycopg.Connection, user_id: int, movie_id: int) -> bool:
    return conn.execute("DELETE FROM user_movies WHERE user_id = %s AND movie_id = %s", (user_id, movie_id)).rowcount > 0


def counts(conn: psycopg.Connection, user_id: int) -> dict[str, int]:
    return conn.execute("""SELECT count(*) FILTER (WHERE status = 'watched') AS watched,
                                  count(*) FILTER (WHERE status = 'plan_to_watch') AS plan_to_watch,
                                  (SELECT count(*) FROM comments WHERE user_id = %s) AS notes
                           FROM user_movies WHERE user_id = %s""", (user_id, user_id)).fetchone()


def notes_for(conn: psycopg.Connection, user_id: int, movie_id: int) -> list[Row]:
    return conn.execute(f"""SELECT {NOTE} FROM comments WHERE user_id = %s AND movie_id = %s
                            ORDER BY created_at DESC, id DESC""", (user_id, movie_id)).fetchall()


def notes_page(conn: psycopg.Connection, user_id: int, limit: int, offset: int) -> tuple[list[Row], int]:
    rows = conn.execute(f"""SELECT {NOTE} FROM comments WHERE user_id = %s ORDER BY created_at DESC, id DESC
                            LIMIT %s OFFSET %s""", (user_id, limit, offset)).fetchall()
    return rows, count_notes(conn, user_id)


def count_notes(conn: psycopg.Connection, user_id: int) -> int:
    return conn.execute("SELECT count(*) AS n FROM comments WHERE user_id = %s", (user_id,)).fetchone()["n"]


def add_note(conn: psycopg.Connection, user_id: int, movie_id: int, body: str) -> Row:
    return conn.execute(f"INSERT INTO comments (user_id, movie_id, body) VALUES (%s, %s, %s) RETURNING {NOTE}",
                        (user_id, movie_id, body)).fetchone()


def update_note(conn: psycopg.Connection, user_id: int, note_id: int, body: str) -> Optional[Row]:
    return conn.execute(f"""UPDATE comments SET body = %s, updated_at = now() WHERE id = %s AND user_id = %s
                            RETURNING {NOTE}""", (body, note_id, user_id)).fetchone()


def delete_note(conn: psycopg.Connection, user_id: int, note_id: int) -> bool:
    return conn.execute("DELETE FROM comments WHERE id = %s AND user_id = %s", (note_id, user_id)).rowcount > 0
