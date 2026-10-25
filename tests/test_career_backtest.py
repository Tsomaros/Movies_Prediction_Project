"""ml/career/backtest.py (Day 14.8): next-film points, the vectorised maths, tuning and the artifact, for the score
and for log revenue."""

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
from ml.career.backtest import (H_GRID, K_GRID, build_artifact, evaluate, next_film_points, tune, _forecast,
                                _from_points, _load, _pop_table, _role_set)
from ml.career.forecast import HIGH, LOW, MIN_RATED, RoleSettings, track_record
from ml.data.build_db import SCHEMA
from ml.data.clean import MIN_VOTES

ACTORS = range(1, 21)
SAME_DATE_ACTOR, STAR = 1, 2  # STAR scores about 9.5, so a wide range clips at 10
DIRECTORS, WRITERS = (31, 32, 33), (41, 42)
SAME_DATE_SCORE, SAME_DATE_SCORE_2 = 9.1, 2.2  # SAME_DATE_ACTOR's 6th and 7th rated films, on one date
SAME_DATE_REVENUE, SAME_DATE_REVENUE_2 = 7_777_777.0, 333_333_333.0  # and their (trusted) revenues
START, END = dt.date(2005, 1, 1), dt.date(2023, 12, 31)


def _career(rng, n):
    days = np.sort(rng.integers(0, (END - START).days, n))
    return [START + dt.timedelta(days=int(d)) for d in days]


def _build():
    rng = np.random.default_rng(7)
    money = np.random.default_rng(8)  # revenues on their own stream, so the scores stay as they were
    movies, cast, crew = [], [], []

    def film(date, score, votes=200, revenue=None, suspect=0, incomplete=0):
        i = 1000 + len(movies)
        movies.append((i, date.isoformat(), date.year, votes, round(float(score), 1), revenue, suspect, incomplete))
        return i

    for p in ACTORS:
        base = 9.5 if p == STAR else rng.uniform(5.0, 7.5)
        log_base = money.uniform(15, 19)
        dates = _career(rng, int(rng.integers(8, 20)))
        if p == SAME_DATE_ACTOR:
            dates[6] = dates[5]
        for j, d in enumerate(dates):
            score = (SAME_DATE_SCORE, SAME_DATE_SCORE_2)[j - 5] if p == SAME_DATE_ACTOR and j in (5, 6) else \
                min(base + rng.normal(0, 0.7), 10)
            revenue = (SAME_DATE_REVENUE, SAME_DATE_REVENUE_2)[j - 5] if p == SAME_DATE_ACTOR and j in (5, 6) else \
                round(float(np.exp(log_base + money.normal(0, 1))))
            doubt = j >= 7 and j % 3  # from the 8th film on, 1 in 3 doubted and 1 in 3 incomplete
            cast.append((film(d, score, revenue=revenue, suspect=int(doubt == 1), incomplete=int(doubt == 2)),
                         p, "Role", j % 4))
        cast.append((film(dates[-1], 9.9, votes=MIN_VOTES - 1), p, "Cameo", 9))  # low-vote: never counts
    for p in DIRECTORS + WRITERS:
        job = "Director" if p in DIRECTORS else "Writer"
        for d in _career(rng, 10):
            i = film(d, rng.uniform(5, 8), revenue=round(float(np.exp(money.uniform(14, 19)))))
            crew.append((i, p, job))
            if p in WRITERS:
                crew.append((i, p, "Screenplay"))  # both jobs on one film: one credit
    return movies, cast, crew


MOVIES, CAST, CREW = _build()
TRUSTED_LOGS = {math.log(r) for *_, r, s, inc in MOVIES if r is not None and not s and not inc}
DOUBTED_LOGS = {math.log(r) for *_, r, s, inc in MOVIES if r is not None and (s or inc)}


@pytest.fixture
def con(tmp_path):
    c = sqlite3.connect(tmp_path / "movies.db")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    people = sorted({p for _, p, *_ in CAST} | {p for _, p, _ in CREW})
    c.executemany("INSERT INTO people VALUES (?, ?)", [(p, f"Person {p}") for p in people])
    c.executemany("""INSERT INTO movies (id, title, release_date, year, vote_count, vote_average, score_ok,
                                         poster_path, revenue_2025, money_suspect, revenue_incomplete, covid_period)
                     VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, 0)""",
                  [(i, f"Film {i}", d, y, v, s, int(v >= MIN_VOTES), r, sus, inc)
                   for i, d, y, v, s, r, sus, inc in MOVIES])
    c.executemany("INSERT INTO movie_cast VALUES (?, ?, ?, ?)", CAST)
    c.executemany("INSERT INTO movie_crew VALUES (?, ?, ?)", CREW)
    yield c
    c.close()


def _pop(con, role="acting", metric="score"):
    return lambda y: population_stats(con, role, MIN_VOTES, y - 1, metric)


def test_points_use_only_strictly_earlier_films(con):
    pts = next_film_points(con, "acting", MIN_VOTES)
    assert pts
    for p in pts:
        assert len(p.history) >= MIN_RATED
        assert all(y <= p.year for y, _ in p.history)
        assert 9.9 not in [s for _, s in p.history] and p.value != 9.9  # the low-vote film
    sd = [p for p in pts if p.person_id == SAME_DATE_ACTOR]
    pair = [p for p in sd if p.value in (SAME_DATE_SCORE, SAME_DATE_SCORE_2)]
    assert len(pair) == 2 and all(len(p.history) == MIN_RATED for p in pair)
    assert not any({SAME_DATE_SCORE, SAME_DATE_SCORE_2} & {s for _, s in p.history} for p in pair)


def test_revenue_points_only_from_trusted_films_strictly_earlier(con):
    pts = next_film_points(con, "acting", MIN_VOTES, "revenue")
    assert pts and DOUBTED_LOGS
    for p in pts:
        assert len(p.history) >= MIN_RATED and all(y <= p.year for y, _ in p.history)
        assert {p.value, *(x for _, x in p.history)} <= TRUSTED_LOGS  # log 2025 $, never a doubted figure
    pair_logs = {math.log(SAME_DATE_REVENUE), math.log(SAME_DATE_REVENUE_2)}
    pair = [p for p in pts if p.person_id == SAME_DATE_ACTOR and p.value in pair_logs]
    assert len(pair) == 2 and all(len(p.history) == MIN_RATED for p in pair)
    assert not any(pair_logs & {x for _, x in p.history} for p in pair)


def test_writer_with_two_jobs_on_a_film_counts_it_once(con):
    pts = [p for p in next_film_points(con, "writing", MIN_VOTES) if p.person_id == WRITERS[0]]
    assert len(pts) == 10 - MIN_RATED and [len(p.history) for p in pts] == list(range(MIN_RATED, 10))


@pytest.mark.parametrize("metric,column,value", [("score", "vote_average", 1.0), ("revenue", "revenue_2025", 1.0)])
def test_time_travel_changing_future_values_changes_nothing(con, metric, column, value):
    def history():
        return {(p.person_id, p.year): p.history for p in next_film_points(con, "acting", MIN_VOTES, metric)
                if p.year < 2019}
    before = history()
    con.execute(f"UPDATE movies SET {column} = ? WHERE year >= 2019", (value,))
    assert before == history()


@pytest.mark.parametrize("metric", ["score", "revenue"])
def test_each_person_weighs_the_same(con, metric):
    totals = Counter()
    for p in next_film_points(con, "acting", MIN_VOTES, metric):
        totals[p.person_id] += p.weight
    assert len(totals) == len(ACTORS) and all(t == pytest.approx(1.0) for t in totals.values())


@pytest.mark.parametrize("metric", ["score", "revenue"])
@pytest.mark.parametrize("s", [RoleSettings(5, 3, 1.3), RoleSettings(math.inf, 1, 1.0), RoleSettings(3, 13, 4.0)])
def test_vectorised_maths_equals_track_record(con, s, metric):
    pts = next_film_points(con, "acting", MIN_VOTES, metric)
    pop = _pop(con, metric=metric)
    bounds = (LOW, HIGH) if metric == "score" else None
    expected = [track_record(p.history, s, *pop(p.year), bounds=bounds) for p in pts]
    for st in (_from_points(pts, pop, (s.h,), metric), _role_set(con, "acting", MIN_VOTES, metric)):
        assert len(st) == len(pts)
        low, mid, high = _forecast(st, s)
        assert low == pytest.approx([f.low for f in expected], rel=1e-9, abs=1e-9)
        assert mid == pytest.approx([f.mid for f in expected], rel=1e-9, abs=1e-9)
        assert high == pytest.approx([f.high for f in expected], rel=1e-9, abs=1e-9)
    if s.q == 4.0 and metric == "score":
        assert any(f.high == 10.0 for f in expected) and any(f.low == 1.0 for f in expected)  # clipping exercised
    if s.q == 4.0 and metric == "revenue":
        assert any(f.high > 10.0 for f in expected)  # log $ are never clipped


@pytest.mark.parametrize("metric", ["score", "revenue"])
def test_population_from_the_loaded_rows_equals_population_stats(con, metric):
    for role in ("acting", "writing"):
        table = _pop_table(_load(con, role, MIN_VOTES, metric), np.array([2008, 2015, 2023]))
        for year, (mu, sd) in table.items():
            assert (mu, sd) == pytest.approx(population_stats(con, role, MIN_VOTES, year - 1, metric), rel=1e-12)


@pytest.mark.parametrize("metric", ["score", "revenue"])
def test_tune_hits_80_percent_on_training_points(con, metric):
    pts = [p for p in next_film_points(con, "acting", MIN_VOTES, metric) if p.year < 2019]
    pop = _pop(con, metric=metric)
    s = tune(pts, pop, metric=metric)
    assert s.h in H_GRID and s.k in K_GRID
    assert evaluate(pts, s, pop, metric)["coverage"] >= 0.80
    assert evaluate(pts, RoleSettings(s.h, s.k, round(s.q - 0.05, 2)), pop, metric)["coverage"] < 0.80  # smallest q


@pytest.mark.parametrize("metric,column,value", [("score", "vote_average", 1.0), ("revenue", "revenue_2025", 1.0)])
def test_tuning_uses_points_before_2019_only(con, metric, column, value):
    before = build_artifact(con, MIN_VOTES, "x")["roles"]["acting"][metric]
    con.execute(f"UPDATE movies SET {column} = ? WHERE year >= 2019", (value,))
    after = build_artifact(con, MIN_VOTES, "x")["roles"]["acting"][metric]
    assert {k: before[k] for k in "hkq"} == {k: after[k] for k in "hkq"}
    assert before["test"] != after["test"]


def test_within_2x_is_the_share_of_log_errors_up_to_log_2(con):
    pts = [p for p in next_film_points(con, "acting", MIN_VOTES, "revenue") if p.year >= 2019]
    s, pop = RoleSettings(5, 3, 1.3), _pop(con, metric="revenue")
    got = evaluate(pts, s, pop, "revenue")["within_2x"]
    hits = [abs(p.value - track_record(p.history, s, *pop(p.year), bounds=None).mid) <= math.log(2) for p in pts]
    assert got == pytest.approx(np.average(hits, weights=[p.weight for p in pts]))
    assert "within_2x" not in evaluate(pts, s, pop, "score")


def test_artifact_shape_and_fallback(con, monkeypatch):
    art = build_artifact(con, MIN_VOTES, "2026-11-01T00:00:00+00:00")
    json.dumps(art, allow_nan=False)
    assert set(art) == {"version", "built_at", "roles"} and art["version"] == 2
    assert set(art["roles"]) == {"acting", "directing", "writing"}
    tests = {"coverage", "mae", "width", "baseline_mae", "n_people", "n_points"}
    for metric, extra in (("score", set()), ("revenue", {"within_2x"})):
        acting = art["roles"]["acting"][metric]
        assert acting["fallback"] is False
        assert set(acting) == {"h", "k", "q", "mu", "sigma_pop", "fallback", "test"}
        assert set(acting["test"]) == tests | extra
        for role in ("directing", "writing"):  # far fewer than 300 people: acting's settings for that metric
            r = art["roles"][role][metric]
            assert r["fallback"] is True and {k: r[k] for k in "hkq"} == {k: acting[k] for k in "hkq"}
            assert r["test"]["n_people"] > 0 and r["mu"] != acting["mu"]  # the role's own population
    assert art["roles"]["acting"]["revenue"]["mu"] > 10  # log 2025 $
    monkeypatch.setattr(backtest, "MIN_PEOPLE", len(DIRECTORS))
    art = build_artifact(con, MIN_VOTES, "x")
    for metric in ("score", "revenue"):
        assert art["roles"]["directing"][metric]["fallback"] is False
        assert art["roles"]["writing"][metric]["fallback"] is True


def test_sampling_caps_the_training_points(con):
    full = build_artifact(con, MIN_VOTES, "x", max_points=None)["roles"]["acting"]
    capped = build_artifact(con, MIN_VOTES, "x", max_points=40)["roles"]["acting"]
    for metric in ("score", "revenue"):  # the report always uses every test point
        assert full[metric]["test"]["n_points"] == capped[metric]["test"]["n_points"]
    assert capped == build_artifact(con, MIN_VOTES, "x", max_points=40)["roles"]["acting"]  # seeded
