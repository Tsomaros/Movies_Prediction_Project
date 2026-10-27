"""GET /random ("Surprise me", Day 14.5), offline: the pick, the floor, the filters, exclude and the empty states.

Runs on a copy of the small `db` fixture (films 1-300, 2008-2022, 2,500 votes each, scores 5.0-7.0 by id % 5,
Action/Drama/Comedy by id % 3 = 0/1/2)
with a few films changed so every rule has a case. No accounts database: whole-database mode must still work,
watchlist mode answers 503. The logged-in cases (watched films left out, the watchlist) are in test_accounts.py.
"""

from __future__ import annotations

import random
import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.routers.random import MAX_EXCLUDE
from backend.app.services.random_pick import FLOOR, SHUFFLE, pick, shuffle_ids
from backend.app.services.ratelimit import RateLimiter
from backend.app.settings import API_PREFIX, Settings
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db, films 1-300)

RANDOM = f"{API_PREFIX}/random"
FEW_VOTES, NO_POSTER, NO_RUNTIME, FRENCH = 4, 9, 14, 19  # all score 7.0 (id % 5 == 4)


@pytest.fixture(scope="module")
def spin_db(db, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("random")
    shutil.copyfile(db / "movies.db", tmp / "movies.db")
    with sqlite3.connect(tmp / "movies.db") as con:
        con.execute("UPDATE movies SET vote_count = 30 WHERE id = ?", (FEW_VOTES,))
        con.execute("UPDATE movies SET poster_path = NULL WHERE id = ?", (NO_POSTER,))
        con.execute("UPDATE movies SET runtime = NULL WHERE id = ?", (NO_RUNTIME,))
        con.execute("UPDATE movies SET original_language = 'fr', runtime = 85 WHERE id = ?", (FRENCH,))
    con.close()
    return tmp / "movies.db"


@pytest.fixture
def spin(spin_db):
    with TestClient(create_app(Settings(db_path=spin_db), predictor=object(), lookups=object())) as c:
        c.app.state.limiters["random"] = RateLimiter(10_000)
        yield c


def expected(spin_db, where: str = "1", floor: bool = True) -> set[int]:
    """The films a spin may pick, straight from SQL."""
    rule = f"vote_count >= {FLOOR[0]} AND vote_average >= {FLOOR[1]}" if floor else "1"
    with sqlite3.connect(spin_db) as con:
        rows = con.execute(f"SELECT id FROM movies WHERE poster_path IS NOT NULL AND {rule} AND {where}")
        return {r[0] for r in rows}


def spin_all(c, **params) -> tuple[list[int], dict]:
    """Spin again until nothing is left: every pick, in order, and the final answer."""
    shown: list[int] = []
    while True:
        r = c.get(RANDOM, params={**params, "exclude": ",".join(map(str, shown))})
        assert r.status_code == 200, r.text
        out = r.json()
        if out["movie"] is None:
            return shown, out
        shown.append(out["movie"]["id"])


# ---------------------------------------------------------------- the pick itself


def test_pick_never_returns_a_seen_or_excluded_film_and_names_why_it_cannot_pick():
    rng = random.Random(0)
    for _ in range(50):
        chosen, reason, left = pick(range(1, 11), seen=[1, 2], exclude=[3, 4], rng=rng)
        assert chosen in left and left == [5, 6, 7, 8, 9, 10] and reason is None
    assert pick([], [], []) == (None, "no_match", [])
    assert pick([1, 2], seen=[1], exclude=[2]) == (None, "all_seen", [])


def test_the_shuffle_is_up_to_8_other_films():
    shuffle = shuffle_ids(list(range(1, 21)), 5, random.Random(0))
    assert len(shuffle) == SHUFFLE == len(set(shuffle)) and 5 not in shuffle
    assert shuffle_ids([5, 6], 5) == [6] and shuffle_ids([5], 5) == []


# ---------------------------------------------------------------- over HTTP


def test_a_spin_returns_a_card_with_runtime_and_shuffle_posters_and_is_never_cached(spin, spin_db):
    r = spin.get(RANDOM)
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    out = r.json()
    film = out["movie"]
    with sqlite3.connect(spin_db) as con:  # the pick is random: NO_RUNTIME and FRENCH have their own runtimes
        runtime = con.execute("SELECT runtime FROM movies WHERE id = ?", (film["id"],)).fetchone()[0]
    con.close()
    assert film["id"] in expected(spin_db) and film["runtime"] == runtime and film["poster"]["small"].startswith("https://")
    assert {"title", "year", "score", "votes", "genres"} <= set(film) and out["reason"] is None
    assert len(out["shuffle"]) == SHUFFLE and out["pool"] == len(expected(spin_db))


def test_spin_again_never_repeats_and_covers_exactly_the_films_above_the_floor(spin, spin_db):
    shown, last = spin_all(spin)
    assert len(shown) == len(set(shown)) and set(shown) == expected(spin_db)
    assert FEW_VOTES not in shown and NO_POSTER not in shown and 1 not in shown  # film 1 scores 5.5
    assert last == {"movie": None, "reason": "all_seen", "shuffle": [], "pool": 0}


def test_hidden_gems_remove_the_floor_but_a_poster_is_still_needed(spin, spin_db):
    shown, _ = spin_all(spin, gems=True, decade=2010)
    assert set(shown) == expected(spin_db, "year BETWEEN 2010 AND 2019", floor=False)
    assert FEW_VOTES in shown and NO_POSTER not in shown and any(i % 5 == 0 for i in shown)  # 5.0 scores too


@pytest.mark.parametrize("params,where", [
    ({"genre": "Drama"}, "id % 3 = 1"),
    ({"decade": 2020}, "year >= 2020"),
    ({"language": "fr"}, "original_language = 'fr'"),
    ({"max_runtime": 100}, "runtime <= 100"),
    ({"genre": "Comedy", "decade": 2010, "language": "en", "max_runtime": 120},
     "id % 3 = 2 AND year BETWEEN 2010 AND 2019 AND original_language = 'en' AND runtime <= 120"),
])
def test_each_filter_is_respected(spin, spin_db, params, where):
    shown, _ = spin_all(spin, **params)
    assert shown and set(shown) == expected(spin_db, where)


def test_a_film_with_no_runtime_is_left_out_under_max_runtime(spin):
    with_limit, _ = spin_all(spin, max_runtime=240)
    without, _ = spin_all(spin)
    assert NO_RUNTIME in without and NO_RUNTIME not in with_limit and FRENCH in with_limit


def test_filters_that_match_nothing_say_no_match(spin):
    out = spin.get(RANDOM, params={"language": "fr", "genre": "Action"}).json()  # film 19 is a Drama
    assert out == {"movie": None, "reason": "no_match", "shuffle": [], "pool": 0}


def test_bad_parameters_are_a_422_in_the_usual_shape(spin):
    def errors(**params):
        r = spin.get(RANDOM, params=params)
        assert r.status_code == 422 and r.json()["detail"] == "Some fields need fixing"
        return set(r.json()["errors"])
    assert errors(decade=1965) == {"decade"} and errors(decade=1950) == {"decade"}
    assert errors(max_runtime=30) == {"max_runtime"} and errors(source="friends") == {"source"}
    assert errors(genre="Cartoon") == {"genre"} and errors(exclude="1,two") == {"exclude"}
    assert errors(exclude=",".join(map(str, range(1, MAX_EXCLUDE + 2)))) == {"exclude"}
    assert spin.get(RANDOM, params={"exclude": ",".join(map(str, range(1, MAX_EXCLUDE + 1)))}).status_code == 200


def test_watchlist_mode_needs_accounts_but_whole_database_mode_does_not(spin):
    assert spin.app.state.userdb is None
    r = spin.get(RANDOM, params={"source": "watchlist"})
    assert r.status_code == 503 and r.json() == {"detail": "Accounts are not set up on this server"}
    spin.cookies.set("mp_session", "anything")  # a cookie, but no accounts to look it up in
    assert spin.get(RANDOM).status_code == 200


def test_more_than_60_spins_a_minute_get_a_429(spin):
    spin.app.state.limiters["random"] = RateLimiter(2)
    assert [spin.get(RANDOM).status_code for _ in range(3)] == [200, 200, 429]
    r = spin.get(RANDOM)
    assert int(r.headers["retry-after"]) > 0 and "Too many spins" in r.json()["detail"]
