"""The Career section's chart and track-record forecast (Day 14.8): GET /people/{id}/career.

    CareerArtifact                  -> ml/artifacts/career_forecast.json as loaded: year_averages {int year: avg},
                                       roles {role: {h (None = every film counts the same), k, q, mu, sigma_pop,
                                       fallback, test}}
    load_career_artifact(path)      -> CareerArtifact; ValueError naming the file and `make career` when it is
                                       missing or lacks a field (the API then refuses to start)
    person_exists(con, person_id)   -> whether the person is in the database
    settings_of(art, role)          -> the role's RoleSettings for ml.career.forecast (h None -> math.inf)
    career_response(con, art, person_id, role)
                                    -> the /career body, or None for an unknown person; NoCredits when they have
                                       no film in that role (role None: their acting/directing/writing role with
                                       the most films)

Rated films (MIN_VOTES+ votes and a score) feed the line, the best film and the forecast; low-vote films are
only drawn. roles_available lists each role with 5+ rated films (MIN_RATED), plus the one shown.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.repo import career as repo
from backend.app.repo.career import CAREER_ROLES, Role
from backend.app.services.posters import poster
from ml.career.forecast import MIN_RATED, RoleSettings, rolling_line, track_record
from ml.data.clean import MIN_VOTES

MODEL_ROLES = ("acting", "directing")  # the score model has director and actor inputs, no writer
ROLE_FIELDS = ("h", "k", "q", "mu", "sigma_pop", "test")


class NoCredits(LookupError):
    pass


@dataclass(frozen=True)
class CareerArtifact:
    version: int
    built_at: str
    year_averages: dict[int, float]
    roles: dict[str, dict[str, Any]]


def load_career_artifact(path: Path) -> CareerArtifact:
    hint = f"{path}: rebuild it with `make career`"
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"The career forecast file is missing ({hint})") from None
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"The career forecast file can't be read ({hint}): {e}") from None
    try:
        roles = {role: data["roles"][role] for role in CAREER_ROLES}
        missing = [f"{role}.{f}" for role, r in roles.items() for f in ROLE_FIELDS if f not in r]
        if missing:
            raise KeyError(", ".join(missing))
        return CareerArtifact(data["version"], data["built_at"],
                              {int(y): float(v) for y, v in data["year_averages"].items()}, roles)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise ValueError(f"The career forecast file lacks {e} ({hint})") from None


def person_exists(con: sqlite3.Connection, person_id: int) -> bool:
    return con.execute("SELECT 1 FROM people WHERE id = ?", (person_id,)).fetchone() is not None


def settings_of(art: CareerArtifact, role: Role) -> RoleSettings:
    r = art.roles[role]
    return RoleSettings(math.inf if r["h"] is None else r["h"], r["k"], r["q"])


def _forecast(art: CareerArtifact, role: Role, rated: list[repo.CareerFilm]) -> dict[str, Any]:
    r = art.roles[role]
    test = {"coverage": r["test"]["coverage"], "n_people": r["test"]["n_people"]}
    f = track_record([(x["year"], x["score"]) for x in rated], settings_of(art, role), r["mu"], r["sigma_pop"])
    if f is None:
        return {"status": "not_enough_films", "low": None, "mid": None, "high": None, "explain": None, "test": test}
    return {"status": "ok", "low": round(f.low, 3), "mid": round(f.mid, 3), "high": round(f.high, 3),
            "explain": {"n_rated": f.n_rated, "half_life": r["h"], "own_share": round(f.own_share, 3),
                        "own_avg": round(f.own_avg, 3), "db_avg": f.db_avg},
            "test": test}


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
    rated = [f for f in films if f["rated"]]
    best = max(enumerate(rated), key=lambda t: (t[1]["score"], t[1]["vote_count"], t[0]), default=None)
    return {
        "person_id": person_id,
        "role": role,
        "roles_available": [r for r in roles if r["rated_count"] >= MIN_RATED or r["role"] == role],
        "films": [{**{k: v for k, v in f.items() if k != "poster_path"},
                   "poster_small": (poster(f["poster_path"]) or {}).get("small"),
                   "year_avg": art.year_averages.get(f["year"])} for f in films],
        "line": [{"year": y, "value": round(v, 3)} for y, v in rolling_line([(f["year"], f["score"]) for f in rated])],
        "best_film": None if best is None else {k: best[1][k] for k in ("movie_id", "title", "year", "score")},
        "latest_year_avg": art.year_averages[max(art.year_averages)] if art.year_averages else None,
        "forecast": _forecast(art, role, rated),
        "model_available": role in MODEL_ROLES and current["rated_count"] > 0,
    }
