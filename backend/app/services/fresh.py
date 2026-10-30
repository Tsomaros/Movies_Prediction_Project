"""fresh.db: the app's small database of new and upcoming films (V1.2).

A film released in the last 14 days or due in the next 60 is stored like any other film, in a SQLite file with the
same schema as the movie tables of data/movies.db, so every page that works for a film from 1995 works for one from
last week. The API attaches the file next to movies.db (backend/app/fresh_views.py); no model, track record,
comparable or career forecast ever reads it.

Building it (this module's pure parts and the async pull):
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
    build_fresh_db(records, cpi, path, meta)
                                   -> writes a complete database at `path` with the existing clean() (unreleased
                                      films kept) and write_db(); returns the number of films

Keeping it fresh:
    Refresher(fresh_path, main_db, token, min_popularity, ttl_s, listed, clock, make_client=TMDBClient)
        due()          -> True when a refresh should start: a token is set, none is running, the last success is
                          older than ttl_s (or there was none) and the last failure is over 60 s ago
        maybe_start()  -> starts run() as a background task when due() (never waits for it), else None
        await run()    -> {"films", "listed", "skipped"}: pulls the two windows plus every listed film (in a user's
                          list or notes) that movies.db lacks, writes fresh.tmp.db and replaces fresh.db with it in
                          one step. Any failure keeps the old file, is logged once and backs off; nothing is raised
        status()       -> {"refreshed_at", "films"} (None before the first refresh)
    python -m backend.app.services.fresh --once   -> one refresh with the settings of .env (data/fresh.db)

Nothing here is stored in git or in the Docker image: the file lives where FRESH_DB says and is rebuilt by the
Refresher at startup and every 6 hours.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from ml.data.build_db import write_db
from ml.data.clean import clean, load_cpi
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


def build_fresh_db(records: list[dict[str, Any]], cpi: dict[int, float], path: Path, meta: dict[str, Any]) -> int:
    tables, _ = clean(records, cpi, keep_unreleased=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA journal_mode = OFF")  # a new file: if this fails it is deleted by the caller
        con.execute("PRAGMA synchronous = OFF")
        write_db(con, tables, meta)
    finally:
        con.close()
    return len(tables["movies"])


BACKOFF_S = 60


class Refresher:
    def __init__(self, fresh_path: Path, main_db: Path, token: str | None, min_popularity: float, ttl_s: int,
                 listed: Callable[[], set[int]] | None, clock: Callable[[], datetime],
                 make_client: Callable[[str], TMDBClient] = TMDBClient):
        self.fresh_path, self.main_db, self.token = Path(fresh_path), Path(main_db), token
        self.min_popularity, self.ttl_s, self.listed, self.clock, self.make_client = min_popularity, ttl_s, listed, clock, make_client
        self._running, self._task = False, None
        self._last_ok: datetime | None = None
        self._failed_at: datetime | None = None
        self._status = {"refreshed_at": None, "films": None}

    @property
    def tmp_path(self) -> Path:
        return self.fresh_path.with_name(self.fresh_path.stem + ".tmp.db")

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

    def _in_main(self, ids: set[int]) -> set[int]:
        from backend.app.deps import connect_read_only
        from backend.app.repo.movies import ids_present

        found: set[int] = set()
        with closing(connect_read_only(self.main_db)) as con:
            wanted = sorted(ids)
            for i in range(0, len(wanted), 500):
                found |= ids_present(con, wanted[i:i + 500])
        return found

    def _write(self, records: list[dict[str, Any]], refreshed_at: str) -> int:
        self.tmp_path.unlink(missing_ok=True)
        try:
            n = build_fresh_db(records, load_cpi(), self.tmp_path, {"refreshed_at": refreshed_at})
            os.replace(self.tmp_path, self.fresh_path)  # one step: a request sees the old file or the new one
        except BaseException:
            self.tmp_path.unlink(missing_ok=True)
            raise
        return n

    async def run(self) -> dict[str, Any]:
        self._running = True
        now = self.clock()
        try:
            async with self.make_client(self.token) as client:
                window = await discover_ids(client, now.date(), self.min_popularity)
                listed = await asyncio.to_thread(self._listed)
                known = await asyncio.to_thread(self._in_main, listed) if listed else set()
                extra = sorted(listed - known - set(window))
                wanted = window + extra
                records = await pull_details(client, wanted, now.isoformat(timespec="seconds"))
            films = await asyncio.to_thread(self._write, records, now.isoformat(timespec="seconds"))
        except Exception as e:  # TMDB or disk trouble: keep the old file, try again after the back-off
            log.warning("fresh: refresh failed (%s: %s)", type(e).__name__, e)
            self._failed_at = now
            return {"films": 0, "listed": 0, "skipped": 0, "error": str(e)}
        finally:
            self._running = False
        self._last_ok, self._failed_at = now, None
        self._status = {"refreshed_at": now.isoformat(timespec="seconds"), "films": films}
        log.info("fresh: %d films (%d listed, %d skipped)", films, len(extra), len(wanted) - len(records))
        return {"films": films, "listed": len(extra), "skipped": len(wanted) - len(records)}


def _once() -> None:
    from backend.app.settings import Settings
    from backend.app.userdb.pool import make_pool
    from backend.app.userdb import repo as userdb

    settings = Settings.from_env()
    pool = make_pool(settings.user_database_url) if settings.user_database_url else None

    def listed() -> set[int]:
        with pool.connection() as conn:
            return userdb.listed_movie_ids(conn)

    refresher = Refresher(settings.fresh_path or Path("data/fresh.db"), settings.db_path, settings.tmdb_read_token,
                          settings.fresh_min_popularity, settings.fresh_ttl_s, listed if pool else None,
                          lambda: datetime.now(timezone.utc))
    if not refresher.token:
        raise SystemExit("TMDB_READ_TOKEN is not set")
    print(json.dumps(asyncio.run(refresher.run())))
    if pool:
        pool.close()


if __name__ == "__main__":
    argparse.ArgumentParser(description="Build data/fresh.db once.").add_argument("--once", action="store_true", required=True)
    _once()
