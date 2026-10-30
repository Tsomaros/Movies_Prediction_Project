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
