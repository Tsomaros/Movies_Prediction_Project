"""Read-only queries for the person pages' Career section (Day 14.8).

    career_films(con, person_id, role, min_votes)
                                    -> the person's dated films in that role, oldest first (one per film)
    roles_available(con, person_id, min_votes)
                                    -> [{role, film_count, rated_count}] for acting, directing, writing with films
    year_averages(con, min_votes)   -> {year: mean score of the rated films released that year}
    population_stats(con, role, min_votes, end_year)
                                    -> (mean, population sd) of rated films in that role from the 10 years to end_year
    latest_year(con)                -> the newest release year in the database

Acting is movie_cast, directing and writing the crew jobs in repo/people.ROLES. A film is rated with
min_votes+ votes (callers pass ml.data.clean.MIN_VOTES) and a score; a lead is an acting credit with ord <= 2.
Films without a year are left out; a film with a year but no date sorts as 1 July of that year, ties by id.
"""

from __future__ import annotations

import sqlite3
import statistics
from typing import Any, Literal, TypedDict

from backend.app.repo.people import ROLES

Role = Literal["acting", "directing", "writing"]
CAREER_ROLES: tuple[Role, ...] = ("acting", "directing", "writing")
JOBS = {role: jobs for role, _, jobs in ROLES if role in CAREER_ROLES[1:]}
LEAD_MAX_ORD = 2
ORDER = "COALESCE(m.release_date, m.year || '-07-01'), m.id"


class CareerFilm(TypedDict):
    movie_id: int
    title: str
    year: int
    release_date: str | None
    score: float | None
    vote_count: int
    rated: bool
    lead: bool | None  # None for crew roles
    character: str | None
    poster_path: str | None


def _credited(role: Role) -> tuple[str, tuple[str, ...]]:
    """A subquery for the ids of films with a credit in that role, and its parameters (the crew jobs)."""
    if role == "acting":
        return "SELECT movie_id FROM movie_cast", ()
    jobs = JOBS[role]
    return f"SELECT movie_id FROM movie_crew WHERE job IN ({','.join('?' * len(jobs))})", jobs


def career_films(con: sqlite3.Connection, person_id: int, role: Role, min_votes: int) -> list[CareerFilm]:
    if role == "acting":
        rows = con.execute(f"""SELECT m.id, m.title, m.year, m.release_date, m.vote_average, m.vote_count,
                                      m.poster_path, c.ord, c.character
                               FROM movie_cast c JOIN movies m ON m.id = c.movie_id
                               WHERE c.person_id = ? AND m.year IS NOT NULL ORDER BY {ORDER}""",
                           (person_id,)).fetchall()
    else:
        sql, jobs = _credited(role)
        rows = con.execute(f"""SELECT m.id, m.title, m.year, m.release_date, m.vote_average, m.vote_count,
                                      m.poster_path, NULL AS ord, NULL AS character
                               FROM movies m WHERE m.id IN ({sql} AND person_id = ?) AND m.year IS NOT NULL
                               ORDER BY {ORDER}""", (*jobs, person_id)).fetchall()
    return [_film(r, role, min_votes) for r in rows]


def _film(r: sqlite3.Row, role: Role, min_votes: int) -> CareerFilm:
    votes = r["vote_count"] or 0
    return {
        "movie_id": r["id"], "title": r["title"], "year": r["year"], "release_date": r["release_date"],
        "score": r["vote_average"], "vote_count": votes,
        "rated": votes >= min_votes and r["vote_average"] is not None,
        "lead": (r["ord"] is not None and r["ord"] <= LEAD_MAX_ORD) if role == "acting" else None,
        "character": r["character"] if role == "acting" else None, "poster_path": r["poster_path"],
    }


def roles_available(con: sqlite3.Connection, person_id: int, min_votes: int) -> list[dict[str, Any]]:
    out = []
    for role in CAREER_ROLES:
        films = career_films(con, person_id, role, min_votes)
        if films:
            out.append({"role": role, "film_count": len(films), "rated_count": sum(f["rated"] for f in films)})
    return out


RATED = "m.year IS NOT NULL AND m.vote_count >= ? AND m.vote_average IS NOT NULL"


def year_averages(con: sqlite3.Connection, min_votes: int) -> dict[int, float]:
    return {y: avg for y, avg in con.execute(
        f"SELECT m.year, AVG(m.vote_average) FROM movies m WHERE {RATED} GROUP BY m.year", (min_votes,))}


def population_stats(con: sqlite3.Connection, role: Role, min_votes: int, end_year: int) -> tuple[float, float]:
    sql, jobs = _credited(role)
    scores = [s for (s,) in con.execute(
        f"""SELECT m.vote_average FROM movies m
            WHERE {RATED} AND m.year BETWEEN ? AND ? AND m.id IN ({sql})""",
        (min_votes, end_year - 9, end_year, *jobs))]
    if not scores:
        raise ValueError(f"no rated {role} films in {end_year - 9}-{end_year}")
    return statistics.fmean(scores), statistics.pstdev(scores)


def latest_year(con: sqlite3.Connection) -> int:
    return con.execute("SELECT MAX(year) FROM movies").fetchone()[0]
