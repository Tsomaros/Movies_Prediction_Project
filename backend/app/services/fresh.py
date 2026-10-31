"""New and upcoming films, merged into movies.db (V1.2; one database since V1.3).

A film released in the last 14 days or due in the next 60 is stored like any other film, in the movie tables of
movies.db itself, so every page that works for a film from 1995 works for one from last week. Only films dated after
MODEL_DATA_MAX_YEAR (2025), or not dated yet, are ever written, and every model, track record, comparable and the
career backtest reads year <= 2025 only, so no model sees them. The table fresh_films records the ids the refresher
wrote (`added` = 1: the build didn't have the film), fresh_people the people it added (they have no page).

Pulling (this module's pure parts and the async pull):
    windows(today)                 -> {"released": (today - 14, today), "upcoming": (today + 1, today + 60)}
    keep_discovered(results, min_popularity)
                                   -> the ids of the discover results that pass the quality filter (a poster, an
                                      overview, not adult, popularity at the floor or above), in order, once each
    await discover_ids(client, today, min_popularity, pages=5)
                                   -> the ids of both windows from /discover/movie (popularity order, up to 5 pages a
                                      window, stopping when a page's last film is under the floor)
    await pull_details(client, ids, pulled_at)
                                   -> one trimmed record per id (the same details call and trim as the backfill); a
                                      film TMDB doesn't know (404) or can't be fetched is left out

Merging:
    merge_into(con, records, cpi, refreshed_at)
                                   -> {"films", "removed", "skipped"}: in one transaction, cleans the records with the
                                      existing clean() (unreleased films kept), skips any dated 2025 or earlier,
                                      replaces each film's rows (FTS included), adds only lookup rows the database
                                      lacks, deletes added films no longer wanted and the people left without a film.
                                      Any error rolls it all back
    open_for_writing(path)         -> a read-write connection that waits up to 30 s for readers (never a new file)
    ensure_tables(con)             -> creates fresh_films and fresh_people when missing

Keeping it fresh:
    Refresher(db_path, token, min_popularity, ttl_s, listed, clock, make_client=TMDBClient)
        prepare()      -> before serving: one read-write open (rolls back a merge a crash left half done) and the
                          two tables; False, and the refresh off, without a token or when the file can't be written
        due()          -> True when a refresh should start: a token is set, none is running, the last success is
                          older than ttl_s (or there was none) and the last failure is over 60 s ago
        maybe_start()  -> starts run() as a background task when due() (never waits for it), else None
        await run()    -> {"films", "listed", "skipped", "removed"}: pulls the two windows plus every listed film (in
                          a user's list or notes) the build lacks and merges them. Any failure keeps the database as
                          it was, is logged once and backs off; nothing is raised
        status()       -> {"refreshed_at", "films"} (None before the first refresh)
    python -m backend.app.services.fresh --once   -> one merge into MOVIES_DB with the settings of .env

The refresh runs only with FRESH_REFRESH=1 (the image), so `make api` never changes the database training reads.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
import pandas as pd

from ml.data.build_db import FRESH_TABLES, _columns, _rows
from ml.data.clean import MODEL_DATA_MAX_YEAR, clean, load_cpi
from ml.data.pull import DETAILS_PARAMS, trim_movie
from ml.data.tmdb_client import TMDBClient, TMDBError

log = logging.getLogger("uvicorn.error")

RELEASED_DAYS, UPCOMING_DAYS = 14, 60
MAX_PAGES = 5  # 20 films a page


def windows(today: date) -> dict[str, tuple[date, date]]:
    return {"released": (today - timedelta(days=RELEASED_DAYS), today),
            "upcoming": (today + timedelta(days=1), today + timedelta(days=UPCOMING_DAYS))}


def passes(film: dict[str, Any], min_popularity: float) -> bool:
    return bool(film.get("poster_path") and (film.get("overview") or "").strip() and not film.get("adult")
                and (film.get("popularity") or 0) >= min_popularity)


def keep_discovered(results: list[dict[str, Any]], min_popularity: float) -> list[int]:
    ids: list[int] = []
    for film in results:
        if film["id"] not in ids and passes(film, min_popularity):
            ids.append(film["id"])
    return ids


async def _window_ids(client: TMDBClient, window: tuple[date, date], min_popularity: float, pages: int) -> list[int]:
    found: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        body = await client.get("/discover/movie", {
            "primary_release_date.gte": window[0].isoformat(), "primary_release_date.lte": window[1].isoformat(),
            "sort_by": "popularity.desc", "include_adult": "false", "include_video": "false", "page": page})
        results = (body or {}).get("results", [])
        found += results
        if not results or (results[-1].get("popularity") or 0) < min_popularity or page >= (body or {}).get("total_pages", 1):
            break  # sorted by popularity: nothing after a page that ends under the floor can pass
    return keep_discovered(found, min_popularity)


async def discover_ids(client: TMDBClient, today: date, min_popularity: float, pages: int = MAX_PAGES) -> list[int]:
    both = await asyncio.gather(*(_window_ids(client, w, min_popularity, pages) for w in windows(today).values()))
    return list(dict.fromkeys(i for ids in both for i in ids))


async def pull_details(client: TMDBClient, ids: list[int], pulled_at: str) -> list[dict[str, Any]]:
    async def one(movie_id: int) -> dict[str, Any] | None:
        try:
            raw = await client.get(f"/movie/{movie_id}", DETAILS_PARAMS)
        except (TMDBError, httpx.HTTPError) as e:  # left out; the next refresh tries again
            log.warning("fresh: film %s skipped: %s", movie_id, e)
            return None
        return None if raw is None else trim_movie(raw, pulled_at)

    return [r for r in await asyncio.gather(*(one(i) for i in ids)) if r is not None]


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


BACKOFF_S = 60


class Refresher:
    def __init__(self, db_path: Path, token: str | None, min_popularity: float, ttl_s: int,
                 listed: Callable[[], set[int]] | None, clock: Callable[[], datetime],
                 make_client: Callable[[str], TMDBClient] = TMDBClient):
        self.db_path, self.token = Path(db_path), token
        self.min_popularity, self.ttl_s, self.listed, self.clock, self.make_client = min_popularity, ttl_s, listed, clock, make_client
        self._running, self._task = False, None
        self._last_ok: datetime | None = None
        self._failed_at: datetime | None = None
        self._status = {"refreshed_at": None, "films": None}

    def prepare(self) -> bool:
        """Before serving: open the database read-write once, so SQLite rolls back a merge a crash left half done
        (a read-only connection can't), and make the two tables. A file that can't be written turns the refresh off."""
        if not self.token:
            return False
        try:
            with closing(open_for_writing(self.db_path)) as con:
                ensure_tables(con)
        except (OSError, sqlite3.Error) as e:
            log.warning("fresh: %s can't be written (%s); new films are off", self.db_path, e)
            self.token = None
            return False
        return True

    def due(self) -> bool:
        if not self.token or self._running:
            return False
        now = self.clock()
        if self._failed_at is not None and (now - self._failed_at).total_seconds() < BACKOFF_S:
            return False
        return self._last_ok is None or (now - self._last_ok).total_seconds() >= self.ttl_s

    def maybe_start(self) -> asyncio.Task | None:
        if not self.due():
            return None
        self._running = True  # at once, so a second call before the task has started finds it running
        self._task = asyncio.get_running_loop().create_task(self.run())
        return self._task

    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

    def _listed(self) -> set[int]:
        if self.listed is None:
            return set()
        try:
            return set(self.listed())
        except Exception as e:  # Postgres down: the windows still refresh
            log.warning("fresh: the listed films could not be read: %s", e)
            return set()

    def _in_build(self, ids: set[int]) -> set[int]:
        """The ids among them that the database has from its build (a film the refresher added is pulled again)."""
        from backend.app.deps import connect_read_only
        from backend.app.repo.movies import ids_present

        found: set[int] = set()
        with closing(connect_read_only(self.db_path)) as con:
            wanted = sorted(ids)
            for i in range(0, len(wanted), 500):
                part = wanted[i:i + 500]
                found |= ids_present(con, part) - {r[0] for r in con.execute(
                    f"SELECT id FROM fresh_films WHERE added AND id IN {_in(part)}", part)}
        return found

    def _write(self, records: list[dict[str, Any]], refreshed_at: str) -> dict[str, int]:
        with closing(open_for_writing(self.db_path)) as con:
            return merge_into(con, records, load_cpi(), refreshed_at)

    async def run(self) -> dict[str, Any]:
        self._running = True
        now = self.clock()
        try:
            async with self.make_client(self.token) as client:
                window = await discover_ids(client, now.date(), self.min_popularity)
                listed = await asyncio.to_thread(self._listed)
                known = await asyncio.to_thread(self._in_build, listed) if listed else set()
                extra = sorted(listed - known - set(window))
                wanted = window + extra
                records = await pull_details(client, wanted, now.isoformat(timespec="seconds"))
            merged = await asyncio.to_thread(self._write, records, now.isoformat(timespec="seconds"))
        except Exception as e:  # TMDB or disk trouble: the merge was rolled back; try again after the back-off
            log.warning("fresh: refresh failed (%s: %s)", type(e).__name__, e)
            self._failed_at = now
            return {"films": 0, "listed": 0, "skipped": 0, "removed": 0, "error": str(e)}
        finally:
            self._running = False
        self._last_ok, self._failed_at = now, None
        self._status = {"refreshed_at": now.isoformat(timespec="seconds"), "films": merged["films"]}
        skipped = len(wanted) - len(records) + merged["skipped"]  # not fetched, or dated 2025 or earlier
        log.info("fresh: %d films (%d listed, %d skipped, %d removed)", merged["films"], len(extra), skipped,
                 merged["removed"])
        return {"films": merged["films"], "listed": len(extra), "skipped": skipped, "removed": merged["removed"]}


def _once() -> None:
    from backend.app.settings import Settings
    from backend.app.userdb.pool import make_pool
    from backend.app.userdb import repo as userdb

    settings = Settings.from_env()
    pool = make_pool(settings.user_database_url) if settings.user_database_url else None

    def listed() -> set[int]:
        with pool.connection() as conn:
            return userdb.listed_movie_ids(conn)

    refresher = Refresher(settings.db_path, settings.tmdb_read_token, settings.fresh_min_popularity,
                          settings.fresh_ttl_s, listed if pool else None, lambda: datetime.now(timezone.utc))
    if not refresher.prepare():
        raise SystemExit("TMDB_READ_TOKEN is not set or the database can't be written")
    print(json.dumps(asyncio.run(refresher.run())))
    if pool:
        pool.close()


if __name__ == "__main__":
    argparse.ArgumentParser(description="Merge the new and upcoming films into MOVIES_DB once.").add_argument("--once", action="store_true", required=True)
    _once()
