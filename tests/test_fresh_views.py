"""Reading fresh.db through shadowing views (V1.2): a new film is an ordinary film in every endpoint, the fresh copy
wins over a main one, a missing file changes nothing, and the models never open it."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.fresh_views import attach_fresh, has_fresh
from backend.app.main import create_app
from backend.app.services.fresh import build_fresh_db
from backend.app.services.ratelimit import RateLimiter
from backend.app.settings import API_PREFIX, Settings
from tests.factories import TEST_CPI, film
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db, films 1-300)
from tests.test_models import (budget_model, budget_rows, revenue_model, revenue_rows,  # noqa: F401 (fixtures)
                               score_model, score_rows)
from tests.test_predict import predictor  # noqa: F401 (fixture: a small Predictor on the db fixture)

MOVIES = f"{API_PREFIX}/movies"
TODAY = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
FRESH, OVERLAP, ZYX, UPCOMING = 900_001, 5, 900_002, 900_003
KNOWN, NEW_FACE, NEW_CREW = 2001, 990_001, 990_002  # Actor 1 is in the main database; the others only in fresh.db
CREDITS = {"cast": [{"id": KNOWN, "name": "Actor 1", "character": "Hero", "order": 0},
                    {"id": NEW_FACE, "name": "New Face", "character": "Friend", "order": 1}],
           "crew": [{"id": 1000, "name": "Director 0", "job": "Director"}, {"id": NEW_CREW, "name": "New Crew", "job": "Writer"}]}


def fresh_records():
    return [
        film(FRESH, title="Just Out", release_date="2026-10-25", credits=CREDITS, vote_count=12),
        film(OVERLAP, title="Fresh title", release_date="2026-10-20"),
        film(ZYX, title="Zyxquest", release_date="2026-10-28"),
        film(UPCOMING, title="Upcoming thing", status="In Production", release_date="2026-11-20"),
    ]


@pytest.fixture(scope="module")
def fresh_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("fresh") / "fresh.db"
    build_fresh_db(fresh_records(), TEST_CPI, path, {"refreshed_at": "2026-10-30T10:00:00+00:00"})
    return path


def app_client(db, predictor, fresh_path):  # noqa: F811
    app = create_app(Settings(db_path=db / "movies.db", fresh_path=fresh_path), predictor=predictor, lookups=object())
    app.state.clock = lambda: TODAY
    c = TestClient(app)
    c.__enter__()
    c.app.state.limiters = {**c.app.state.limiters, "read": RateLimiter(10_000), "random": RateLimiter(10_000)}
    return c


@pytest.fixture
def client_with_fresh(db, predictor, fresh_file):  # noqa: F811
    c = app_client(db, predictor, fresh_file)
    yield c
    c.__exit__(None, None, None)


@pytest.fixture
def client_main_only(db, predictor, tmp_path):  # noqa: F811
    c = app_client(db, predictor, tmp_path / "no-such-fresh.db")
    yield c
    c.__exit__(None, None, None)


def ids(response) -> list[int]:
    return [f["id"] for f in response.json()["items"]]


def test_attach_does_nothing_without_a_file(db, tmp_path):  # noqa: F811
    con = sqlite3.connect(db / "movies.db")
    assert attach_fresh(con, tmp_path / "missing.db") is False and attach_fresh(con, None) is False
    assert not has_fresh(con)


def test_a_broken_file_is_ignored(db, tmp_path):  # noqa: F811
    bad = tmp_path / "fresh.db"
    bad.write_bytes(b"this is not a database at all" * 100)
    con = sqlite3.connect(db / "movies.db")
    assert attach_fresh(con, bad) is False and not has_fresh(con)
    assert con.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 300  # main still readable


def test_a_fresh_film_everywhere(client_with_fresh):
    r = client_with_fresh.get(f"{MOVIES}/{FRESH}")
    assert r.status_code == 200 and r.json()["title"] == "Just Out" and r.json()["genres"] == ["Action"]
    assert FRESH in ids(client_with_fresh.get(f"{MOVIES}?sort=newest&page_size=48"))


def test_the_fresh_copy_wins(client_with_fresh):
    assert client_with_fresh.get(f"{MOVIES}/{OVERLAP}").json()["title"] == "Fresh title"
    assert ids(client_with_fresh.get(MOVIES, params={"page_size": 48, "sort": "title"})).count(OVERLAP) <= 1


def test_no_fresh_file_behaves_like_main_only(client_main_only, db, predictor):  # noqa: F811
    bare = TestClient(create_app(Settings(db_path=db / "movies.db"), predictor=predictor, lookups=object()))  # fresh_path None
    with bare:
        for url in (MOVIES, f"{MOVIES}?q=film", f"{MOVIES}/3", f"{MOVIES}?sort=newest"):
            assert client_main_only.get(url).json() == bare.get(url).json()
        assert client_main_only.get(f"{MOVIES}/{FRESH}").status_code == 404


def test_a_new_face_has_no_link_a_known_person_has(client_with_fresh):
    body = client_with_fresh.get(f"{MOVIES}/{FRESH}").json()
    assert {c["id"]: c["linked"] for c in body["cast"]} == {KNOWN: True, NEW_FACE: False}
    assert {c["id"]: c["linked"] for c in body["crew"]} == {1000: True, NEW_CREW: False}


def test_similar_films_for_a_fresh_film(client_with_fresh):  # outside the comparables index: matched on genres
    similar = client_with_fresh.get(f"{MOVIES}/{FRESH}").json()["similar"]
    assert FRESH not in [f["id"] for f in similar]


def test_a_person_only_in_fresh_has_no_page(client_with_fresh):
    assert client_with_fresh.get(f"{API_PREFIX}/people/{NEW_FACE}").status_code == 404
    assert client_with_fresh.get(f"{API_PREFIX}/people/{KNOWN}").status_code == 200


def test_a_known_persons_page_lists_their_fresh_film(client_with_fresh):
    roles = client_with_fresh.get(f"{API_PREFIX}/people/{KNOWN}").json()["roles"]
    acting = next(r for r in roles if r["role"] == "acting")
    assert FRESH in [f["id"] for f in acting["films"]]


def test_health_model_card_and_options_never_count_fresh_films(client_with_fresh):
    assert client_with_fresh.get(f"{API_PREFIX}/health").json()["database"]["films"] == 300


# ---------------------------------------------------------------- when=, soonest, search, unreleased, health


EDGES = {"2026-10-30": 910_001, "2026-10-16": 910_002, "2026-10-15": 910_003,
         "2026-10-31": 910_004, "2026-12-29": 910_005, "2026-12-30": 910_006}


@pytest.fixture(scope="module")
def edges_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("edges") / "fresh.db"
    build_fresh_db([film(i, release_date=d, status="Released" if d <= "2026-10-30" else "Planned") for d, i in EDGES.items()],
                   TEST_CPI, path, {})
    return path


def test_when_window_edges(db, predictor, edges_file):  # noqa: F811
    c = app_client(db, predictor, edges_file)
    try:
        # a film released today is Just released; 14 days ago is still in, 15 days ago is out
        assert ids(c.get(MOVIES, params={"when": "released", "sort": "newest", "page_size": 48})) == [910_001, 910_002]
        # tomorrow is Coming soon, 60 days on is the last day, 61 is out
        assert ids(c.get(MOVIES, params={"when": "upcoming", "sort": "soonest"})) == [910_004, 910_005]
    finally:
        c.__exit__(None, None, None)


def test_when_rejects_unknown_values_and_the_sort_is_known(client_main_only):
    r = client_main_only.get(MOVIES, params={"when": "soon"})
    assert r.status_code == 422 and "when" in r.json()["errors"]
    assert client_main_only.get(MOVIES, params={"sort": "soonest"}).status_code == 200


def titles(response) -> list[str]:
    return [f["title"] for f in response.json()["items"]]


def test_search_fresh_only_and_no_duplicates(client_with_fresh):
    assert titles(client_with_fresh.get(MOVIES, params={"q": "Zyxquest"})) == ["Zyxquest"]  # only in fresh
    assert titles(client_with_fresh.get(MOVIES, params={"q": "Fresh title"})) == ["Fresh title"]  # in both, once
    found = ids(client_with_fresh.get(MOVIES, params={"q": "film", "page_size": 48}))
    assert len(found) == len(set(found)) and OVERLAP in found  # nothing twice


def test_search_without_the_file_is_the_old_join(client_main_only):
    assert client_main_only.get(MOVIES, params={"q": "Zyxquest"}).json()["total"] == 0
    assert client_main_only.get(MOVIES, params={"q": "film"}).json()["total"] > 0


def test_unreleased_left_out_of_default_lists(client_with_fresh):
    c = client_with_fresh
    assert UPCOMING not in ids(c.get(MOVIES, params={"page_size": 48}))
    assert UPCOMING not in ids(c.get(MOVIES, params={"sort": "newest", "page_size": 48}))
    assert UPCOMING not in ids(c.get(MOVIES, params={"sort": "popularity", "year_from": 2026}))
    assert UPCOMING in ids(c.get(MOVIES, params={"q": "Upcoming"}))  # search finds it
    assert UPCOMING in ids(c.get(MOVIES, params={"when": "upcoming"}))
    assert all(c.get(f"{API_PREFIX}/random", params={"gems": "true"}).json()["movie"]["id"] != UPCOMING for _ in range(40))


def test_health_has_a_fresh_block(client_with_fresh):
    class Stub:
        def status(self):
            return {"refreshed_at": "2026-10-30T10:00:00+00:00", "films": 4}

    assert client_with_fresh.get(f"{API_PREFIX}/health").json()["fresh"] == {"refreshed_at": None, "films": None}  # no refresher yet
    client_with_fresh.app.state.fresh = Stub()
    assert client_with_fresh.get(f"{API_PREFIX}/health").json()["fresh"] == {"refreshed_at": "2026-10-30T10:00:00+00:00", "films": 4}


def test_answers_with_a_fresh_film_are_cached_ten_minutes(client_with_fresh):
    r = client_with_fresh.get(MOVIES, params={"q": "Zyxquest"})
    assert "max-age=600" in r.headers["Cache-Control"]
    assert "max-age=600" in client_with_fresh.get(MOVIES, params={"when": "released"}).headers["Cache-Control"]
    assert "max-age=3600" in client_with_fresh.get(MOVIES, params={"q": "Film 3"}).headers["Cache-Control"]
