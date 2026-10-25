"""Read-only queries for the person pages' Career section (Day 14.8).

    career_films(con, person_id, role, min_votes)
                                    -> the person's dated films in that role, oldest first (one per film)
    roles_available(con, person_id, min_votes)
                                    -> [{role, film_count, rated_count}] for acting, directing, writing with films
    year_averages(con, min_votes)   -> {year: mean score of the rated films released that year}
    population_stats(con, role, min_votes, end_year)
                                    -> (mean, population sd) of rated films in that role from the 10 years to end_year
    latest_year(con)                -> the newest release year in the database

Recipe sources for the model card (services/career_model):
    person_name(con, person_id)     -> the person's name, or None
    genre_names(con)                -> {genre id: name}
    credited_genres(con, person_id, role)
                                    -> genre ids of every film they have a credit on in that role (undated too)
    repeat_collaborators(con, person_id, role, kind, limit)
                                    -> [{id, name}] actors or directors on 2+ of their films in that role
    film_details(con, ids)          -> {id: language, month, runtime, certification, trusted budget_2025,
                                       genres, keywords, countries}
    recent_genre_lists(con, min_votes)
                                    -> each recent rated film's genre ids
    recent_films(con, min_votes, genre_ids)
                                    -> month, certification and keywords of recent rated films with all those genres

Acting is movie_cast, directing and writing the crew jobs in repo/people.ROLES. A film is rated with
min_votes+ votes (callers pass ml.data.clean.MIN_VOTES) and a score; a lead is an acting credit with ord <= 2.
Films without a year are left out; a film with a year but no date sorts as 1 July of that year, ties by id.
Recent = rated films from the 5 latest release years in the database.
"""

from __future__ import annotations

import sqlite3
import statistics
from typing import Any, Literal, TypedDict

from backend.app.repo.people import MIN_SHARED, ROLES

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


# ---------------------------------------------------------------- recipe sources (Task 4)

RECENT_YEARS = 5
SLOT_TABLES = {"actor": "movie_cast", "director": "(SELECT movie_id, person_id FROM movie_crew WHERE job = 'Director')"}


def _films_of(role: Role) -> tuple[str, tuple[str, ...]]:
    """A subquery for the ids of every film the person (the last parameter) has a credit on in that role, dated or
    not, and its parameters before the person id."""
    if role == "acting":
        return "SELECT movie_id FROM movie_cast WHERE person_id = ?", ()
    jobs = JOBS[role]
    return f"SELECT DISTINCT movie_id FROM movie_crew WHERE job IN ({','.join('?' * len(jobs))}) AND person_id = ?", jobs


def person_name(con: sqlite3.Connection, person_id: int) -> str | None:
    row = con.execute("SELECT name FROM people WHERE id = ?", (person_id,)).fetchone()
    return row[0] if row else None


def genre_names(con: sqlite3.Connection) -> dict[int, str]:
    return {i: name for i, name in con.execute("SELECT id, name FROM genres ORDER BY id")}


def credited_genres(con: sqlite3.Connection, person_id: int, role: Role) -> set[int]:
    sql, jobs = _films_of(role)
    return {g for (g,) in con.execute(f"SELECT DISTINCT genre_id FROM movie_genres WHERE movie_id IN ({sql})",
                                      (*jobs, person_id))}


def repeat_collaborators(con: sqlite3.Connection, person_id: int, role: Role, kind: Literal["actor", "director"],
                         limit: int) -> list[dict[str, Any]]:
    """[{id, name}] of the actors or directors on 2+ (MIN_SHARED) of the person's films in that role, whole career
    (low-vote and undated films too), never the person: most shared films, then most recent shared film, then name."""
    sql, jobs = _films_of(role)
    rows = con.execute(f"""SELECT p.id, p.name, COUNT(DISTINCT x.movie_id) AS shared,
                                  MAX(COALESCE(m.release_date, m.year || '-07-01')) AS last
                           FROM {SLOT_TABLES[kind]} x JOIN people p ON p.id = x.person_id
                           JOIN movies m ON m.id = x.movie_id
                           WHERE x.movie_id IN ({sql}) AND x.person_id != ?
                           GROUP BY p.id HAVING shared >= ?
                           ORDER BY shared DESC, last IS NULL, last DESC, p.name, p.id LIMIT ?""",
                       (*jobs, person_id, person_id, MIN_SHARED, limit)).fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]


def film_details(con: sqlite3.Connection, ids: list[int]) -> dict[int, dict[str, Any]]:
    """{id: {language, month, runtime, certification (raw), budget_2025 (None if suspect), genres (TMDB order),
    keywords, countries}} for these films."""
    marks = ",".join("?" * len(ids))
    out = {r["id"]: {"language": r["original_language"], "month": r["month"], "runtime": r["runtime"],
                     "certification": r["us_certification"],
                     "budget_2025": None if r["money_suspect"] else r["budget_2025"],
                     "genres": [], "keywords": set(), "countries": []}
           for r in con.execute(f"""SELECT id, original_language, month, runtime, us_certification, budget_2025,
                                           money_suspect FROM movies WHERE id IN ({marks})""", ids)}
    for movie_id, g in con.execute(f"SELECT movie_id, genre_id FROM movie_genres WHERE movie_id IN ({marks}) "
                                   "ORDER BY movie_id, ord, genre_id", ids):
        out[movie_id]["genres"].append(g)
    for movie_id, k in con.execute(f"SELECT movie_id, keyword_id FROM movie_keywords WHERE movie_id IN ({marks})", ids):
        out[movie_id]["keywords"].add(k)
    for movie_id, c in con.execute(f"SELECT movie_id, country FROM movie_countries WHERE movie_id IN ({marks}) "
                                   "ORDER BY movie_id, country", ids):
        out[movie_id]["countries"].append(c)
    return out


def _recent(con: sqlite3.Connection, min_votes: int) -> tuple[str, tuple[Any, ...]]:
    """WHERE text and parameters for rated films from the RECENT_YEARS latest years in the database."""
    end = latest_year(con)
    return f"{RATED} AND m.year BETWEEN ? AND ?", (min_votes, end - RECENT_YEARS + 1, end)


def recent_genre_lists(con: sqlite3.Connection, min_votes: int) -> list[list[int]]:
    """Each recent rated film's genre ids (ascending)."""
    where, params = _recent(con, min_votes)
    films: dict[int, list[int]] = {}
    for movie_id, g in con.execute(f"""SELECT g.movie_id, g.genre_id FROM movie_genres g JOIN movies m ON m.id = g.movie_id
                                       WHERE {where} ORDER BY g.movie_id, g.genre_id""", params):
        films.setdefault(movie_id, []).append(g)
    return list(films.values())


def recent_films(con: sqlite3.Connection, min_votes: int, genre_ids: list[int]) -> list[dict[str, Any]]:
    """[{month, certification (raw), keywords}] of the recent rated films that have all of these genres."""
    where, params = _recent(con, min_votes)
    where += (f" AND (SELECT COUNT(*) FROM movie_genres g WHERE g.movie_id = m.id"
              f" AND g.genre_id IN ({','.join('?' * len(genre_ids))})) = ?")
    params = (*params, *genre_ids, len(genre_ids))
    films = {r["id"]: {"month": r["month"], "certification": r["us_certification"], "keywords": set()}
             for r in con.execute(f"SELECT m.id, m.month, m.us_certification FROM movies m WHERE {where}", params)}
    for movie_id, k in con.execute(f"""SELECT k.movie_id, k.keyword_id FROM movie_keywords k
                                       JOIN movies m ON m.id = k.movie_id WHERE {where}""", params):
        films[movie_id]["keywords"].add(k)
    return list(films.values())
