"""New and upcoming films merged into movies.db (V1.2; one database since V1.3): a new film is an ordinary film in
every endpoint, a film the models read is never replaced, and the build's counts stay the build's."""

from __future__ import annotations

import shutil
from contextlib import closing
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.services.fresh import merge_into, open_for_writing
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
KNOWN, NEW_FACE, NEW_CREW = 2001, 990_001, 990_002  # Actor 1 is in the build; the others come with the new film
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


def merged_copy(db, folder, records):  # noqa: F811
    path = folder / "movies.db"
    shutil.copyfile(db / "movies.db", path)
    with closing(open_for_writing(path)) as con:
        merge_into(con, records, TEST_CPI, "2026-10-30T10:00:00+00:00")
    return path


@pytest.fixture(scope="module")
def merged_db(db, tmp_path_factory):  # noqa: F811
    return merged_copy(db, tmp_path_factory.mktemp("merged"), fresh_records())


def app_client(predictor, db_path):  # noqa: F811
    app = create_app(Settings(db_path=db_path), predictor=predictor, lookups=object())
    app.state.clock = lambda: TODAY
    c = TestClient(app)
    c.__enter__()
    c.app.state.limiters = {**c.app.state.limiters, "read": RateLimiter(10_000), "random": RateLimiter(10_000)}
    return c


@pytest.fixture
def client_with_fresh(predictor, merged_db):  # noqa: F811
    c = app_client(predictor, merged_db)
    yield c
    c.__exit__(None, None, None)


@pytest.fixture
def client_main_only(db, predictor):  # noqa: F811
    c = app_client(predictor, db / "movies.db")
    yield c
    c.__exit__(None, None, None)


def ids(response) -> list[int]:
    return [f["id"] for f in response.json()["items"]]


def test_a_fresh_film_everywhere(client_with_fresh):
    r = client_with_fresh.get(f"{MOVIES}/{FRESH}")
    assert r.status_code == 200 and r.json()["title"] == "Just Out" and r.json()["genres"] == ["Action"]
    assert FRESH in ids(client_with_fresh.get(f"{MOVIES}?sort=newest&page_size=48"))


def test_a_film_the_models_read_is_never_replaced(client_with_fresh, client_main_only):
    assert client_with_fresh.get(f"{MOVIES}/{OVERLAP}").json() == client_main_only.get(f"{MOVIES}/{OVERLAP}").json()
    assert client_with_fresh.get(MOVIES, params={"q": "Fresh title"}).json()["total"] == 0


def test_the_build_films_answer_as_before(client_with_fresh, client_main_only):
    for url in (f"{MOVIES}/3", f"{MOVIES}?year_to=2025&sort=title", f"{MOVIES}?year_to=2025&sort=newest"):
        assert client_with_fresh.get(url).json() == client_main_only.get(url).json(), url
    assert client_main_only.get(f"{MOVIES}/{FRESH}").status_code == 404


def test_a_new_face_has_no_link_a_known_person_has(client_with_fresh):
    body = client_with_fresh.get(f"{MOVIES}/{FRESH}").json()
    assert {c["id"]: c["linked"] for c in body["cast"]} == {KNOWN: True, NEW_FACE: False}
    assert {c["id"]: c["linked"] for c in body["crew"]} == {1000: True, NEW_CREW: False}


def test_similar_films_for_a_fresh_film(client_with_fresh):  # outside the comparables index: matched on genres
    similar = client_with_fresh.get(f"{MOVIES}/{FRESH}").json()["similar"]
    assert FRESH not in [f["id"] for f in similar]


def test_a_person_the_refresh_added_has_no_page(client_with_fresh):
    assert client_with_fresh.get(f"{API_PREFIX}/people/{NEW_FACE}").status_code == 404
    assert client_with_fresh.get(f"{API_PREFIX}/people/{KNOWN}").status_code == 200


def test_a_known_persons_page_lists_their_fresh_film(client_with_fresh):
    roles = client_with_fresh.get(f"{API_PREFIX}/people/{KNOWN}").json()["roles"]
    acting = next(r for r in roles if r["role"] == "acting")
    assert FRESH in [f["id"] for f in acting["films"]]


def test_health_and_options_count_the_build_only(client_with_fresh, client_main_only):
    assert client_with_fresh.get(f"{API_PREFIX}/health").json()["database"]["films"] == 300
    assert client_with_fresh.get(f"{API_PREFIX}/meta/options").json() == client_main_only.get(f"{API_PREFIX}/meta/options").json()


# ---------------------------------------------------------------- when=, soonest, search, unreleased, health


EDGES = {"2026-10-30": 910_001, "2026-10-16": 910_002, "2026-10-15": 910_003,
         "2026-10-31": 910_004, "2026-12-29": 910_005, "2026-12-30": 910_006}


@pytest.fixture(scope="module")
def edges_db(db, tmp_path_factory):  # noqa: F811
    return merged_copy(db, tmp_path_factory.mktemp("edges"),
                       [film(i, release_date=d, status="Released" if d <= "2026-10-30" else "Planned") for d, i in EDGES.items()])


def test_when_window_edges(predictor, edges_db):  # noqa: F811
    c = app_client(predictor, edges_db)
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


def test_search_finds_a_merged_film_once(client_with_fresh, client_main_only):
    assert titles(client_with_fresh.get(MOVIES, params={"q": "Zyxquest"})) == ["Zyxquest"]
    assert client_main_only.get(MOVIES, params={"q": "Zyxquest"}).json()["total"] == 0
    found = ids(client_with_fresh.get(MOVIES, params={"q": "film", "page_size": 48}))
    assert len(found) == len(set(found)) and OVERLAP in found  # nothing twice


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

        def cancel(self):
            pass

        def maybe_start(self):
            return None

    assert client_with_fresh.get(f"{API_PREFIX}/health").json()["fresh"] == {"refreshed_at": None, "films": None}  # refresh off
    client_with_fresh.app.state.fresh = Stub()
    assert client_with_fresh.get(f"{API_PREFIX}/health").json()["fresh"] == {"refreshed_at": "2026-10-30T10:00:00+00:00", "films": 4}


def test_answers_with_a_fresh_film_are_cached_ten_minutes(client_with_fresh):
    r = client_with_fresh.get(MOVIES, params={"q": "Zyxquest"})
    assert "max-age=600" in r.headers["Cache-Control"]
    assert "max-age=600" in client_with_fresh.get(MOVIES, params={"when": "released"}).headers["Cache-Control"]
    assert "max-age=3600" in client_with_fresh.get(MOVIES, params={"q": "Film 3"}).headers["Cache-Control"]
