"""GET /movies/new-and-upcoming and the live matches on GET /movies?q= (V1.2), over HTTP with a fake cache."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import API_PREFIX, Settings
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db, films 1-300)

LIVE = f"{API_PREFIX}/movies/new-and-upcoming"
MOVIES = f"{API_PREFIX}/movies"


def film(tmdb_id, title, status="new", movie_id=None, release="2026-10-20"):
    return {"tmdb_id": tmdb_id, "movie_id": movie_id, "title": title, "original_title": title, "release_date": release,
            "year": 2026, "poster": {"small": "https://x/w342/p.jpg", "large": "https://x/w780/p.jpg"},
            "overview": "A story.", "genres": ["Drama"], "vote_average": None, "vote_count": 3, "popularity": 9.0,
            "status": status}


class FakeCache:
    def __init__(self, new=(), upcoming=(), fail=False, primed=True):
        self.new, self.upcoming, self.fail, self.primed, self.fetch_calls = list(new), list(upcoming), fail, primed, 0

    def _view(self):
        return {"fetched_at": "2026-10-30T10:00:00+00:00", "stale": self.fail, "new": self.new, "upcoming": self.upcoming}

    async def get(self):
        self.fetch_calls += 1
        return {"fetched_at": None, "stale": True, "new": [], "upcoming": []} if self.fail else self._view()

    def peek(self):
        return self._view() if self.primed else None


@pytest.fixture
def client(db):
    with TestClient(create_app(Settings(db_path=db / "movies.db"), predictor=object())) as c:
        c.app.state.live = FakeCache(new=[film(10, "Night Train"), film(11, "Dune Three", movie_id=5)],
                                     upcoming=[film(12, "Dune Four", "upcoming", release="2026-11-14")])
        yield c


def test_the_shape_and_the_cache_header(client):
    r = client.get(LIVE)
    body = r.json()
    assert r.status_code == 200 and set(body) == {"fetched_at", "stale", "new", "upcoming"}
    assert set(body["new"][0]) >= {"tmdb_id", "movie_id", "title", "release_date", "poster", "status"}
    assert "max-age=600" in r.headers["Cache-Control"]


def test_the_route_is_not_captured_by_the_film_id_route(client):
    assert client.get(LIVE).status_code == 200  # captured by /movies/{movie_id}, it would be a 422 (not a number)


def test_tmdb_down_gives_empty_stale_lists(client):
    client.app.state.live = FakeCache(fail=True)
    body = client.get(LIVE).json()
    assert body["stale"] is True and body["new"] == [] and body["upcoming"] == []


def test_the_live_endpoint_works_without_a_token_at_all(db):
    with TestClient(create_app(Settings(db_path=db / "movies.db"), predictor=object())) as c:
        body = c.get(LIVE).json()
    assert body["stale"] is True and body["new"] == [] and body["upcoming"] == []


def test_live_matches_come_on_page_one_only_and_never_include_films_in_the_database(client):
    one = client.get(MOVIES, params={"q": "dune"}).json()
    assert [f["title"] for f in one["live_matches"]] == ["Dune Four"]  # "Dune Three" is film 5 in our database
    assert client.get(MOVIES, params={"q": "dune", "page": 2}).json()["live_matches"] == []
    assert client.get(MOVIES).json()["live_matches"] == []  # no search text


def test_an_empty_cache_is_never_filled_by_a_search(client):
    cache = client.app.state.live = FakeCache(primed=False)
    body = client.get(MOVIES, params={"q": "dune"}).json()
    assert body["live_matches"] == [] and cache.fetch_calls == 0
