"""fresh.db's build (V1.2): the two windows, the quality filter, the details pull and the database file itself."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

import httpx
import pytest

from backend.app.services.fresh import build_fresh_db, discover_ids, keep_discovered, pull_details, windows
from ml.data.tmdb_client import TMDBClient
from tests.factories import TEST_CPI, film
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db, films 1-300)
from tests.test_pull import raw_movie

TODAY = date(2026, 10, 30)


def disc(movie_id: int, popularity: float = 50.0, **over) -> dict:
    return {"id": movie_id, "poster_path": "/p.jpg", "overview": "x", "adult": False, "popularity": popularity, **over}


class FakeTMDB:
    """Discover by date range (a list of results per window and page) and details; records what was asked."""

    def __init__(self, released: list[list[dict]], upcoming: list[list[dict]], not_found: set[int] = frozenset()):
        self.pages = {("2026-10-16", "2026-10-30"): released, ("2026-10-31", "2026-12-29"): upcoming}
        self.not_found, self.seen_ranges, self.discover_calls, self.detail_calls = set(not_found), set(), 0, []
        self.fail_discover = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path, q = request.url.path, request.url.params
        if path == "/3/discover/movie":
            if self.fail_discover:
                return httpx.Response(401)
            self.discover_calls += 1
            key = (q["primary_release_date.gte"], q["primary_release_date.lte"])
            self.seen_ranges.add(key)
            assert q["sort_by"] == "popularity.desc" and q["include_adult"] == "false"
            pages, page = self.pages[key], int(q["page"])
            return httpx.Response(200, json={"page": page, "total_pages": len(pages),
                                             "results": pages[page - 1] if page <= len(pages) else []})
        movie_id = int(path.rsplit("/", 1)[1])
        self.detail_calls.append(movie_id)
        if movie_id in self.not_found:
            return httpx.Response(404)
        return httpx.Response(200, json={**raw_movie(movie_id), "release_date": "2026-10-25", "status": "Released"})


def client_for(fake: FakeTMDB) -> TMDBClient:
    return TMDBClient("t", rate=10_000, backoff_base=0, transport=httpx.MockTransport(fake))


def columns(con: sqlite3.Connection, table: str) -> list[tuple]:
    return [tuple(r[1:3]) for r in con.execute(f"PRAGMA table_info({table})")]


def test_windows_edges():
    w = windows(TODAY)
    assert w["released"] == (date(2026, 10, 16), date(2026, 10, 30))
    assert w["upcoming"] == (date(2026, 10, 31), date(2026, 12, 29))


def test_keep_discovered_quality_filter():
    ok = disc(1, 5.0)
    rows = [ok, {**ok, "id": 2, "poster_path": None}, {**ok, "id": 3, "overview": " "}, {**ok, "id": 4, "adult": True},
            {**ok, "id": 5, "popularity": 4.9}, ok]
    assert keep_discovered(rows, 5.0) == [1]


async def test_discover_ids_queries_both_windows_and_stops_under_the_floor():
    fake = FakeTMDB(released=[[disc(1), disc(2, 20)], [disc(3, 4.0)], [disc(99)]],   # page 2 ends under the floor
                    upcoming=[[disc(10), disc(11, 90)]])
    async with client_for(fake) as client:
        ids = await discover_ids(client, TODAY, 5.0, pages=5)
    assert fake.seen_ranges == {("2026-10-16", "2026-10-30"), ("2026-10-31", "2026-12-29")}
    assert ids == [1, 2, 10, 11] and fake.discover_calls == 3   # page 3 of the first window was never asked


async def test_discover_ids_respects_the_page_cap():
    fake = FakeTMDB(released=[[disc(i)] for i in range(1, 9)], upcoming=[[disc(100)]])
    async with client_for(fake) as client:
        ids = await discover_ids(client, TODAY, 5.0, pages=2)
    assert ids == [1, 2, 100]


async def test_pull_details_skips_unknown_and_failed_films():
    fake = FakeTMDB([[]], [[]], not_found={2})
    async with client_for(fake) as client:
        records = await pull_details(client, [1, 2, 3], "2026-10-30T10:00:00+00:00")
    assert sorted(r["id"] for r in records) == [1, 3] and records[0]["pulled_at"] == "2026-10-30T10:00:00+00:00"


def test_build_fresh_db_has_the_schema_of_the_main_database(tmp_path, db):  # noqa: F811
    n = build_fresh_db([film(900001, status="Planned", release_date="2026-11-20")], TEST_CPI, tmp_path / "fresh.db",
                       {"refreshed_at": "2026-10-30T10:00:00+00:00"})
    assert n == 1
    fresh, main = sqlite3.connect(tmp_path / "fresh.db"), sqlite3.connect(db / "movies.db")
    for table in ("movies", "movie_genres", "movie_cast", "movie_crew", "people", "genres", "companies", "keywords",
                  "collections", "movie_companies", "movie_keywords", "movie_countries", "movie_languages", "movies_fts"):
        assert columns(fresh, table) == columns(main, table), table
    assert json.loads(fresh.execute("SELECT value FROM meta WHERE key='refreshed_at'").fetchone()[0])
    assert fresh.execute("SELECT status, split FROM movies WHERE id = 900001").fetchone() == ("Planned", "later")
    assert fresh.execute("SELECT COUNT(*) FROM movies_fts WHERE movies_fts MATCH 'film'").fetchone()[0] == 1


def test_build_fresh_db_replaces_an_old_file(tmp_path):
    path = tmp_path / "fresh.db"
    build_fresh_db([film(1), film(2)], TEST_CPI, path, {})
    assert build_fresh_db([film(3)], TEST_CPI, path, {}) == 1
    assert [r[0] for r in sqlite3.connect(path).execute("SELECT id FROM movies")] == [3]
