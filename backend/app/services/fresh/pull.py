"""Pulling the new and upcoming films from TMDB (V1.2).

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
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx

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
