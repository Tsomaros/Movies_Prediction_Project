"""Track-record features for directors, actors and companies, from earlier films only.

    History.from_db(con)                     -> every person's dated films, loaded once
    history.person(person_id, role, as_of)   -> PERSON_FEATURES for one person (neutral values when unknown)
    history.director_features(ids, as_of)    -> director_* columns (the most experienced of the film's directors)
    history.actor_features(ids, as_of)       -> actors_*_{max,mean,min} over the first N_ACTORS billed
    history.resolve(ref, role)               -> person id for a form reference {"id", "name"}, or None if new
    history.priors(as_of)                    -> (typical log revenue, typical score) at that date
    history.typical_budget(as_of)            -> typical log budget at that date
    Companies.from_db(con)                   -> every company's dated budgets
    companies.features(refs, as_of, typical) -> company_budget (the biggest earlier spender among the companies)

Leak-safety rules:
- History means films released strictly before `as_of`, so a film never counts towards itself.
- An earlier film's revenue and score only count once it is MATURE_DAYS old at `as_of`; before that
  it adds to the film count but not to the medians. Its budget counts from its release (a budget is
  known before release, so nothing about it is still coming in).
- Medians are shrunk towards the typical film at `as_of` (built from earlier films only):
  (n * own + SHRINK_FILMS * typical) / (n + SHRINK_FILMS).
- Franchise experience counts earlier films that already had an earlier film in their collection
  (a sequel at the time), because collection membership of a first film can come from later sequels.

Known limitation: an earlier film's score is its current TMDB rating, not its rating at `as_of`.
"""

from __future__ import annotations

import heapq
import sqlite3
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import numpy as np
import pandas as pd

from ml.data.clean import INCOMPLETE_DAYS

SHRINK_FILMS = 4  # the typical film counts as this many extra films
MATURE_DAYS = INCOMPLETE_DAYS  # revenue and score count once a film is this old
LOG_BUDGET_SQL = "CASE WHEN budget IS NOT NULL AND NOT money_suspect THEN LN(budget_2025) END"  # = v_train_budget
N_ACTORS = 5  # first-billed actors used (the form requires 5)
ROLES = ("director", "actor")
PERSON_FEATURES = ("n_films", "years_active", "revenue", "score", "franchise_films", "is_new")
# person() also returns "budget"; it goes into BUDGET_FEATURES, which come last in the features table
BUDGET_FEATURES = ("director_budget", *(f"actors_budget_{a}" for a in ("max", "mean", "min")),
                   "company_budget", "franchise_budget")  # the budget track record (log 2025 $)
AGGREGATES = ("max", "mean", "min")


def day_number(d: date | str | np.datetime64) -> int:
    return int(np.datetime64(d, "D").astype(np.int64))


@dataclass
class _Values:
    """One kind of value (revenue, score or budget) for every track, packed: track t's values are
    values[offsets[t]:offsets[t + 1]], sorted by the day they belong to."""

    days: np.ndarray  # int64
    values: np.ndarray  # float64: log revenue / score / log budget (2025 dollars for money)
    offsets: np.ndarray  # int64, number of tracks + 1

    @classmethod
    def pack(cls, track_of_row: np.ndarray, n_tracks: int, days: np.ndarray, values: np.ndarray) -> _Values:
        ok = ~np.isnan(values)
        counts = np.bincount(track_of_row[ok], minlength=n_tracks)
        return cls(days[ok], values[ok], np.concatenate([[0], np.cumsum(counts)]).astype(np.int64))

    def until(self, track: int, day: int, side: str) -> np.ndarray:
        """Track's values dated before `day` (side="left") or on or before it (side="right")."""
        s, e = self.offsets[track], self.offsets[track + 1]
        return self.values[s:s + int(np.searchsorted(self.days[s:e], day, side))]


class NameMap:
    """Exact lookups of a casefolded name -> id, packed: names in one sorted bytes blob with int64 offsets, found
    by binary search. A dict of the 344k person names took 83 MB in Docker (Day 9); this takes about 10 MB."""

    def __init__(self, keys: Iterable[str], ids: Iterable[int]) -> None:
        encoded, ids = [k.encode("utf-8") for k in keys], list(ids)
        order = sorted(range(len(encoded)), key=encoded.__getitem__)
        self.blob = b"".join(encoded[i] for i in order)
        self.offsets = np.concatenate([[0], np.cumsum([len(encoded[i]) for i in order])]).astype(np.int64)
        self.ids = np.array([ids[i] for i in order], dtype=np.int64)

    def _key(self, i: int) -> bytes:
        return self.blob[self.offsets[i]:self.offsets[i + 1]]

    def get(self, key: str) -> int | None:
        target, lo, hi = key.encode("utf-8"), 0, len(self.ids)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._key(mid) < target:
                lo = mid + 1
            else:
                hi = mid
        return int(self.ids[lo]) if lo < len(self.ids) and self._key(lo) == target else None

    def __len__(self) -> int:
        return len(self.ids)


@dataclass
class Groups:
    """Rows sorted by a group id (a company, a collection), packed: group g's rows are offsets[g]:offsets[g + 1].
    Replaces a dict of one small array per group (the 47k companies and collections took about 50 MB)."""

    ids: np.ndarray  # sorted group ids, int64
    offsets: np.ndarray  # int64, len(ids) + 1

    @classmethod
    def of(cls, group_of_row: np.ndarray) -> Groups:
        """group_of_row must be sorted (rows ordered by group, then day)."""
        ids, starts = np.unique(np.asarray(group_of_row, dtype=np.int64), return_index=True)
        return cls(ids, np.r_[starts, len(group_of_row)].astype(np.int64))

    def span(self, group_id: int | None) -> tuple[int, int] | None:
        """(start, end) of the group's rows, or None if the group has none."""
        if group_id is None:
            return None
        i = int(np.searchsorted(self.ids, group_id))
        if i < len(self.ids) and self.ids[i] == group_id:
            return int(self.offsets[i]), int(self.offsets[i + 1])
        return None

    def __contains__(self, group_id: int) -> bool:
        return self.span(group_id) is not None


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
        """films: id, release_date, collection_id, log_revenue, score, log_budget (each NaN if unusable).
        credits: person_id, movie_id, role ("director" or "actor"). people: id, name."""
        films = films.copy()
        films["day"] = pd.to_datetime(films["release_date"]).values.astype("datetime64[D]").astype(np.int64)
        films["sequel"] = _sequel_flags(films)
        self.revenue_typical = _ExpandingMedian(*_available(films, "log_revenue"))
        self.score_typical = _ExpandingMedian(*_available(films, "score"))
        self.budget_typical = _ExpandingMedian(*_available(films, "log_budget", delay=1))

        used = films[["id", "day", "sequel", "log_revenue", "score", "log_budget"]]  # numbers only: a smaller merge
        rows = credits.merge(used, left_on="movie_id", right_on="id")
        rows = rows.sort_values(["role", "person_id", "day"], kind="stable").reset_index(drop=True)
        # A track is one person's films in one role. Everything is packed into a few flat arrays sorted by
        # (role, person, day): track t's films are rows row_offsets[t]:row_offsets[t + 1]. One small object per
        # person took about 870 MB for the 350k tracks; this takes a few tens of MB.
        role = rows["role"].to_numpy()
        person = rows["person_id"].to_numpy(np.int64)
        new_track = np.r_[True, (role[1:] != role[:-1]) | (person[1:] != person[:-1])] if len(rows) else np.zeros(0, bool)
        track_of_row = np.cumsum(new_track) - 1
        starts = np.flatnonzero(new_track)
        n_tracks = len(starts)
        self.row_offsets = np.r_[starts, len(rows)].astype(np.int64)
        self.days = rows["day"].to_numpy(np.int64)
        self.sequels = np.r_[0, np.cumsum(rows["sequel"].to_numpy())].astype(np.int32)  # sequels among rows[:i]
        self.revenue = _Values.pack(track_of_row, n_tracks, self.days, rows["log_revenue"].to_numpy(float))
        self.score = _Values.pack(track_of_row, n_tracks, self.days, rows["score"].to_numpy(float))
        self.budget = _Values.pack(track_of_row, n_tracks, self.days, rows["log_budget"].to_numpy(float))
        # role -> sorted person ids and the index of each one's track
        self.people = {r: person[starts][role[starts] == r] for r in ROLES}
        self.first_track = {r: np.flatnonzero(role[starts] == r) for r in ROLES}

        # Name lookup for free-text form entries: lower-cased name -> the person with the most films in that role.
        counts = credits.groupby(["person_id", "role"]).size().rename("n").reset_index()
        named = counts.merge(people, left_on="person_id", right_on="id")
        named["key"] = named["name"].str.casefold()
        named = named.sort_values(["role", "key", "n", "person_id"], ascending=[True, True, False, True])
        named = named.drop_duplicates(["role", "key"])
        self.by_name = {r: NameMap(g["key"], g["person_id"]) for r, g in named.groupby("role")}

    def _track(self, person_id: int | None, role: str) -> int | None:
        """Index of the person's track in that role, or None if they have no film in it."""
        if person_id is None:
            return None
        ids = self.people[role]
        i = int(np.searchsorted(ids, person_id))
        return int(self.first_track[role][i]) if i < len(ids) and ids[i] == person_id else None

    @classmethod
    def from_db(cls, con: sqlite3.Connection) -> History:
        films = load_films(con)
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

    def typical_budget(self, as_of: int) -> float:
        return self.budget_typical.at(as_of)

    def resolve(self, ref: dict[str, Any] | None, role: str) -> int | None:
        """An id we know in this role, else a case-insensitive name match, else None (a new person)."""
        if not ref:
            return None
        if ref.get("id") is not None and self._track(int(ref["id"]), role) is not None:
            return int(ref["id"])
        if ref.get("name"):
            return self.by_name[role].get(ref["name"].strip().casefold()) if role in self.by_name else None
        return None

    def person(self, person_id: int | None, role: str, as_of: int) -> dict[str, float]:
        typical_revenue, typical_score = self.priors(as_of)
        typical_budget = self.typical_budget(as_of)
        track = self._track(person_id, role)
        if track is not None:
            s, e = self.row_offsets[track], self.row_offsets[track + 1]
            n = int(np.searchsorted(self.days[s:e], as_of, "left"))
        else:
            n = 0
        if n == 0:
            return {"n_films": 0, "years_active": 0.0, "revenue": typical_revenue, "score": typical_score,
                    "budget": typical_budget, "franchise_films": 0, "is_new": 1}
        mature = as_of - MATURE_DAYS
        return {
            "n_films": n,
            "years_active": (as_of - int(self.days[s])) / 365.25,
            "revenue": _shrunk(self.revenue.until(track, mature, "right"), typical_revenue),
            "score": _shrunk(self.score.until(track, mature, "right"), typical_score),
            "budget": _shrunk(self.budget.until(track, as_of, "left"), typical_budget),
            "franchise_films": int(self.sequels[s + n] - self.sequels[s]),
            "is_new": 0,
        }

    def director_features(self, person_ids: Iterable[int | None], as_of: int) -> dict[str, float]:
        candidates = [self.person(pid, "director", as_of) for pid in person_ids] or [self.person(None, "director", as_of)]
        best = max(candidates, key=lambda f: f["n_films"])  # first listed wins a tie
        return {f"director_{k}": best[k] for k in PERSON_FEATURES}

    def actor_features(self, person_ids: Iterable[int | None], as_of: int) -> dict[str, float]:
        return self._actor_aggregates(person_ids, as_of, PERSON_FEATURES)

    def budget_features(self, director_ids: Iterable[int | None], actor_ids: Iterable[int | None],
                        as_of: int) -> dict[str, float]:
        """director_budget and actors_budget_{max,mean,min}: shrunk median earlier log budgets."""
        candidates = [self.person(pid, "director", as_of) for pid in director_ids] or [self.person(None, "director", as_of)]
        best = max(candidates, key=lambda f: f["n_films"])  # the same director as director_features
        return {"director_budget": best["budget"], **self._actor_aggregates(actor_ids, as_of, ("budget",))}

    def _actor_aggregates(self, person_ids: Iterable[int | None], as_of: int, keys: tuple[str, ...]) -> dict[str, float]:
        ids = list(person_ids)[:N_ACTORS]
        ids += [None] * (N_ACTORS - len(ids))  # missing slots count as new actors
        rows = [self.person(pid, "actor", as_of) for pid in ids]
        out = {}
        for k in keys:
            values = np.array([r[k] for r in rows], dtype=float)
            out.update({f"actors_{k}_max": float(values.max()), f"actors_{k}_mean": float(values.mean()),
                        f"actors_{k}_min": float(values.min())})
        return out


class Companies:
    def __init__(self, films: pd.DataFrame, credits: pd.DataFrame, companies: pd.DataFrame) -> None:
        """films: id, release_date, log_budget (NaN if unusable). credits: company_id, movie_id. companies: id, name."""
        rows = credits.merge(films[films["log_budget"].notna()], left_on="movie_id", right_on="id")
        rows["day"] = pd.to_datetime(rows["release_date"]).values.astype("datetime64[D]").astype(np.int64)
        rows = rows.sort_values(["company_id", "day"], kind="stable")
        self.groups = Groups.of(rows["company_id"].to_numpy())
        self.days = rows["day"].to_numpy(np.int64)
        self.budget = rows["log_budget"].to_numpy(float)
        # Name lookup for free-text form entries: lower-cased name -> the company with the most films.
        counts = credits.groupby("company_id").size().rename("n").reset_index()
        named = counts.merge(companies, left_on="company_id", right_on="id")
        named["key"] = named["name"].str.casefold()
        named = named.sort_values(["key", "n", "company_id"], ascending=[True, False, True])
        named = named.drop_duplicates("key")
        self.by_name = NameMap(named["key"], named["company_id"])

    @classmethod
    def from_db(cls, con: sqlite3.Connection) -> Companies:
        return cls(load_films(con), pd.read_sql_query("SELECT company_id, movie_id FROM movie_companies", con),
                   pd.read_sql_query("SELECT id, name FROM companies", con))

    def resolve(self, ref: dict[str, Any] | None) -> int | None:
        """The ref's id, else a case-insensitive name match, else None (a new company)."""
        if not ref:
            return None
        if ref.get("id") is not None:
            return int(ref["id"])
        return self.by_name.get((ref.get("name") or "").strip().casefold())

    def budget_of(self, company_id: int | None, as_of: int, typical: float) -> tuple[int, float]:
        """(number of earlier budgets, shrunk median earlier log budget) for one company."""
        span = self.groups.span(company_id)
        if span is None:
            return 0, typical
        s, e = span
        n = int(np.searchsorted(self.days[s:e], as_of, "left"))
        return n, (_shrunk(self.budget[s:s + n], typical) if n else typical)

    def features(self, refs: Iterable[dict[str, Any]], as_of: int, typical: float) -> dict[str, float]:
        """The highest shrunk budget among the companies with earlier budgets; the typical budget when none has."""
        known = [b for n, b in (self.budget_of(self.resolve(r), as_of, typical) for r in refs) if n]
        return {"company_budget": max(known) if known else typical}


def load_films(con: sqlite3.Connection) -> pd.DataFrame:
    """Every dated film with the revenue, score and budget it may contribute (NaN when unusable)."""
    return pd.read_sql_query(
        f"""
        SELECT id, release_date, collection_id,
               CASE WHEN budget IS NOT NULL AND revenue IS NOT NULL AND NOT money_suspect
                         AND NOT revenue_incomplete THEN LN(revenue_2025) END AS log_revenue,
               CASE WHEN score_ok THEN vote_average END AS score,
               {LOG_BUDGET_SQL} AS log_budget
        FROM movies WHERE release_date IS NOT NULL
        """,  # revenue rule = v_train_revenue, score rule = v_train_score, budget rule = v_train_budget
        con,
    )


def typical_at(films: pd.DataFrame, days: np.ndarray) -> pd.DataFrame:
    """The typical film's log revenue and score at each day, from earlier films only (the shrinkage targets)."""
    films = films.assign(day=pd.to_datetime(films["release_date"]).values.astype("datetime64[D]").astype(np.int64))
    revenue, score = _ExpandingMedian(*_available(films, "log_revenue")), _ExpandingMedian(*_available(films, "score"))
    return pd.DataFrame({"typical_revenue": [revenue.at(int(d)) for d in days],
                         "typical_score": [score.at(int(d)) for d in days]})


def _sequel_flags(films: pd.DataFrame) -> np.ndarray:
    """1 when the film's collection already had a film released strictly earlier."""
    first_day = films.groupby("collection_id")["day"].transform("min")
    return (films["collection_id"].notna() & (films["day"] > first_day)).astype(int).to_numpy()


def _available(films: pd.DataFrame, column: str, delay: int = MATURE_DAYS) -> tuple[np.ndarray, np.ndarray]:
    """(day the value may first be used, value) for films that have it; delay=1 means from the day after release."""
    have = films[films[column].notna()]
    return (have["day"] + delay).to_numpy(np.int64), have[column].to_numpy(float)


def feature_names() -> list[str]:
    return [f"director_{k}" for k in PERSON_FEATURES] + [
        f"actors_{k}_{a}" for k in PERSON_FEATURES for a in AGGREGATES
    ]
