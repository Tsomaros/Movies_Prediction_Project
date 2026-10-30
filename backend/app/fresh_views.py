"""Reading movies.db and fresh.db as one database (V1.2).

    attach_fresh(con, fresh_path) -> True when fresh.db exists and was attached as `fresh` (read-only) with the TEMP
                                     views below created; False (nothing changed) when there is no file, or when it
                                     can't be opened
    has_fresh(con)                -> whether this connection has fresh attached

SQLite looks an unqualified table name up in `temp` first, so a TEMP view with the name of a main table makes all
the existing SQL read both files without changing it:
- movies and every movie_* table (SHADOWED_MOVIE_TABLES, SHADOWED_CHILD_TABLES): all fresh rows, plus the main rows
  of films that are not in fresh.movies (a film in both files shows its fresh copy, with the current votes);
- genres, companies, keywords, collections and people (SHADOWED_LOOKUPS): all main rows, plus the fresh rows whose
  id main doesn't have;
- person_details, meta, features, the FTS tables and the training views are not shadowed.

FTS5 can't be matched through a view, so the text search asks both movies_fts tables itself (repo/movies.py).
Only the API's per-request connection (deps.get_db) attaches: the models, the comparables, the career data and the
startup lookups open movies.db alone and never see fresh.db.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SHADOWED_MOVIE_TABLES = ("movies",)
SHADOWED_CHILD_TABLES = ("movie_genres", "movie_companies", "movie_keywords", "movie_cast", "movie_crew",
                         "movie_countries", "movie_languages")
SHADOWED_LOOKUPS = ("genres", "companies", "keywords", "collections", "people")


def has_fresh(con: sqlite3.Connection) -> bool:
    return any(row[1] == "fresh" for row in con.execute("PRAGMA database_list"))


_COLUMNS: dict[str, str] = {}  # the schema is fixed for a build of movies.db: read each table's columns once


def _columns(con: sqlite3.Connection, table: str) -> str:
    if table not in _COLUMNS:
        _COLUMNS[table] = ", ".join(f'"{r[1]}"' for r in con.execute(f"PRAGMA main.table_info({table})"))
    return _COLUMNS[table]


def attach_fresh(con: sqlite3.Connection, fresh_path: Path | None) -> bool:
    if fresh_path is None or not Path(fresh_path).is_file():
        return False
    try:
        con.execute("ATTACH DATABASE ? AS fresh", (f"file:{Path(fresh_path).resolve().as_posix()}?mode=ro",))
        views = []
        fresh_films = "SELECT id FROM fresh.movies"
        for table in SHADOWED_MOVIE_TABLES:
            cols = _columns(con, table)
            views.append(f"CREATE TEMP VIEW {table} AS SELECT {cols} FROM fresh.{table} "
                         f"UNION ALL SELECT {cols} FROM main.{table} WHERE id NOT IN ({fresh_films})")
        for table in SHADOWED_CHILD_TABLES:
            cols = _columns(con, table)
            views.append(f"CREATE TEMP VIEW {table} AS SELECT {cols} FROM fresh.{table} "
                         f"UNION ALL SELECT {cols} FROM main.{table} WHERE movie_id NOT IN ({fresh_films})")
        for table in SHADOWED_LOOKUPS:
            cols = _columns(con, table)
            views.append(f"CREATE TEMP VIEW {table} AS SELECT {cols} FROM main.{table} "
                         f"UNION ALL SELECT {cols} FROM fresh.{table} WHERE id NOT IN (SELECT id FROM main.{table})")
        for sql in views:
            con.execute(sql)
    except sqlite3.Error:  # an unreadable file: behave as if there were none
        if has_fresh(con):
            for table in (*SHADOWED_MOVIE_TABLES, *SHADOWED_CHILD_TABLES, *SHADOWED_LOOKUPS):
                con.execute(f"DROP VIEW IF EXISTS temp.{table}")
            con.execute("DETACH DATABASE fresh")
        return False
    return True
