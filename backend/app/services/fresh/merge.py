"""Merging pulled films into movies.db (V1.3).

    merge_into(con, records, cpi, refreshed_at)
                                   -> {"films", "removed", "skipped"}: in one transaction, cleans the records with the
                                      existing clean() (unreleased films kept), skips any dated 2025 or earlier and
                                      never replaces a film dated 2025 or earlier, replaces each film's rows (FTS
                                      included), adds only lookup rows the database lacks, deletes added films no
                                      longer wanted and the people left without a film. Any error rolls it all back
    open_for_writing(path)         -> a read-write connection that waits up to 30 s for readers (never a new file)
    ensure_tables(con)             -> creates fresh_films and fresh_people when missing
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from ml.data.build_db import FRESH_TABLES, _columns, _rows
from ml.data.clean import MODEL_DATA_MAX_YEAR, clean

LOOKUPS = ("genres", "companies", "keywords", "collections", "people")
LINKS = ("movie_genres", "movie_companies", "movie_keywords", "movie_cast", "movie_crew", "movie_countries",
         "movie_languages")
LINK_KEYS = {"movie_genres": ("genre_id", "genres"), "movie_companies": ("company_id", "companies"),
             "movie_keywords": ("keyword_id", "keywords"), "movie_cast": ("person_id", "people"),
             "movie_crew": ("person_id", "people")}
FTS_COLUMNS = "title, original_title, overview"


def _in(ids: list[int]) -> str:
    return f"({','.join('?' * len(ids))})"


def _remove(con: sqlite3.Connection, ids: list[int]) -> None:
    """Delete films and their links. The FTS index mirrors movies (content='movies'), so its 'delete' must be sent
    with the old values before the rows go."""
    if not ids:
        return
    con.execute(f"INSERT INTO movies_fts(movies_fts, rowid, {FTS_COLUMNS}) SELECT 'delete', id, {FTS_COLUMNS} "
                f"FROM movies WHERE id IN {_in(ids)}", ids)
    for table in LINKS:
        con.execute(f"DELETE FROM {table} WHERE movie_id IN {_in(ids)}", ids)
    con.execute(f"DELETE FROM movies WHERE id IN {_in(ids)}", ids)


def _insert(con: sqlite3.Connection, table: str, df: pd.DataFrame, ignore: bool = False) -> None:
    columns = _columns(con, table)
    con.executemany(f"INSERT {'OR IGNORE ' if ignore else ''}INTO {table} ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' * len(columns))})", _rows(df, columns))


def ensure_tables(con: sqlite3.Connection) -> None:
    for sql in FRESH_TABLES.strip().split(";")[:-1]:  # execute, not executescript, which would commit
        con.execute(sql)


def _check_links(con: sqlite3.Connection, ids: list[int]) -> None:
    """write_db's foreign-key check, for the merged films only (PRAGMA foreign_key_check takes 16 s on the real file)."""
    broken = con.execute(f"SELECT COUNT(*) FROM movies WHERE id IN {_in(ids)} AND collection_id IS NOT NULL "
                         f"AND collection_id NOT IN (SELECT id FROM collections)", ids).fetchone()[0]
    for table, (column, lookup) in LINK_KEYS.items():
        broken += con.execute(f"SELECT COUNT(*) FROM {table} WHERE movie_id IN {_in(ids)} "
                              f"AND {column} NOT IN (SELECT id FROM {lookup})", ids).fetchone()[0]
    if broken:
        raise RuntimeError(f"{broken} merged rows point at missing ids")


def merge_into(con: sqlite3.Connection, records: list[dict[str, Any]], cpi: dict[int, float],
               refreshed_at: str) -> dict[str, int]:
    """One refresh in one transaction (the caller's connection: read-write, isolation_level=None)."""
    tables, _ = clean(records, cpi, keep_unreleased=True)
    films = tables["movies"]
    later = films["year"].isna() | (films["year"] > MODEL_DATA_MAX_YEAR)  # the models read year <= 2025 only
    con.execute("BEGIN IMMEDIATE")
    try:
        # nor is a film the models read ever replaced (a 2025 film TMDB has moved to 2026, say)
        candidates = [int(i) for i in films.loc[later, "id"]]
        modelled = {r[0] for r in con.execute(f"SELECT id FROM movies WHERE id IN {_in(candidates)} "
                                              f"AND year <= {MODEL_DATA_MAX_YEAR}", candidates)} if candidates else set()
        later &= ~films["id"].isin(modelled)
        ids = sorted(int(i) for i in films.loc[later, "id"])
        ensure_tables(con)
        tracked = dict(con.execute("SELECT id, added FROM fresh_films").fetchall())
        stale = [i for i, added in tracked.items() if added and i not in set(ids)]
        _remove(con, stale)
        present: set[int] = set()
        if ids:
            present = {r[0] for r in con.execute(f"SELECT id FROM movies WHERE id IN {_in(ids)}", ids)}
            people_before = {r[0] for r in con.execute("SELECT id FROM people WHERE id IN (SELECT value FROM "
                                                       "json_each(?))", (json.dumps(tables["people"]["id"].tolist()),))}
            _remove(con, sorted(present))
            for table in LOOKUPS:
                _insert(con, table, tables[table], ignore=True)  # the build's names win, as the views did in V1.2
            _insert(con, "movies", films[later])
            for table in LINKS:
                _insert(con, table, tables[table][tables[table]["movie_id"].isin(ids)])
            con.execute(f"INSERT INTO movies_fts(rowid, {FTS_COLUMNS}) SELECT id, {FTS_COLUMNS} FROM movies "
                        f"WHERE id IN {_in(ids)}", ids)
            _check_links(con, ids)
            new_people = sorted(set(int(i) for i in tables["people"]["id"]) - people_before)
            con.executemany("INSERT OR IGNORE INTO fresh_people (id) VALUES (?)", [(i,) for i in new_people])
        con.execute("DELETE FROM fresh_films")
        con.executemany("INSERT INTO fresh_films (id, added) VALUES (?, ?)",
                        [(i, tracked.get(i, int(i not in present))) for i in ids])
        # people the refresher added who are left without a film
        con.execute("DELETE FROM people WHERE id IN (SELECT id FROM fresh_people) "  # NOT EXISTS: by the person indexes
                    "AND NOT EXISTS (SELECT 1 FROM movie_cast c WHERE c.person_id = people.id) "
                    "AND NOT EXISTS (SELECT 1 FROM movie_crew c WHERE c.person_id = people.id)")
        con.execute("DELETE FROM fresh_people WHERE id NOT IN (SELECT id FROM people)")
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('fresh_refreshed_at', ?)", (json.dumps(refreshed_at),))
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    return {"films": len(ids), "removed": len(stale), "skipped": int((~later).sum())}


def open_for_writing(path: Path) -> sqlite3.Connection:
    """The refresher's connection: it waits up to 30 s for readers to finish before it commits."""
    if not Path(path).is_file():
        raise FileNotFoundError(path)  # never a new empty database
    return sqlite3.connect(path, timeout=30, isolation_level=None)
