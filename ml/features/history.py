"""Track-record features for directors and actors, from earlier films only.

    History.from_db(con)                     -> every person's dated films, loaded once
    history.person(person_id, role, as_of)   -> PERSON_FEATURES for one person (neutral values when unknown)
    history.director_features(ids, as_of)    -> director_* columns (the most experienced of the film's directors)
    history.actor_features(ids, as_of)       -> actors_*_{max,mean,min} over the first N_ACTORS billed
    history.resolve(ref, role)               -> person id for a form reference {"id", "name"}, or None if new
    history.priors(as_of)                    -> (typical log revenue, typical score) at that date

Leak-safety rules:
- History means films released strictly before `as_of`, so a film never counts towards itself.
- An earlier film's revenue and score only count once it is MATURE_DAYS old at `as_of`; before that
  it adds to the film count but not to the medians.
- Medians are shrunk towards the typical film at `as_of` (built from earlier films only):
  (n * own + SHRINK_FILMS * typical) / (n + SHRINK_FILMS).
- Franchise experience counts earlier films that already had an earlier film in their collection
  (a sequel at the time), because collection membership of a first film can come from later sequels.

Known limitation: an earlier film's score is its current TMDB rating, not its rating at `as_of`.
"""

from __future__ import annotations

import heapq
import sqlite3
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import numpy as np
import pandas as pd

from ml.data.clean import INCOMPLETE_DAYS

SHRINK_FILMS = 4  # the typical film counts as this many extra films
MATURE_DAYS = INCOMPLETE_DAYS  # revenue and score count once a film is this old
N_ACTORS = 5  # first-billed actors used (the form requires 5)
ROLES = ("director", "actor")
PERSON_FEATURES = ("n_films", "years_active", "revenue", "score", "franchise_films", "is_new")
AGGREGATES = ("max", "mean", "min")


def day_number(d: date | str | np.datetime64) -> int:
    return int(np.datetime64(d, "D").astype(np.int64))


@dataclass
class _Track:
    """One person's films in one role, sorted by date (days since 1970-01-01)."""

    dates: np.ndarray
    sequel_cumsum: np.ndarray  # sequel_cumsum[i] = sequels among the first i films
    revenue_dates: np.ndarray
    revenue: np.ndarray  # log revenue in 2025 dollars
    score_dates: np.ndarray
    score: np.ndarray


class _ExpandingMedian:
    """Median of all values that became available on or before a day, for any day."""

    def __init__(self, available: np.ndarray, values: np.ndarray) -> None:
        order = np.argsort(available, kind="stable")
        available, values = available[order], values[order]
        low: list[float] = []  # max-heap (negated) of the lower half
        high: list[float] = []  # min-heap of the upper half
        days, medians = [], []
        for i, (day, v) in enumerate(zip(available, values)):
            if not low or v <= -low[0]:
                heapq.heappush(low, -v)
            else:
                heapq.heappush(high, v)
            if len(low) > len(high) + 1:
                heapq.heappush(high, -heapq.heappop(low))
            elif len(high) > len(low):
                heapq.heappush(low, -heapq.heappop(high))
            if i + 1 == len(available) or available[i + 1] != day:  # last value of this day
                days.append(day)
                medians.append(-low[0] if len(low) > len(high) else (-low[0] + high[0]) / 2)
        self.days, self.medians = np.array(days, dtype=np.int64), np.array(medians)

    def at(self, day: int) -> float:
        i = bisect_right(self.days, day) - 1
        return float(self.medians[i]) if i >= 0 else float("nan")


def _shrunk(values: np.ndarray, typical: float) -> float:
    if len(values) == 0:
        return typical
    n = len(values)
    return (n * float(np.median(values)) + SHRINK_FILMS * typical) / (n + SHRINK_FILMS)


class History:
    def __init__(self, films: pd.DataFrame, credits: pd.DataFrame, people: pd.DataFrame) -> None:
        """films: id, release_date, collection_id, log_revenue (NaN if unusable), score (NaN if not score_ok).
        credits: person_id, movie_id, role ("director" or "actor"). people: id, name."""
        films = films.copy()
        films["day"] = pd.to_datetime(films["release_date"]).values.astype("datetime64[D]").astype(np.int64)
        films["sequel"] = _sequel_flags(films)
        self.revenue_typical = _ExpandingMedian(*_available(films, "log_revenue"))
        self.score_typical = _ExpandingMedian(*_available(films, "score"))

        rows = credits.merge(films, left_on="movie_id", right_on="id")
        rows = rows.sort_values(["role", "person_id", "day"], kind="stable").reset_index(drop=True)
        # One flat sorted array per column; each track is a view into it (no per-person copies).
        keys = list(zip(rows["person_id"].astype(int), rows["role"]))
        day, sequel = rows["day"].to_numpy(np.int64), rows["sequel"].to_numpy()
        revenue, score = rows["log_revenue"].to_numpy(float), rows["score"].to_numpy(float)
        starts = np.flatnonzero(np.r_[True, [a != b for a, b in zip(keys[1:], keys[:-1])]])
        ends = np.r_[starts[1:], len(rows)]
        self.tracks: dict[tuple[int, str], _Track] = {}
        for s, e in zip(starts, ends):
            rev_ok, score_ok = ~np.isnan(revenue[s:e]), ~np.isnan(score[s:e])
            self.tracks[keys[s]] = _Track(
                dates=day[s:e],
                sequel_cumsum=np.concatenate([[0], np.cumsum(sequel[s:e])]),
                revenue_dates=day[s:e][rev_ok],
                revenue=revenue[s:e][rev_ok],
                score_dates=day[s:e][score_ok],
                score=score[s:e][score_ok],
            )

        # Name lookup for free-text form entries: lower-cased name -> the person with the most films in that role.
        counts = credits.groupby(["person_id", "role"]).size().rename("n").reset_index()
        named = counts.merge(people, left_on="person_id", right_on="id")
        named["key"] = named["name"].str.casefold()
        named = named.sort_values(["role", "key", "n", "person_id"], ascending=[True, True, False, True])
        self.by_name = {(r.role, r.key): int(r.person_id) for r in named.drop_duplicates(["role", "key"]).itertuples()}
        self.known_ids = {role: {pid for pid, r in self.tracks if r == role} for role in ROLES}

    @classmethod
    def from_db(cls, con: sqlite3.Connection) -> History:
        films = pd.read_sql_query(
            """
            SELECT id, release_date, collection_id,
                   CASE WHEN budget IS NOT NULL AND revenue IS NOT NULL AND NOT money_suspect
                             AND NOT revenue_incomplete THEN LN(revenue_2025) END AS log_revenue,
                   CASE WHEN score_ok THEN vote_average END AS score
            FROM movies WHERE release_date IS NOT NULL
            """,  # revenue rule = v_train_revenue, score rule = v_train_score
            con,
        )
        credits = pd.read_sql_query(
            """
            SELECT DISTINCT person_id, movie_id, 'director' AS role FROM movie_crew WHERE job = 'Director'
            UNION ALL
            SELECT person_id, movie_id, 'actor' FROM movie_cast
            """,
            con,
        )
        people = pd.read_sql_query("SELECT id, name FROM people", con)
        return cls(films, credits, people)

    # ------------------------------------------------------------ queries

    def priors(self, as_of: int) -> tuple[float, float]:
        return self.revenue_typical.at(as_of), self.score_typical.at(as_of)

    def resolve(self, ref: dict[str, Any] | None, role: str) -> int | None:
        """An id we know in this role, else a case-insensitive name match, else None (a new person)."""
        if not ref:
            return None
        if ref.get("id") is not None and ref["id"] in self.known_ids[role]:
            return int(ref["id"])
        if ref.get("name"):
            return self.by_name.get((role, ref["name"].strip().casefold()))
        return None

    def person(self, person_id: int | None, role: str, as_of: int) -> dict[str, float]:
        typical_revenue, typical_score = self.priors(as_of)
        track = self.tracks.get((person_id, role)) if person_id is not None else None
        n = bisect_left(track.dates, as_of) if track is not None else 0
        if n == 0:
            return {"n_films": 0, "years_active": 0.0, "revenue": typical_revenue, "score": typical_score,
                    "franchise_films": 0, "is_new": 1}
        mature = as_of - MATURE_DAYS
        revenue = track.revenue[: bisect_right(track.revenue_dates, mature)]
        score = track.score[: bisect_right(track.score_dates, mature)]
        return {
            "n_films": n,
            "years_active": (as_of - int(track.dates[0])) / 365.25,
            "revenue": _shrunk(revenue, typical_revenue),
            "score": _shrunk(score, typical_score),
            "franchise_films": int(track.sequel_cumsum[n]),
            "is_new": 0,
        }

    def director_features(self, person_ids: Iterable[int | None], as_of: int) -> dict[str, float]:
        candidates = [self.person(pid, "director", as_of) for pid in person_ids] or [self.person(None, "director", as_of)]
        best = max(candidates, key=lambda f: f["n_films"])  # first listed wins a tie
        return {f"director_{k}": v for k, v in best.items()}

    def actor_features(self, person_ids: Iterable[int | None], as_of: int) -> dict[str, float]:
        ids = list(person_ids)[:N_ACTORS]
        ids += [None] * (N_ACTORS - len(ids))  # missing slots count as new actors
        rows = [self.person(pid, "actor", as_of) for pid in ids]
        out = {}
        for k in PERSON_FEATURES:
            values = np.array([r[k] for r in rows], dtype=float)
            out.update({f"actors_{k}_max": float(values.max()), f"actors_{k}_mean": float(values.mean()),
                        f"actors_{k}_min": float(values.min())})
        return out


def _sequel_flags(films: pd.DataFrame) -> np.ndarray:
    """1 when the film's collection already had a film released strictly earlier."""
    first_day = films.groupby("collection_id")["day"].transform("min")
    return (films["collection_id"].notna() & (films["day"] > first_day)).astype(int).to_numpy()


def _available(films: pd.DataFrame, column: str) -> tuple[np.ndarray, np.ndarray]:
    """(day the value may first be used, value) for films that have it."""
    have = films[films[column].notna()]
    return (have["day"] + MATURE_DAYS).to_numpy(np.int64), have[column].to_numpy(float)


def feature_names() -> list[str]:
    return [f"director_{k}" for k in PERSON_FEATURES] + [
        f"actors_{k}_{a}" for k in PERSON_FEATURES for a in AGGREGATES
    ]
