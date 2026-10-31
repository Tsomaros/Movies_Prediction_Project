"""The new and upcoming films (V1.2): the two windows, the quality filter, the details pull, and their merge into
movies.db (V1.3): one transaction, later films only, the models' data untouched."""

from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing
from datetime import date

import httpx
import pytest

import backend.app.services.fresh as fresh
from backend.app.services.fresh import (discover_ids, keep_discovered, merge_into, open_for_writing, pull_details,
                                         windows)
from ml.features.build import database_stamp
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


@pytest.fixture
def movies_db(db, tmp_path):  # noqa: F811
    """A copy of the small movies.db (films 1-300, 2008-2022) to merge into."""
    shutil.copyfile(db / "movies.db", tmp_path / "movies.db")
    return tmp_path / "movies.db"


REFRESHED = "2026-10-30T10:00:00+00:00"
NEW_FACE = 990_001
CREDITS = {"cast": [{"id": 2001, "name": "Actor 1", "character": "Hero", "order": 0},
                    {"id": NEW_FACE, "name": "New Face", "character": "Friend", "order": 1}],
           "crew": [{"id": 1000, "name": "Director 0", "job": "Director"}]}


def merge(path, records) -> dict:
    with closing(open_for_writing(path)) as con:
        return merge_into(con, records, TEST_CPI, REFRESHED)


def query(path, sql, args=()):
    with closing(sqlite3.connect(path)) as con:
        return con.execute(sql, args).fetchall()


def ids_in(path) -> set[int]:
    return {r[0] for r in query(path, "SELECT id FROM fresh_films")}


def model_data(path) -> list:
    """What the models read: the training views and every film dated 2025 or earlier, with its links."""
    return [query(path, f"SELECT COUNT(*) FROM {v}") for v in ("v_train_revenue", "v_train_budget", "v_train_score")] + [
        query(path, "SELECT * FROM movies WHERE year <= 2025 ORDER BY id"),
        query(path, "SELECT c.* FROM movie_cast c JOIN movies m ON m.id = c.movie_id WHERE m.year <= 2025 ORDER BY 1, 2")]


def test_a_merged_film_is_an_ordinary_film_of_the_database(movies_db):
    out = merge(movies_db, [film(900_001, title="Zyxquest", status="Planned", release_date="2026-11-20", credits=CREDITS)])
    assert out == {"films": 1, "removed": 0, "skipped": 0}
    assert query(movies_db, "SELECT status, split FROM movies WHERE id = 900001") == [("Planned", "later")]
    assert query(movies_db, "SELECT id, added FROM fresh_films") == [(900_001, 1)]
    assert query(movies_db, "SELECT id FROM fresh_people") == [(NEW_FACE,)]  # Actor 1 was there already
    assert query(movies_db, "SELECT rowid FROM movies_fts WHERE movies_fts MATCH 'zyxquest'") == [(900_001,)]
    query(movies_db, "INSERT INTO movies_fts(movies_fts) VALUES ('integrity-check')")  # raises when the index is off
    assert json.loads(query(movies_db, "SELECT value FROM meta WHERE key = 'fresh_refreshed_at'")[0][0]) == REFRESHED


def test_the_models_data_and_the_stamp_never_change(movies_db):
    with closing(sqlite3.connect(movies_db)) as con:
        stamp = database_stamp(con)
    before, film5 = model_data(movies_db), query(movies_db, "SELECT * FROM movies WHERE id = 5")
    out = merge(movies_db, [film(900_001, release_date="2026-10-25"),
                            film(900_002, release_date="2025-12-20"),        # a 2025 film: the models' years
                            film(5, title="Moved", release_date="2026-10-20")])  # a build film TMDB moved to 2026
    assert out["skipped"] == 2 and ids_in(movies_db) == {900_001}
    assert model_data(movies_db) == before and query(movies_db, "SELECT * FROM movies WHERE id = 5") == film5
    with closing(sqlite3.connect(movies_db)) as con:
        assert database_stamp(con) == stamp


def test_a_film_that_left_the_windows_goes_with_its_new_people(movies_db):
    merge(movies_db, [film(900_001, release_date="2026-10-25", credits=CREDITS), film(900_002, release_date="2026-10-26")])
    out = merge(movies_db, [film(900_002, title="Renamed", release_date="2026-10-26")])
    assert out == {"films": 1, "removed": 1, "skipped": 0} and ids_in(movies_db) == {900_002}
    assert query(movies_db, "SELECT id FROM movies WHERE id = 900001") == []
    assert query(movies_db, "SELECT COUNT(*) FROM movie_cast WHERE movie_id = 900001") == [(0,)]
    assert query(movies_db, "SELECT id FROM people WHERE id = ?", (NEW_FACE,)) == []  # only in the film that went
    assert (NEW_FACE,) not in query(movies_db, "SELECT id FROM fresh_people")
    assert query(movies_db, "SELECT title FROM movies WHERE id = 900002") == [("Renamed",)]  # replaced, not doubled
    assert query(movies_db, "SELECT rowid FROM movies_fts WHERE movies_fts MATCH 'renamed'") == [(900_002,)]
    query(movies_db, "INSERT INTO movies_fts(movies_fts) VALUES ('integrity-check')")


def test_a_2026_film_of_the_build_is_updated_and_kept_when_it_leaves(movies_db):
    merge(movies_db, [film(900_001, release_date="2026-10-25", vote_count=10)])
    query_con = sqlite3.connect(movies_db)
    query_con.execute("UPDATE fresh_films SET added = 0")  # as if the build had it (Part A's 2026 films)
    query_con.commit()
    query_con.close()
    merge(movies_db, [film(900_001, release_date="2026-10-25", vote_count=99)])
    assert query(movies_db, "SELECT id, added FROM fresh_films") == [(900_001, 0)]
    assert merge(movies_db, [])["removed"] == 0
    assert query(movies_db, "SELECT vote_count FROM movies WHERE id = 900001") == [(99,)] and ids_in(movies_db) == set()


def test_a_failed_merge_changes_nothing(movies_db, monkeypatch):
    merge(movies_db, [film(900_001, release_date="2026-10-25")])
    before = movies_db.read_bytes()

    def broken(con, ids):
        raise RuntimeError("bad links")
    monkeypatch.setattr(fresh, "_check_links", broken)
    with pytest.raises(RuntimeError, match="bad links"):
        merge(movies_db, [film(900_002, release_date="2026-10-26")])
    assert movies_db.read_bytes() == before


def test_the_writer_never_creates_a_database(tmp_path):
    with pytest.raises(FileNotFoundError):
        open_for_writing(tmp_path / "nope.db")
    assert not (tmp_path / "nope.db").exists()
