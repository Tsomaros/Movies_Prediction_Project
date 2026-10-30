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

Nothing here is stored in git or in the Docker image: the file lives where FRESH_DB says and is rebuilt by the
Refresher (the rest of this module) at startup and every 6 hours.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

from ml.data.build_db import write_db
from ml.data.clean import clean
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
