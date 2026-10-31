"""The Career section's endpoints (Day 14.8): GET /people/{id}/career and /career/model on a small database.

ACTOR has 8 rated Drama/Crime films (FEW in 3 of them) 2012-19 (two supporting parts, two films at 7.9: BEST has more votes), a low-vote
2020 film, an undated one and one rated directing credit. FEW has 3 rated films, WRITER wrote 6, COMPOSER only
scored a film, UNRATED only acted in the low-vote one. Recent films 2021-25 (Horror/Mystery, Science Fiction/Action)
give "Something new" its genres and themes. The predictor is a stand-in that records every form it is given;
the real PredictionService (validation and cache) sits in front of it, as for POST /predict.
"""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas.career import CareerModelResponse, CareerResponse
from backend.app.services.career.forecast import load_career_artifact, settings_of
from backend.app.settings import API_PREFIX, Settings
from ml.career.forecast import rolling_line, track_record
from ml.data.build_db import SCHEMA
from ml.data.clean import MIN_VOTES
from tests.career.test_career_model import GENRES, THEMES

ACTOR, FEW, WRITER, COMPOSER, UNRATED, COSTAR, YOUNGSTER, FIVE_ONE_YOUNG = 1, 2, 3, 4, 5, 6, 7, 8
PEOPLE = {ACTOR: "Actor A", FEW: "Few Films", WRITER: "Wendy Writer", COMPOSER: "Composer C", UNRATED: "Unrated U",
          COSTAR: "Co Star", YOUNGSTER: "Young Ster", FIVE_ONE_YOUNG: "Five One"}
DRAMA, CRIME, HORROR, MYSTERY, SCIFI, ACTION = 18, 80, 27, 9648, 878, 28
BEST, LOW_VOTES, UNDATED = 103, 109, 110
YOUNG_ID = 300  # an 8.9 film released 2019-01-01 and pulled 60 days later: settling
CAREER = f"{API_PREFIX}/people/{{}}/career"
MODEL = f"{API_PREFIX}/people/{{}}/career/model"

SCORES = [6.0, 6.4, 7.9, 6.8, 7.0, 7.9, 6.2, 7.1]
FILMS = [  # id, date, year, votes, score, genres, keywords, poster
    *[(101 + k, f"{2012 + k}-05-01", 2012 + k, 500 if k != 5 else 200, s, (DRAMA, CRIME), (3,), f"/p{101 + k}.jpg")
      for k, s in enumerate(SCORES)],
    (LOW_VOTES, "2020-05-01", 2020, 10, 8.5, (DRAMA,), (3,), None),
    (UNDATED, None, None, 500, 7.0, (DRAMA,), (3,), None),
    (YOUNG_ID, "2019-01-01", 2019, 500, 8.9, (DRAMA,), (3,), None),
    *[(301 + k, f"{2014 + k}-03-01", 2014 + k, 500, s, (DRAMA,), (3,), None) for k, s in enumerate([6.0, 6.5, 7.0, 6.2, 6.8])],
    *[(201 + k, f"{2021 + k}-10-01", 2021 + k, 500, 6.5, (HORROR, MYSTERY), (5,), None) for k in range(5)],
    *[(206 + k, f"{2021 + k}-06-01", 2021 + k, 500, 6.5, (SCIFI, ACTION), (6,), None) for k in range(5)],
]
CAST = ([(101 + k, ACTOR, f"Part {k}", 4 if k in (1, 4) else 0) for k in range(8)]
        + [(LOW_VOTES, ACTOR, "Late", 0), (UNDATED, ACTOR, "Lost", 0), (LOW_VOTES, UNRATED, "Extra", 3)]
        + [(101 + k, FEW, "Friend", 1) for k in range(3)]
        + [(i, YOUNGSTER, "Part", 0) for i in (YOUNG_ID, 301, 302, 303, 304, 305)]  # 5 counted + 1 settling
        + [(i, FIVE_ONE_YOUNG, "Part", 0) for i in (YOUNG_ID, 301, 302, 303, 304)])  # 4 counted + 1 settling
CREW = ([(108, ACTOR, "Director")] + [(101 + k, WRITER, "Screenplay") for k in range(6)]
        + [(101, COMPOSER, "Original Music Composer")])
ROLE = {"h": 5.0, "k": 3.0, "q": 1.35, "mu": 6.4, "sigma_pop": 0.8, "fallback": False,
        "test": {"coverage": 0.82, "mae": 0.59, "width": 1.99, "baseline_mae": 0.64, "n_people": 9594, "n_points": 31498}}
ARTIFACT = {"version": 1, "built_at": "2026-10-25T00:00:00+00:00",
            "roles": {"acting": ROLE, "directing": {**ROLE, "h": 3.0, "k": 1.0},
                      "writing": {**ROLE, "h": None, "q": 1.6}}}


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("career")
    con = sqlite3.connect(tmp / "movies.db")
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO genres VALUES (?, ?)", GENRES)
    con.executemany("INSERT INTO people VALUES (?, ?)", PEOPLE.items())
    for i, date, year, votes, score, genres, kw, poster in FILMS:
        con.execute("""INSERT INTO movies (id, title, release_date, year, month, runtime, original_language,
                                           us_certification, poster_path, money_suspect, revenue_incomplete,
                                           covid_period, vote_count, vote_average, score_ok)
                       VALUES (?, ?, ?, ?, ?, 110, 'en', 'R', ?, 0, 0, 0, ?, ?, ?)""",
                    (i, f"Film {i}", date, year, int(date[5:7]) if date else None, poster, votes, score,
                     int(votes >= MIN_VOTES)))
        con.executemany("INSERT INTO movie_genres VALUES (?, ?, ?)", [(i, g, o) for o, g in enumerate(genres)])
        con.executemany("INSERT INTO movie_keywords VALUES (?, ?)", [(i, k) for k in kw])
        con.execute("INSERT INTO movie_countries VALUES (?, 'US')", (i,))
    con.executemany("INSERT INTO movie_cast VALUES (?, ?, ?, ?)", CAST)
    con.executemany("INSERT INTO movie_crew VALUES (?, ?, ?)", CREW)
    con.execute("UPDATE movies SET pulled_at = '2019-03-02T10:00:00+00:00' WHERE id = ?", (YOUNG_ID,))
    con.commit()  # the app reads it through its own read-only connections
    con.close()
    (tmp / "career.json").write_text(json.dumps(ARTIFACT), encoding="utf-8")
    return tmp


class FakePredictor:
    """Records every (validated) form; the score range depends on the genres, so the two films differ."""
    manifest = {"version": "test-1"}

    def __init__(self):
        self.ctx = SimpleNamespace(themes=THEMES)
        self.calls = []

    def predict(self, clean):
        self.calls.append(clean)
        mid = 6.0 + 0.1 * sum(g in ("Horror", "Science Fiction") for g in clean["genres"])
        return {"score": {"low": mid - 1, "middle": mid, "high": mid + 1}, "comparables": [], "model_version": "test-1"}


def make_client(files, rate_limit=1000, **settings):
    fake = FakePredictor()
    app = create_app(Settings(db_path=files / "movies.db", career_file=files / "career.json", rate_limit=rate_limit,
                              **settings), predictor=fake, lookups=object())
    return TestClient(app), fake


@pytest.fixture
def client(files):
    c, fake = make_client(files)
    with c:
        c.fake = fake
        yield c


def test_career_full_response(client):
    r = client.get(CAREER.format(ACTOR))
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=3600"
    b = r.json()
    CareerResponse.model_validate(b)
    assert b["person_id"] == ACTOR and b["role"] == "acting"  # 9 dated acting films beat 1 directing
    assert b["roles_available"] == [{"role": "acting", "film_count": 9, "rated_count": 8}]  # directing: 1 rated
    assert [f["movie_id"] for f in b["films"]] == [*range(101, 109), LOW_VOTES]  # the undated film is left out
    first = b["films"][0]
    assert first == {"movie_id": 101, "title": "Film 101", "year": 2012, "release_date": "2012-05-01", "score": 6.0,
                     "vote_count": 500, "rated": True, "settling": False, "lead": True, "character": "Part 0",
                     "poster_small": "https://image.tmdb.org/t/p/w342/p101.jpg"}
    assert [f["lead"] for f in b["films"][:3]] == [True, False, True]
    assert b["films"][-1]["rated"] is False  # drawn faint, never counted
    rated = [(2012 + k, s) for k, s in enumerate(SCORES)]
    assert b["line"] == [{"year": y, "value": round(v, 3)} for y, v in rolling_line(rated)]
    assert b["best_film"] == {"movie_id": BEST, "title": f"Film {BEST}", "year": 2014, "score": 7.9}  # more votes
    art = load_career_artifact(client.app.state.settings.career_file)
    f = track_record(rated, settings_of(art, "acting"), ROLE["mu"], ROLE["sigma_pop"])
    assert b["forecast"] == {
        "status": "ok", "low": round(f.low, 3), "mid": round(f.mid, 3), "high": round(f.high, 3),
        "explain": {"n_rated": 8, "half_life": 5.0, "own_share": round(f.own_share, 3), "own_avg": round(f.own_avg, 3),
                    "db_avg": 6.4},
        "test": {"coverage": 0.82, "n_people": 9594}}
    assert b["forecast"]["low"] < b["forecast"]["mid"] < b["forecast"]["high"]
    assert b["model_available"] is True


def test_settling_film_is_drawn_but_not_counted(client):
    b = client.get(CAREER.format(YOUNGSTER)).json()
    young = next(f for f in b["films"] if f["movie_id"] == YOUNG_ID)
    assert young["settling"] is True and young["rated"] is True
    assert b["best_film"]["movie_id"] != YOUNG_ID
    assert len(b["line"]) == sum(f["rated"] and not f["settling"] for f in b["films"]) == 5
    assert b["forecast"]["explain"]["n_rated"] == len(b["line"])
    assert all(f["settling"] is False for f in client.get(CAREER.format(ACTOR)).json()["films"])


def test_five_rated_with_one_settling_is_not_enough(client):
    assert client.get(CAREER.format(FIVE_ONE_YOUNG)).json()["forecast"]["status"] == "not_enough_films"


def test_a_role_with_few_rated_films_is_listed_when_shown(client):
    b = client.get(CAREER.format(ACTOR) + "?role=directing").json()
    assert b["role"] == "directing" and [r["role"] for r in b["roles_available"]] == ["acting", "directing"]
    assert b["films"][0]["lead"] is None and b["films"][0]["character"] is None


def test_not_enough_films(client):
    b = client.get(CAREER.format(FEW)).json()
    assert b["forecast"] == {"status": "not_enough_films", "low": None, "mid": None, "high": None, "explain": None,
                             "test": {"coverage": 0.82, "n_people": 9594}}
    assert len(b["line"]) == 3 and b["model_available"] is True


def test_writing_has_no_model(client):
    b = client.get(CAREER.format(WRITER)).json()
    assert b["role"] == "writing" and b["model_available"] is False
    assert b["forecast"]["explain"]["half_life"] is None  # every film counts the same
    r = client.get(MODEL.format(WRITER) + "?role=writing")
    assert r.status_code == 404 and r.json() == {"detail": "The film model has no writer input"}


@pytest.mark.parametrize("path,status,detail", [
    (CAREER.format(424242), 404, "Person not found"),
    (CAREER.format(0), 404, "Person not found"),
    (CAREER.format(2**63), 404, "Person not found"),
    (MODEL.format(424242) + "?role=acting", 404, "Person not found"),
    (CAREER.format(ACTOR) + "?role=writing", 404, "No credits in this role"),
    (CAREER.format(COMPOSER), 404, "No credits in this role"),
    (MODEL.format(WRITER) + "?role=acting", 404, "No credits in this role"),
    (MODEL.format(UNRATED) + "?role=acting", 404, "No rated films in this role"),
    (MODEL.format(ACTOR) + f"?role=acting&genre={DRAMA}", 422, "Genre already done"),
    (MODEL.format(ACTOR) + "?role=acting&genre=999", 422, "Unknown genre"),
    (CAREER.format(ACTOR) + "?role=dancing", 422, "Some fields need fixing"),
    (MODEL.format(ACTOR) + "?role=dancing", 422, "Some fields need fixing"),
    (MODEL.format(ACTOR), 422, "Some fields need fixing"),
    (MODEL.format(ACTOR) + "?role=acting&genre=drama", 422, "Some fields need fixing"),
])
def test_career_errors(client, path, status, detail):
    r = client.get(path)
    assert r.status_code == status and r.json()["detail"] == detail
    assert "cache-control" not in r.headers


def test_a_bad_genre_names_the_field_like_every_422(client):
    r = client.get(MODEL.format(ACTOR) + f"?role=acting&genre={DRAMA}")
    assert r.json() == {"detail": "Genre already done", "errors": {"genre": "Genre already done"}}


def test_model_response_and_no_budget_in_score_call(client):
    r = client.get(MODEL.format(ACTOR) + "?role=acting")
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=3600"
    b = r.json()
    CareerModelResponse.model_validate(b)
    assert set(b) == {"usual", "new", "chips"}
    usual, new = b["usual"], b["new"]
    assert usual["recipe"]["genres"] == [DRAMA, CRIME] and usual["recipe"]["labels"]["genres"] == ["Drama", "Crime"]
    assert usual["recipe"]["actors"] == [{"id": ACTOR, "name": "Actor A"}, {"id": FEW, "name": "Few Films"}, "new"]
    assert usual["recipe"]["labels"]["collaborators"] == ["Few Films"]  # 3 shared films
    assert usual["recipe"]["director"] == "new" and usual["recipe"]["release_year"] == 2027  # next year
    assert usual["prediction"] == {"low": 5.0, "mid": 6.0, "high": 7.0}
    assert new["recipe"]["genres"] == [HORROR, MYSTERY] and new["note"] is None  # most common never-done pair
    assert new["prediction"] == {"low": pytest.approx(5.1), "mid": pytest.approx(6.1), "high": pytest.approx(7.1)}
    assert {c["genre_id"]: c["default"] for c in b["chips"]}[HORROR] is True
    calls = client.fake.calls
    assert len(calls) == 2 and all(c["budget"] is None for c in calls)  # never a budget, though the recipe has one
    assert calls[0]["actors"][0] == {"id": ACTOR, "name": "Actor A"} and len(calls[0]["actors"]) == 5


def test_a_director_page_puts_them_in_the_director_slot(client):
    b = client.get(MODEL.format(ACTOR) + "?role=directing").json()
    assert b["usual"]["recipe"]["director"] == {"id": ACTOR, "name": "Actor A"}
    assert client.fake.calls[0]["director"] == {"id": ACTOR, "name": "Actor A"}


def test_chip_returns_only_new_and_is_cached(client):
    url = MODEL.format(ACTOR) + f"?role=acting&genre={SCIFI}"
    first = client.get(url)
    assert first.status_code == 200 and set(first.json()) == {"new"}
    assert first.json()["new"]["recipe"]["genres"] == [SCIFI, ACTION]  # its most common never-done partner
    service = client.app.state.predictions
    n, seen = len(client.fake.calls), service.hits + service.misses
    assert client.get(url).json() == first.json()
    assert len(client.fake.calls) == n and service.hits + service.misses == seen  # the career cache answered
    assert len(client.app.state.career_models) == 1


def test_the_career_cache_is_keyed_by_next_year(client):
    from datetime import datetime, timezone
    url = MODEL.format(ACTOR) + "?role=acting"
    client.get(url)
    client.app.state.clock = lambda: datetime(2030, 1, 1, tzinfo=timezone.utc)
    assert client.get(url).json()["usual"]["recipe"]["release_year"] == 2031
    assert len(client.app.state.career_models) == 2


def test_both_endpoints_count_toward_the_predict_limit(files):
    c, _ = make_client(files, rate_limit=30)
    with c:
        for i in range(30):
            url = CAREER.format(ACTOR) if i % 2 else MODEL.format(ACTOR) + "?role=acting"
            assert c.get(url).status_code == 200
        for url in (CAREER.format(ACTOR), MODEL.format(ACTOR) + "?role=acting"):
            r = c.get(url)
            assert r.status_code == 429 and "retry-after" in r.headers


def test_a_missing_or_broken_artifact_stops_the_start(files, tmp_path):
    for path, problem in ((tmp_path / "nope.json", "missing"), (tmp_path / "bad.json", "lacks")):
        if problem == "lacks":
            path.write_text(json.dumps({**ARTIFACT, "roles": {"acting": ROLE}}), encoding="utf-8")
        app = create_app(Settings(db_path=files / "movies.db", career_file=path), predictor=FakePredictor(),
                         lookups=object())
        with pytest.raises(ValueError, match=f"{problem}.*make career"):
            with TestClient(app):
                pass
        assert not hasattr(app.state, "predictor")
