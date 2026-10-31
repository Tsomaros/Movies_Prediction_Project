"""ml/career/backtest.py (Day 14.8): next-film points, the vectorised maths, tuning and the artifact."""

from __future__ import annotations

import datetime as dt
import json
import math
import sqlite3
from collections import Counter

import numpy as np
import pytest

from backend.app.repo.career import population_stats
from ml.career import backtest
from ml.career.backtest import (H_GRID, HOLDOUT_FROM, K_GRID, build_artifact, evaluate, holdout_points,
                                next_film_points, tune, _forecast, _from_points, _load, _pop_table, _role_set)
from ml.career.forecast import MIN_RATED, RoleSettings, track_record
from ml.data.build_db import SCHEMA
from ml.data.clean import MIN_VOTES, MODEL_DATA_MAX_YEAR

ACTORS = range(1, 21)
SAME_DATE_ACTOR, STAR = 1, 2  # STAR scores about 9.5, so a wide range clips at 10
DIRECTORS, WRITERS = (31, 32, 33), (41, 42)
SAME_DATE_SCORE, SAME_DATE_SCORE_2 = 9.1, 2.2  # SAME_DATE_ACTOR's 6th and 7th rated films, on one date
START, END = dt.date(2005, 1, 1), dt.date(2023, 12, 31)
YOUNG_2026_SCORE = 9.77  # a 2026 film still settling at its pull: never a holdout point
HOLDOUT_ACTORS = (3, 4, 5, 6, 7, 8)  # each has a settled 2026 film; actor 3 has two
PULLED = "2026-10-30T13:42:39+00:00"


def _career(rng, n):
    days = np.sort(rng.integers(0, (END - START).days, n))
    return [START + dt.timedelta(days=int(d)) for d in days]


def _build():
    rng = np.random.default_rng(7)
    movies, cast, crew = [], [], []

    def film(date, score, votes=200):
        i = 1000 + len(movies)
        movies.append((i, date.isoformat(), date.year, votes, round(float(score), 1)))
        return i

    for p in ACTORS:
        base = 9.5 if p == STAR else rng.uniform(5.0, 7.5)
        dates = _career(rng, int(rng.integers(8, 20)))
        if p == SAME_DATE_ACTOR:
            dates[6] = dates[5]
        for j, d in enumerate(dates):
            score = (SAME_DATE_SCORE, SAME_DATE_SCORE_2)[j - 5] if p == SAME_DATE_ACTOR and j in (5, 6) else \
                min(base + rng.normal(0, 0.7), 10)
            cast.append((film(d, score), p, "Role", j % 4))
        cast.append((film(dates[-1], 9.9, votes=MIN_VOTES - 1), p, "Cameo", 9))  # low-vote: never counts
    for p in DIRECTORS + WRITERS:
        job = "Director" if p in DIRECTORS else "Writer"
        for d in _career(rng, 10):
            i = film(d, rng.uniform(5, 8))
            crew.append((i, p, job))
            if p in WRITERS:
                crew.append((i, p, "Screenplay"))  # both jobs on one film: one credit
    return movies, cast, crew


MOVIES, CAST, CREW = _build()


@pytest.fixture
def con(tmp_path):
    c = sqlite3.connect(tmp_path / "movies.db")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    people = sorted({p for _, p, *_ in CAST} | {p for _, p, _ in CREW})
    c.executemany("INSERT INTO people VALUES (?, ?)", [(p, f"Person {p}") for p in people])
    c.executemany("""INSERT INTO movies (id, title, release_date, year, vote_count, vote_average, score_ok,
                                         poster_path, money_suspect, revenue_incomplete, covid_period)
                     VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, 0, 0)""",
                  [(i, f"Film {i}", d, y, v, s, int(v >= MIN_VOTES)) for i, d, y, v, s in MOVIES])
    c.executemany("INSERT INTO movie_cast VALUES (?, ?, ?, ?)", CAST)
    c.executemany("INSERT INTO movie_crew VALUES (?, ?, ?)", CREW)
    later = [(9001, "2026-01-10", 6.5, 3), (9002, "2026-02-14", 7.0, 4), (9003, "2026-03-01", 5.5, 5),
             (9004, "2026-03-20", 6.0, 6), (9005, "2026-04-02", 8.0, 7), (9006, "2026-04-20", 6.8, 8),
             (9007, "2026-08-01", YOUNG_2026_SCORE, 3)]  # the last was 90 days old when pulled
    c.executemany("""INSERT INTO movies (id, title, release_date, year, vote_count, vote_average, score_ok,
                                         poster_path, money_suspect, revenue_incomplete, covid_period, pulled_at)
                     VALUES (?, ?, ?, 2026, 200, ?, 1, NULL, 0, 0, 0, ?)""",
                  [(i, f"Film {i}", d, sc, PULLED) for i, d, sc, _ in later])
    c.executemany("INSERT INTO movie_cast VALUES (?, ?, 'Role', 0)", [(i, p) for i, _, _, p in later])
    c.execute("""INSERT INTO movies (id, title, release_date, year, vote_count, vote_average, score_ok, poster_path,
                                    money_suspect, revenue_incomplete, covid_period, pulled_at)
                  VALUES (9008, 'Film 9008', '2026-04-25', 2026, 200, 6.2, 1, NULL, 0, 0, 0, ?)""", (PULLED,))
    c.execute("INSERT INTO movie_cast VALUES (9008, 3, 'Role', 0)")
    yield c
    c.close()


def _pop(con, role="acting"):
    return lambda y: population_stats(con, role, MIN_VOTES, y - 1)


def test_points_use_only_strictly_earlier_films(con):
    pts = next_film_points(con, "acting", MIN_VOTES)
    assert pts
    for p in pts:
        assert len(p.history) >= MIN_RATED
        assert all(y <= p.year for y, _ in p.history)
        assert 9.9 not in [s for _, s in p.history] and p.score != 9.9  # the low-vote film
    sd = [p for p in pts if p.person_id == SAME_DATE_ACTOR]
    pair = [p for p in sd if p.score in (SAME_DATE_SCORE, SAME_DATE_SCORE_2)]
    assert len(pair) == 2 and all(len(p.history) == MIN_RATED for p in pair)
    assert not any({SAME_DATE_SCORE, SAME_DATE_SCORE_2} & {s for _, s in p.history} for p in pair)


def test_writer_with_two_jobs_on_a_film_counts_it_once(con):
    pts = [p for p in next_film_points(con, "writing", MIN_VOTES) if p.person_id == WRITERS[0]]
    assert len(pts) == 10 - MIN_RATED and [len(p.history) for p in pts] == list(range(MIN_RATED, 10))


def test_time_travel_changing_future_scores_changes_nothing(con):
    before = {(p.person_id, p.year): p.history for p in next_film_points(con, "acting", MIN_VOTES) if p.year < 2019}
    con.execute("UPDATE movies SET vote_average = 1.0 WHERE year >= 2019")
    after = {(p.person_id, p.year): p.history for p in next_film_points(con, "acting", MIN_VOTES) if p.year < 2019}
    assert before == after


def test_each_person_weighs_the_same(con):
    totals = Counter()
    for p in next_film_points(con, "acting", MIN_VOTES):
        totals[p.person_id] += p.weight
    assert len(totals) == len(ACTORS) and all(t == pytest.approx(1.0) for t in totals.values())


@pytest.mark.parametrize("s", [RoleSettings(5, 3, 1.3), RoleSettings(math.inf, 1, 1.0), RoleSettings(3, 13, 4.0)])
def test_vectorised_maths_equals_track_record(con, s):
    pts = next_film_points(con, "acting", MIN_VOTES)
    pop = _pop(con)
    expected = [track_record(p.history, s, *pop(p.year)) for p in pts]
    for st in (_from_points(pts, pop, (s.h,)), _role_set(con, "acting", MIN_VOTES)):
        assert len(st) == len(pts)
        low, mid, high = _forecast(st, s)
        assert low == pytest.approx([f.low for f in expected], rel=1e-9, abs=1e-9)
        assert mid == pytest.approx([f.mid for f in expected], rel=1e-9, abs=1e-9)
        assert high == pytest.approx([f.high for f in expected], rel=1e-9, abs=1e-9)
    if s.q == 4.0:
        assert any(f.high == 10.0 for f in expected) and any(f.low == 1.0 for f in expected)  # clipping exercised


def test_population_from_the_loaded_rows_equals_population_stats(con):
    for role in ("acting", "writing"):
        table = _pop_table(_load(con, role, MIN_VOTES), np.array([2008, 2015, 2023]))
        for year, (mu, sd) in table.items():
            assert (mu, sd) == pytest.approx(population_stats(con, role, MIN_VOTES, year - 1), rel=1e-12)


def test_tune_hits_80_percent_on_training_points(con):
    pts = [p for p in next_film_points(con, "acting", MIN_VOTES) if p.year < 2019]
    pop = _pop(con)
    s = tune(pts, pop)
    assert s.h in H_GRID and s.k in K_GRID
    assert evaluate(pts, s, pop)["coverage"] >= 0.80
    assert evaluate(pts, RoleSettings(s.h, s.k, round(s.q - 0.05, 2)), pop)["coverage"] < 0.80  # the smallest q


def test_tuning_uses_points_before_2019_only(con):
    before = build_artifact(con, MIN_VOTES, "x")["roles"]["acting"]
    con.execute("UPDATE movies SET vote_average = 1.0 WHERE year >= 2019")
    after = build_artifact(con, MIN_VOTES, "x")["roles"]["acting"]
    assert {k: before[k] for k in "hkq"} == {k: after[k] for k in "hkq"}
    assert before["test"] != after["test"]


def test_artifact_shape_and_fallback(con, monkeypatch):
    art = build_artifact(con, MIN_VOTES, "2026-11-01T00:00:00+00:00")
    json.dumps(art, allow_nan=False)
    assert set(art) == {"version", "built_at", "roles"} and art["version"] == 2
    acting = art["roles"]["acting"]
    assert acting["fallback"] is False
    assert set(acting) == {"h", "k", "q", "mu", "sigma_pop", "fallback", "test", "holdout"}
    assert set(acting["test"]) == {"coverage", "mae", "width", "baseline_mae", "n_people", "n_points"}
    for role in ("directing", "writing"):  # far fewer than 300 people: the acting settings
        r = art["roles"][role]
        assert r["fallback"] is True and {k: r[k] for k in "hkq"} == {k: acting[k] for k in "hkq"}
        assert r["test"]["n_people"] > 0
    monkeypatch.setattr(backtest, "MIN_PEOPLE", len(DIRECTORS))
    art = build_artifact(con, MIN_VOTES, "x")
    assert art["roles"]["directing"]["fallback"] is False and art["roles"]["writing"]["fallback"] is True


def test_sampling_caps_the_training_points(con):
    full = build_artifact(con, MIN_VOTES, "x", max_points=None)["roles"]["acting"]
    capped = build_artifact(con, MIN_VOTES, "x", max_points=40)["roles"]["acting"]
    assert full["test"]["n_points"] == capped["test"]["n_points"]  # the report always uses every test point
    assert capped == build_artifact(con, MIN_VOTES, "x", max_points=40)["roles"]["acting"]  # seeded


# ---------------------------------------------------------------- the 2026 holdout (V1.4)


def test_holdout_history_stops_at_2025_and_skips_settling(con):
    pts = holdout_points(con, "acting", MIN_VOTES)
    assert pts and all(p.year >= HOLDOUT_FROM and all(y <= MODEL_DATA_MAX_YEAR for y, _ in p.history) for p in pts)
    assert HOLDOUT_FROM == MODEL_DATA_MAX_YEAR + 1
    assert YOUNG_2026_SCORE not in [p.score for p in pts]
    assert all(len(p.history) >= MIN_RATED for p in pts)
    assert len(pts) == 7  # 6 people, actor 3 with two films; the settling one is out


def test_holdout_time_travel(con):
    before = [p.history for p in holdout_points(con, "acting", MIN_VOTES)]
    con.execute("UPDATE movies SET vote_average = 1.0 WHERE year >= 2026")
    assert [p.history for p in holdout_points(con, "acting", MIN_VOTES)] == before


def test_holdout_person_weights_sum_to_one(con):
    totals = Counter()
    for p in holdout_points(con, "acting", MIN_VOTES):
        totals[p.person_id] += p.weight
    assert totals and all(t == pytest.approx(1.0) for t in totals.values())


def test_holdout_changes_no_tuned_number(con):
    art = build_artifact(con, MIN_VOTES, "2026-10-31T00:00:00+00:00")
    con.execute("DELETE FROM movie_cast WHERE movie_id >= 9000")
    con.execute("DELETE FROM movies WHERE year >= 2026")
    old = build_artifact(con, MIN_VOTES, "2026-10-31T00:00:00+00:00")
    for role in art["roles"]:  # (mu and sigma_pop move here only because the fixture's latest year drops to 2023)
        assert {k: art["roles"][role][k] for k in ("h", "k", "q", "fallback", "test")} ==                {k: old["roles"][role][k] for k in ("h", "k", "q", "fallback", "test")}


def test_artifact_v2_holdout_shape_and_empty_role(con):
    art = build_artifact(con, MIN_VOTES, "2026-10-31T00:00:00+00:00")
    assert art["version"] == 2
    h = art["roles"]["acting"]["holdout"]
    assert set(h) == {"year_from", "coverage", "mae", "baseline_mae", "n_people", "n_points"}
    assert h["year_from"] == HOLDOUT_FROM and h["n_points"] == 7 and h["n_people"] == 6
    assert 0 <= h["coverage"] <= 1
    w = art["roles"]["writing"]["holdout"]
    assert w == {"year_from": HOLDOUT_FROM, "coverage": None, "mae": None, "baseline_mae": None,
                 "n_people": 0, "n_points": 0}


def test_holdout_uses_the_artifacts_population_numbers(con):
    art = build_artifact(con, MIN_VOTES, "x")["roles"]["acting"]
    s = RoleSettings(math.inf if art["h"] is None else art["h"], art["k"], art["q"])
    want = evaluate(holdout_points(con, "acting", MIN_VOTES), s, lambda _y: (art["mu"], art["sigma_pop"]))
    assert art["holdout"]["coverage"] == round(want["coverage"], 4)
    assert art["holdout"]["baseline_mae"] == round(want["baseline_mae"], 4)
