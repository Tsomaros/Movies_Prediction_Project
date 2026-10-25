"""The Career section's chart and track-record forecasts (Day 14.8): GET /people/{id}/career.

    CareerArtifact                  -> ml/artifacts/career_forecast.json as loaded: roles {role: {score|revenue:
                                       {h (None = every film counts the same), k, q, mu, sigma_pop, fallback, test}}}
    load_career_artifact(path)      -> CareerArtifact; ValueError naming the file and `make career` when it is
                                       missing or lacks a field (the API then refuses to start)
    person_exists(con, person_id)   -> whether the person is in the database
    settings_of(art, role, metric="score")
                                    -> the role's RoleSettings for ml.career.forecast (h None -> math.inf)
    career_response(con, art, person_id, role)
                                    -> the /career body, or None for an unknown person; NoCredits when they have
                                       no film in that role (role None: their acting/directing/writing role with
                                       the most films)

Each metric has its own line, best film and forecast (`metrics.score`, `metrics.revenue`). Score: rated films
(MIN_VOTES+ votes and a score); low-vote films are only drawn. Revenue: films with a trusted revenue_2025
(repo/career), worked on in log dollars like the backtest and given back in whole 2025 dollars: the line is a
rolling geometric mean, own_avg and db_avg are exp of the weighted log means. A forecast needs MIN_RATED films with
a value. roles_available lists each role with 5+ rated films (MIN_RATED), plus the one shown.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.repo import career as repo
from backend.app.repo.career import CAREER_METRICS, CAREER_ROLES, Metric, Role
from backend.app.services.posters import poster
from ml.career.forecast import HIGH, LOW, MIN_RATED, RoleSettings, rolling_line, track_record
from ml.data.clean import MIN_VOTES

MODEL_ROLES = ("acting", "directing")  # the score model has director and actor inputs, no writer
ROLE_FIELDS = ("h", "k", "q", "mu", "sigma_pop", "test")


class NoCredits(LookupError):
    pass


@dataclass(frozen=True)
class CareerArtifact:
    version: int
    built_at: str
    roles: dict[str, dict[str, dict[str, Any]]]


def load_career_artifact(path: Path) -> CareerArtifact:
    hint = f"{path}: rebuild it with `make career`"
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"The career forecast file is missing ({hint})") from None
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"The career forecast file can't be read ({hint}): {e}") from None
    try:
        roles = {role: {metric: data["roles"][role][metric] for metric in CAREER_METRICS} for role in CAREER_ROLES}
        missing = [f"{role}.{metric}.{f}" for role, r in roles.items() for metric, m in r.items()
                   for f in ROLE_FIELDS if f not in m]
        if missing:
            raise KeyError(", ".join(missing))
        return CareerArtifact(data["version"], data["built_at"], roles)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise ValueError(f"The career forecast file lacks {e} ({hint})") from None


def person_exists(con: sqlite3.Connection, person_id: int) -> bool:
    return con.execute("SELECT 1 FROM people WHERE id = ?", (person_id,)).fetchone() is not None


def settings_of(art: CareerArtifact, role: Role, metric: Metric = "score") -> RoleSettings:
    r = art.roles[role][metric]
    return RoleSettings(math.inf if r["h"] is None else r["h"], r["k"], r["q"])


def _out(metric: Metric, x: float) -> float | int:
    """A value as the API gives it: a score to 3 decimals, a log revenue as whole dollars."""
    return round(x, 3) if metric == "score" else round(math.exp(x))


def _forecast(art: CareerArtifact, role: Role, metric: Metric, history: list[tuple[int, float]]) -> dict[str, Any]:
    r = art.roles[role][metric]
    test = {"coverage": r["test"]["coverage"], "n_people": r["test"]["n_people"]}
    if metric == "revenue":
        test["within_2x"] = r["test"]["within_2x"]
    f = track_record(history, settings_of(art, role, metric), r["mu"], r["sigma_pop"],
                     bounds=(LOW, HIGH) if metric == "score" else None)
    if f is None:
        return {"status": "not_enough_films", "low": None, "mid": None, "high": None, "explain": None, "test": test}
    return {"status": "ok", "low": _out(metric, f.low), "mid": _out(metric, f.mid), "high": _out(metric, f.high),
            "explain": {"n_films": f.n_rated, "half_life": r["h"], "own_share": round(f.own_share, 3),
                        "own_avg": _out(metric, f.own_avg), "db_avg": _out(metric, f.db_avg)},
            "test": test}


def _metric(art: CareerArtifact, role: Role, metric: Metric, films: list[repo.CareerFilm]) -> dict[str, Any]:
    """{line, best_film, forecast} over the films with a value (oldest first)."""
    if metric == "score":
        counted = [(f, f["score"]) for f in films if f["rated"]]
        history = [(f["year"], v) for f, v in counted]
    else:
        counted = [(f, f["revenue"]) for f in films if f["revenue"] is not None]
        history = [(f["year"], math.log(v)) for f, v in counted]
    best = max(enumerate(counted), key=lambda t: (t[1][1], t[1][0]["vote_count"], t[0]), default=None)
    return {
        "line": [{"year": y, "value": _out(metric, v)} for y, v in rolling_line(history)],
        "best_film": None if best is None else {**{k: best[1][0][k] for k in ("movie_id", "title", "year")},
                                                "value": best[1][1] if metric == "score" else round(best[1][1])},
        "forecast": _forecast(art, role, metric, history),
    }


def career_response(con: sqlite3.Connection, art: CareerArtifact, person_id: int,
                    role: Role | None) -> dict[str, Any] | None:
    if not person_exists(con, person_id):
        return None
    roles = repo.roles_available(con, person_id, MIN_VOTES)
    if role is None:
        role = max(roles, key=lambda r: r["film_count"])["role"] if roles else None  # ties: CAREER_ROLES order
    current = next((r for r in roles if r["role"] == role), None)
    if current is None:
        raise NoCredits(role)
    films = repo.career_films(con, person_id, role, MIN_VOTES)  # oldest first
    return {
        "person_id": person_id,
        "role": role,
        "roles_available": [r for r in roles if r["rated_count"] >= MIN_RATED or r["role"] == role],
        "films": [{**{k: v for k, v in f.items() if k != "poster_path"},
                   "poster_small": (poster(f["poster_path"]) or {}).get("small")} for f in films],
        "metrics": {metric: _metric(art, role, metric, films) for metric in CAREER_METRICS},
        "model_available": role in MODEL_ROLES and current["rated_count"] > 0,
    }
