"""The track-record forecast's backtest (Day 14.8): tune h, k, q per role and write ml/artifacts/career_forecast.json.

    Point(person_id, history, year, score, weight)
                                     -> one "next film": its (year, score) history of strictly earlier rated films
    next_film_points(con, role, min_votes)
                                     -> every rated film after a person's 5th rated film in that role, as Points
    evaluate(points, s, pop)         -> {coverage, mae, width, baseline_mae, n_people, n_points}, weighted
    tune(points, pop, max_points=None)
                                     -> RoleSettings: (h, k) by the lowest weighted MAE of the middle, then the
                                        smallest q on a 0.05 grid with weighted coverage >= 0.80
    build_artifact(con, min_votes, built_at, max_points=50000)
                                     -> {version, built_at, roles: {role: {h, k, q, mu, sigma_pop,
                                        fallback, test}}}

CLI: uv run python -m ml.career.backtest [--db data/movies.db] [--out ml/artifacts/career_forecast.json]
                                         [--max-points 50000]

A point is a rated film whose history (the person's rated films in that role with a strictly earlier date; a
film without a date counts as 1 July, as in repo/career) has MIN_RATED+ films, so films on the same date never
count for each other. Each point weighs 1 / (that person's points), so busy people don't dominate. pop(year) is
the role's population_stats with end_year = year - 1 (the 10 years before, leak-safe); the rare point with no
rated film of the role in those years (a 1960 film) is left out. Tuning uses points from before 2019, the test
report 2019 onward; a role with fewer than MIN_PEOPLE people with test points takes the acting settings
(fallback). The baseline forecasts every film at mu. The artifact's mu and sigma_pop are the 10 latest years
(what the API uses); h = inf is written as null.

The real data has about 450,000 rated acting credits, so the backtest works on arrays: one query per role, and
per person and h the cumulative sums of w, w·s, w·s² and w² (weights taken relative to the person's first year,
then rescaled to the history's latest year L), from which every k and q is vectorised. This gives what
ml.career.forecast.track_record gives (tests/test_career_backtest.py checks it).
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from backend.app.repo.career import CAREER_ROLES, JOBS, ORDER, RATED, Role, latest_year, population_stats
from ml.career.forecast import HIGH, LOW, MIN_RATED, RoleSettings
from ml.data.build_db import DB_FILE
from ml.data.clean import MIN_VOTES, VALIDATION_LAST_YEAR

OUT_FILE = Path("ml/artifacts/career_forecast.json")
VERSION = 1
H_GRID = (3.0, 5.0, 8.0, 12.0, math.inf)
K_GRID = (1.0, 2.0, 3.0, 5.0, 8.0, 13.0)
Q_GRID = np.round(np.arange(0.05, 5.0001, 0.05), 2)
TARGET_COVERAGE = 0.80
TEST_FROM = VALIDATION_LAST_YEAR + 1  # tune on next films before 2019, report 2019+
MIN_PEOPLE = 300  # people with test points a role needs for its own settings
MAX_POINTS = 50_000  # training points per role used for tuning (sampled with seed 0 above that)
POP_YEARS = 10
DATE_KEY = ORDER.rsplit(",", 1)[0]  # repo/career's date: 1 July for a film with only a year

Pop = Callable[[int], tuple[float, float]]


@dataclass(frozen=True)
class Point:
    person_id: int
    history: list[tuple[int, float]]
    year: int
    score: float
    weight: float


@dataclass(frozen=True)
class _Set:
    """Points as arrays: the sums over each history per h, and what the maths needs besides."""
    person: np.ndarray
    year: np.ndarray
    score: np.ndarray
    weight: np.ndarray
    n: np.ndarray  # history length
    mu: np.ndarray
    sigma_pop: np.ndarray
    sums: dict[float, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]  # h -> (Σw, Σw·s, Σw·s², Σw²)

    def take(self, idx: np.ndarray) -> _Set:
        return _Set(self.person[idx], self.year[idx], self.score[idx], self.weight[idx], self.n[idx], self.mu[idx],
                    self.sigma_pop[idx], {h: tuple(a[idx] for a in v) for h, v in self.sums.items()})

    def __len__(self) -> int:
        return len(self.year)


# ---------------------------------------------------------------- the maths, vectorised over points


def _middle(st: _Set, h: float, k: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(c, share, v) per point, as in track_record."""
    s0, s1, s2, w2 = st.sums[h]
    m = s1 / s0
    n_eff = np.clip(s0 ** 2 / w2, 1, st.n)
    share = n_eff / (n_eff + k)
    c = share * m + (1 - share) * st.mu
    v = np.maximum(s2 / s0 - m ** 2, 0)
    return c, share, v


def _sigma(st: _Set, share: np.ndarray, v: np.ndarray) -> np.ndarray:
    return np.sqrt(share * v + (1 - share) * st.sigma_pop ** 2)


def _forecast(st: _Set, s: RoleSettings) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(low, mid, high) per point, clipped to the score scale."""
    c, share, v = _middle(st, s.h, s.k)
    sigma = _sigma(st, share, v)
    return (np.clip(c - s.q * sigma, LOW, HIGH), np.clip(c, LOW, HIGH), np.clip(c + s.q * sigma, LOW, HIGH))


def _mean(x: np.ndarray, w: np.ndarray) -> float:
    return float(np.sum(w * x) / np.sum(w))


def _evaluate(st: _Set, s: RoleSettings) -> dict[str, Any]:
    if len(st) == 0:
        return {"coverage": None, "mae": None, "width": None, "baseline_mae": None, "n_people": 0, "n_points": 0}
    low, mid, high = _forecast(st, s)
    w = st.weight
    return {
        "coverage": _mean((low <= st.score) & (st.score <= high), w),
        "mae": _mean(np.abs(st.score - mid), w),
        "width": _mean(high - low, w),
        "baseline_mae": _mean(np.abs(st.score - st.mu), w),
        "n_people": int(len(np.unique(st.person))),
        "n_points": int(len(st)),
    }


def _tune(st: _Set) -> RoleSettings:
    if len(st) == 0:
        raise ValueError("no training points to tune on")
    w = st.weight
    maes = [(_mean(np.abs(st.score - np.clip(_middle(st, h, k)[0], LOW, HIGH)), w), h, k)
            for h in H_GRID for k in K_GRID]
    _, h, k = min(maes, key=lambda t: t[0])  # min keeps the first in grid order on a tie
    c, share, v = _middle(st, h, k)
    sigma = _sigma(st, share, v)
    q = Q_GRID[:, None]
    covered = (np.clip(c - q * sigma, LOW, HIGH) <= st.score) & (st.score <= np.clip(c + q * sigma, LOW, HIGH))
    coverage = covered @ w / np.sum(w)
    ok = np.flatnonzero(coverage >= TARGET_COVERAGE)
    if not len(ok):
        raise ValueError(f"no q up to {Q_GRID[-1]} reaches {TARGET_COVERAGE:.0%} coverage")
    return RoleSettings(h, k, float(Q_GRID[ok[0]]))


def _sample(st: _Set, max_points: int | None) -> _Set:
    if max_points is None or len(st) <= max_points:
        return st
    return st.take(np.sort(np.random.default_rng(0).choice(len(st), max_points, replace=False)))


# ---------------------------------------------------------------- from Points (the tests' path)


def _cached(pop: Pop) -> Pop:
    cache: dict[int, tuple[float, float]] = {}
    return lambda y: cache[y] if y in cache else cache.setdefault(y, pop(y))


def _from_points(points: list[Point], pop: Pop, hs: Iterable[float]) -> _Set:
    pop = _cached(pop)
    stats = [pop(p.year) for p in points]
    sums: dict[float, tuple[np.ndarray, ...]] = {}
    for h in hs:
        rows = []
        for p in points:
            y = np.array([a for a, _ in p.history], dtype=float)
            x = np.array([b for _, b in p.history], dtype=float)
            w = np.ones_like(y) if math.isinf(h) else 0.5 ** ((y.max() - y) / h)
            rows.append((w.sum(), (w * x).sum(), (w * x * x).sum(), (w * w).sum()))
        sums[h] = tuple(np.array(c, dtype=float) for c in zip(*rows)) if rows else (np.empty(0),) * 4
    return _Set(np.array([p.person_id for p in points], dtype=np.int64), np.array([p.year for p in points]),
                np.array([p.score for p in points], dtype=float), np.array([p.weight for p in points], dtype=float),
                np.array([len(p.history) for p in points]), np.array([m for m, _ in stats], dtype=float),
                np.array([sd for _, sd in stats], dtype=float), sums)


def evaluate(points: list[Point], s: RoleSettings, pop: Pop) -> dict[str, Any]:
    return _evaluate(_from_points(points, pop, (s.h,)), s)


def tune(points: list[Point], pop: Pop, max_points: int | None = None) -> RoleSettings:
    """Tuned on every point given: callers pass the training points."""
    return _tune(_sample(_from_points(points, pop, H_GRID), max_points))


# ---------------------------------------------------------------- from the database (the real path)


@dataclass(frozen=True)
class _Rows:
    """A role's rated credits, one per person and film, sorted by person, date, film id."""
    person: np.ndarray
    movie: np.ndarray
    year: np.ndarray
    score: np.ndarray
    seg_start: np.ndarray  # per row: where the person's rows begin
    hist: np.ndarray  # per row: rated films with a strictly earlier date


def _load(con: sqlite3.Connection, role: Role, min_votes: int) -> _Rows:
    if role == "acting":
        credits, params = "SELECT DISTINCT person_id, movie_id FROM movie_cast", ()
    else:
        jobs = JOBS[role]
        credits = f"SELECT DISTINCT person_id, movie_id FROM movie_crew WHERE job IN ({','.join('?' * len(jobs))})"
        params = jobs
    cur = con.cursor()
    cur.row_factory = None  # plain tuples, whatever the connection uses
    rows = cur.execute(f"""SELECT c.person_id, m.id, CAST(REPLACE({DATE_KEY}, '-', '') AS INTEGER), m.year,
                                  m.vote_average
                           FROM ({credits}) c JOIN movies m ON m.id = c.movie_id
                           WHERE {RATED} ORDER BY c.person_id, {ORDER}""", (*params, min_votes)).fetchall()
    a = np.array(rows, dtype=float).reshape(-1, 5)
    person, movie, key = a[:, 0].astype(np.int64), a[:, 1].astype(np.int64), a[:, 2].astype(np.int64)
    idx = np.arange(len(a))
    new_person = np.ones(len(a), dtype=bool)
    new_person[1:] = person[1:] != person[:-1]
    new_date = new_person.copy()
    new_date[1:] |= key[1:] != key[:-1]
    seg_start = np.maximum.accumulate(np.where(new_person, idx, 0)) if len(a) else idx
    run_start = np.maximum.accumulate(np.where(new_date, idx, 0)) if len(a) else idx
    return _Rows(person, movie, a[:, 3].astype(np.int64), a[:, 4], seg_start, run_start - seg_start)


def _point_rows(r: _Rows) -> tuple[np.ndarray, np.ndarray]:
    """(row indices of the points, their weights)."""
    pts = np.flatnonzero(r.hist >= MIN_RATED)
    _, inverse, counts = np.unique(r.person[pts], return_inverse=True, return_counts=True)
    return pts, 1.0 / counts[inverse]


def next_film_points(con: sqlite3.Connection, role: Role, min_votes: int) -> list[Point]:
    r = _load(con, role, min_votes)
    pts, weights = _point_rows(r)
    return [Point(int(r.person[j]), [(int(y), float(x)) for y, x in zip(r.year[a:a + n], r.score[a:a + n])],
                  int(r.year[j]), float(r.score[j]), float(w))
            for j, w, a, n in zip(pts, weights, r.seg_start[pts], r.hist[pts])]


def _pop_table(r: _Rows, years: np.ndarray) -> dict[int, tuple[float, float] | None]:
    """pop(year) for each year: the population_stats of the films (each once) from the 10 years before."""
    _, first = np.unique(r.movie, return_index=True)
    fy, fs = r.year[first], r.score[first]
    out: dict[int, tuple[float, float] | None] = {}
    for y in np.unique(years).tolist():
        x = fs[(fy >= y - POP_YEARS) & (fy <= y - 1)]
        out[y] = (float(x.mean()), float(x.std())) if len(x) else None
    return out


def _role_set(con: sqlite3.Connection, role: Role, min_votes: int) -> _Set:
    r = _load(con, role, min_votes)
    pts, weights = _point_rows(r)
    pop = _pop_table(r, r.year[pts])
    keep = np.array([pop[y] is not None for y in r.year[pts].tolist()], dtype=bool)
    pts, weights = pts[keep], weights[keep]  # weights stay 1 / all of the person's points
    sums = {h: tuple(np.empty(len(pts)) for _ in range(4)) for h in H_GRID}
    starts = r.seg_start[pts]
    bounds = np.flatnonzero(np.r_[True, starts[1:] != starts[:-1], True]) if len(pts) else np.zeros(1, np.int64)
    for lo, hi in zip(bounds[:-1], bounds[1:]):  # one person's points: pts[lo:hi]
        a = starts[lo]
        last = a + r.hist[pts[hi - 1]]  # the longest history among them
        y, x = r.year[a:last].astype(float), r.score[a:last]
        idx = r.hist[pts[lo:hi]] - 1  # the end of each point's history
        latest = np.maximum.accumulate(y)[idx]
        for h in H_GRID:
            if math.isinf(h):
                g, f = np.ones_like(y), np.ones_like(latest)
            else:  # 0.5 ** ((L - y) / h) = 2 ** ((y - y0) / h) * 2 ** (-(L - y0) / h), y0 keeps it in range
                g, f = 2.0 ** ((y - y[0]) / h), 2.0 ** (-(latest - y[0]) / h)
            for out, part, scale in zip(sums[h], (g, g * x, g * x * x, g * g), (f, f, f, f * f)):
                out[lo:hi] = np.cumsum(part)[idx] * scale
    stats = [pop[y] for y in r.year[pts].tolist()]
    return _Set(r.person[pts], r.year[pts], r.score[pts], weights, r.hist[pts],
                np.array([m for m, _ in stats], dtype=float), np.array([sd for _, sd in stats], dtype=float), sums)


def build_artifact(con: sqlite3.Connection, min_votes: int, built_at: str,
                   max_points: int | None = MAX_POINTS) -> dict[str, Any]:
    end = latest_year(con)
    roles: dict[str, Any] = {}
    acting: RoleSettings | None = None
    for role in CAREER_ROLES:  # acting first: the fallback roles take its settings
        st = _role_set(con, role, min_votes)
        train, test = st.take(st.year < TEST_FROM), st.take(st.year >= TEST_FROM)
        fallback = role != "acting" and len(np.unique(test.person)) < MIN_PEOPLE
        s = acting if fallback else _tune(_sample(train, max_points))
        if role == "acting":
            acting = s
        mu, sigma_pop = population_stats(con, role, min_votes, end)
        test_stats = {k: round(v, 4) if isinstance(v, float) else v for k, v in _evaluate(test, s).items()}
        roles[role] = {"h": None if math.isinf(s.h) else s.h, "k": s.k, "q": s.q, "mu": round(mu, 4),
                       "sigma_pop": round(sigma_pop, 4), "fallback": fallback, "test": test_stats}
    return {"version": VERSION, "built_at": built_at, "roles": roles}


def _fmt(v: float | None, spec: str) -> str:
    return "-" if v is None else format(v, spec)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ml.career.backtest")
    ap.add_argument("--db", type=Path, default=DB_FILE)
    ap.add_argument("--out", type=Path, default=OUT_FILE)
    ap.add_argument("--max-points", type=int, default=MAX_POINTS)
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    con = sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        art = build_artifact(con, MIN_VOTES, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             args.max_points)
    finally:
        con.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(art, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"{'role':<10} {'h':>5} {'k':>4} {'q':>5} {'coverage':>9} {'MAE':>6} {'base MAE':>9} {'width':>6} "
          f"{'people':>7} {'points':>8}  fallback")
    for role, r in art["roles"].items():
        t = r["test"]
        print(f"{role:<10} {'inf' if r['h'] is None else _fmt(r['h'], 'g'):>5} {_fmt(r['k'], 'g'):>4} "
              f"{_fmt(r['q'], '.2f'):>5} {_fmt(t['coverage'], '.3f'):>9} {_fmt(t['mae'], '.3f'):>6} "
              f"{_fmt(t['baseline_mae'], '.3f'):>9} {_fmt(t['width'], '.2f'):>6} {t['n_people']:>7} "
              f"{t['n_points']:>8}  {r['fallback']}")
    print(f"wrote {args.out} in {time.perf_counter() - t0:.0f} s", file=sys.stderr)


if __name__ == "__main__":
    main()
