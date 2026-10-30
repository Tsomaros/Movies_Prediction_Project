"""Films released in the last 14 days and the next 60, live from TMDB through a 6-hour in-memory cache (V1.2).

Mapping (pure functions):
    windows(today)                 -> {"new": (today - 14, today), "upcoming": (today + 1, today + 60)}
    map_results(raw, genres, today, min_pop, min_votes)
                                   -> LiveMovie dicts from TMDB discover results: no poster, empty overview, adult or
                                      under min_pop popularity dropped, duplicates removed, genre ids as names, a status
                                      (out_today / new / upcoming) and a score only from min_votes votes
    sort_new(items), sort_upcoming(items)
                                   -> newest first / soonest first, then the more popular
    match_live(items, q, limit=3)  -> the films whose title or original title has a word starting with each word of q
                                      (accent- and case-insensitive); films already in our database are left out

Cache:
    LiveCache(fetch, ids_present, ttl_s, now=...)
        await get()                -> {fetched_at, stale, new, upcoming}: the cached answer while it is fresh, else one
                                      refresh at a time (a lock). A failed refresh serves the last good copy marked stale,
                                      or empty lists; a failure is not retried for RETRY_AFTER_FAILURE_S
        peek()                     -> the cached answer or None, with no I/O (search never waits for TMDB)
    warm_up(cache)                 -> the first refresh at startup; a failure is only logged
    fetch_discover(client, token, today, min_pop)
                                   -> (new, upcoming) from TMDB's /discover/movie, 5 pages of 20 each, in parallel

`movie_id` of a LiveMovie is set when the film is in our database (our film ids are TMDB ids).
Nothing is stored: live films exist only in memory.
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

import httpx

from backend.app.services.posters import poster

log = logging.getLogger("uvicorn.error")

DISCOVER_URL = "https://api.themoviedb.org/3/discover/movie"
NEW_DAYS, UPCOMING_DAYS = 14, 60
MAX_PAGES = 5  # 100 films a list
CALL_TIMEOUT_S = 4.0
REFRESH_TIMEOUT_S = 8.0
RETRY_AFTER_FAILURE_S = 60
GENRES = {28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime", 99: "Documentary", 18: "Drama",
          10751: "Family", 14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music", 9648: "Mystery",
          10749: "Romance", 878: "Science Fiction", 10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western"}

Fetch = Callable[[date], Awaitable[tuple[list[dict[str, Any]], list[dict[str, Any]]]]]


class LiveUnavailable(Exception):
    """TMDB can't be asked (no token) or didn't answer."""


def windows(today: date) -> dict[str, tuple[date, date]]:
    return {"new": (today - timedelta(days=NEW_DAYS), today),
            "upcoming": (today + timedelta(days=1), today + timedelta(days=UPCOMING_DAYS))}


def map_results(raw: list[dict[str, Any]], genres: dict[int, str], today: date, min_pop: float,
                min_votes: int) -> list[dict[str, Any]]:
    out, seen = [], set()
    for r in raw:
        release = r.get("release_date")
        if (r["id"] in seen or not r.get("poster_path") or not (r.get("overview") or "").strip() or r.get("adult")
                or (r.get("popularity") or 0) < min_pop or not release):
            continue
        seen.add(r["id"])
        votes = r.get("vote_count") or 0
        released = date.fromisoformat(release)
        out.append({
            "tmdb_id": r["id"], "movie_id": None, "title": r["title"],
            "original_title": r.get("original_title") or r["title"], "release_date": release, "year": released.year,
            "poster": poster(r["poster_path"]), "overview": r["overview"].strip(),
            "genres": [genres[g] for g in r.get("genre_ids", []) if g in genres],
            "vote_average": r.get("vote_average") if votes >= min_votes else None, "vote_count": votes,
            "popularity": r.get("popularity"),
            "status": "out_today" if released == today else "new" if released < today else "upcoming",
        })
    return out


def sort_new(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda f: (f["release_date"], f["popularity"] or 0), reverse=True)


def sort_upcoming(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda f: (f["release_date"], -(f["popularity"] or 0)))


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", _fold(text))


def match_live(items: list[dict[str, Any]], q: str, limit: int = 3) -> list[dict[str, Any]]:
    wanted = _words(q)
    if not wanted:
        return []
    out = []
    for f in items:
        if f["movie_id"] is not None:
            continue
        have = _words(f["title"]) + _words(f["original_title"])
        if all(any(h.startswith(w) for h in have) for w in wanted):
            out.append(f)
            if len(out) == limit:
                break
    return out


async def _page(client: httpx.AsyncClient, token: str, window: tuple[date, date], page: int) -> list[dict[str, Any]]:
    params = {"primary_release_date.gte": window[0].isoformat(), "primary_release_date.lte": window[1].isoformat(),
              "include_adult": "false", "include_video": "false", "sort_by": "popularity.desc", "page": page,
              "language": "en-US"}
    r = await client.get(DISCOVER_URL, params=params, headers={"Authorization": f"Bearer {token}"},
                         timeout=CALL_TIMEOUT_S)
    r.raise_for_status()
    return r.json().get("results", [])


async def fetch_discover(client: httpx.AsyncClient, token: str | None, today: date, min_pop: float,
                         min_votes: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not token:
        raise LiveUnavailable("no TMDB token")
    w = windows(today)
    try:
        pages = await asyncio.gather(*[_page(client, token, w[name], p) for name in ("new", "upcoming")
                                       for p in range(1, MAX_PAGES + 1)])
    except (httpx.HTTPError, ValueError) as e:
        raise LiveUnavailable(str(e)) from e
    lists = [[r for page in pages[i * MAX_PAGES:(i + 1) * MAX_PAGES] for r in page] for i in range(2)]
    new, upcoming = (map_results(raw, GENRES, today, min_pop, min_votes) for raw in lists)
    return sort_new(new), sort_upcoming(upcoming)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LiveCache:
    def __init__(self, fetch: Fetch, ids_present: Callable[[list[int]], set[int]], ttl_s: int,
                 now: Callable[[], datetime] = _now):
        self._fetch, self._ids_present, self._ttl, self._now = fetch, ids_present, ttl_s, now
        self._lock = asyncio.Lock()
        self._entry: Optional[dict[str, Any]] = None  # {fetched_at: datetime, new, upcoming}
        self._stale = False
        self._failed_at: Optional[datetime] = None

    def _view(self) -> dict[str, Any]:
        e = self._entry
        if e is None:
            return {"fetched_at": None, "stale": True, "new": [], "upcoming": []}
        return {"fetched_at": e["fetched_at"].isoformat(), "stale": self._stale, "new": e["new"],
                "upcoming": e["upcoming"]}

    def _fresh(self) -> bool:
        return self._entry is not None and not self._stale and (self._now() - self._entry["fetched_at"]).total_seconds() < self._ttl

    def peek(self) -> Optional[dict[str, Any]]:
        return self._view() if self._entry is not None else None

    async def get(self) -> dict[str, Any]:
        if self._fresh():
            return self._view()
        if self._lock.locked() and self._entry is not None:  # someone is refreshing: serve what we have
            return self._view()
        async with self._lock:
            if self._fresh():
                return self._view()
            if self._failed_at is not None and (self._now() - self._failed_at).total_seconds() < RETRY_AFTER_FAILURE_S:
                return self._view()
            try:
                new, upcoming = await asyncio.wait_for(self._fetch(self._now().date()), REFRESH_TIMEOUT_S)
                ids = [f["tmdb_id"] for f in new + upcoming]
                present = await asyncio.to_thread(self._ids_present, ids) if ids else set()
                for f in new + upcoming:
                    f["movie_id"] = f["tmdb_id"] if f["tmdb_id"] in present else None
                self._entry, self._stale, self._failed_at = {"fetched_at": self._now(), "new": new, "upcoming": upcoming}, False, None
            except Exception as e:  # TMDB down, slow or answering nonsense: the page must never break
                log.warning("live new/upcoming refresh failed: %s", e)
                self._stale, self._failed_at = True, self._now()
            return self._view()


async def warm_up(cache: LiveCache) -> None:
    try:
        await cache.get()
    except Exception as e:  # never blocks or stops the start
        log.warning("live new/upcoming warm-up failed: %s", e)
