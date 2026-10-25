"""Read-only queries for the person pages (Day 14.6) and the extras on autocomplete hits.

    person(con, person_id)          -> the name plus TMDB details (None where TMDB had none), or None
    credits(con, person_id)         -> (cast: film summaries with character, {job: film summaries}), newest first
    stats(con, person_id, cast)     -> film count, years, top genres, average score, box office, top co-star and director
    extras(con, ids, role)          -> {id: {profile_path, known_for}} for autocomplete hits (known_for: their
                                       most-voted film in that role)

Films are the /movies card rows (repo/movies.SUMMARY). The average score uses films with a usable score
(score_ok: 50+ votes), the box office trusted revenue in 2025 dollars only; the top co-star and director need
2+ shared films (ties: TMDB popularity, then name). A stat with nothing to go on is None.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Any

from backend.app.repo.movies import SUMMARY, _summary

NEWEST = "m.release_date IS NULL, m.release_date DESC, m.id"
MIN_SHARED = 2


def person(con: sqlite3.Connection, person_id: int) -> dict[str, Any] | None:
    row = con.execute("""SELECT p.id, p.name, d.profile_path, d.biography, d.birthday, d.deathday, d.place_of_birth,
                                d.known_for_department, d.imdb_id, d.homepage
                         FROM people p LEFT JOIN person_details d ON d.person_id = p.id WHERE p.id = ?""",
                      (person_id,)).fetchone()
    return dict(row) if row else None


def credits(con: sqlite3.Connection, person_id: int) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    cast = [{**_summary(r), "character": r["character"]} for r in con.execute(
        f"""SELECT {SUMMARY}, c.character FROM movie_cast c JOIN movies m ON m.id = c.movie_id
            WHERE c.person_id = ? ORDER BY {NEWEST}""", (person_id,))]
    crew: dict[str, list[dict[str, Any]]] = {}
    for r in con.execute(f"""SELECT {SUMMARY}, c.job FROM movie_crew c JOIN movies m ON m.id = c.movie_id
                             WHERE c.person_id = ? ORDER BY c.job, {NEWEST}""", (person_id,)):
        crew.setdefault(r["job"], []).append(_summary(r))
    return cast, crew


def _top(con: sqlite3.Connection, sql: str, person_id: int) -> dict[str, Any] | None:
    row = con.execute(f"""SELECT p.id, p.name, COUNT(DISTINCT x.movie_id) AS shared_films
                          FROM movie_cast me JOIN {sql} JOIN people p ON p.id = x.person_id
                          LEFT JOIN person_details d ON d.person_id = p.id
                          WHERE me.person_id = ? AND x.person_id != me.person_id
                          GROUP BY p.id HAVING shared_films >= ?
                          ORDER BY shared_films DESC, d.tmdb_popularity IS NULL, d.tmdb_popularity DESC, p.name
                          LIMIT 1""", (person_id, MIN_SHARED)).fetchone()
    return dict(row) if row else None


def stats(con: sqlite3.Connection, person_id: int, cast: list[dict[str, Any]]) -> dict[str, Any]:
    """`cast` is credits()[0]: the counts come from the films already read."""
    years = [f["year"] for f in cast if f["year"] is not None]
    scored = [f["vote_average"] for f in cast if f["score_ok"]]
    money = [f["revenue_2025"] for f in cast if f["revenue_2025"] is not None]  # SUMMARY blanks doubted figures
    genres = Counter(g for f in cast for g in f["genres"])
    return {
        "film_count": len(cast),
        "first_year": min(years) if years else None,
        "last_year": max(years) if years else None,
        "top_genres": [{"name": g, "films": n} for g, n in sorted(genres.items(), key=lambda t: (-t[1], t[0]))[:3]],
        "avg_score": {"value": round(sum(scored) / len(scored), 1), "films": len(scored)} if scored else None,
        "box_office_2025": {"total": sum(money), "films": len(money), "of": len(cast)} if money else None,
        "top_costar": _top(con, "movie_cast x ON x.movie_id = me.movie_id", person_id),
        "top_director": _top(con, "movie_crew x ON x.movie_id = me.movie_id AND x.job = 'Director'", person_id),
    }


ROLE = {"actor": "movie_cast", "director": "movie_crew"}


def extras(con: sqlite3.Connection, ids: list[int], role: str) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    job = "AND c.job = 'Director'" if role == "director" else ""
    rows = con.execute(f"""SELECT p.id, d.profile_path, (
                               SELECT m.title FROM {ROLE[role]} c JOIN movies m ON m.id = c.movie_id
                               WHERE c.person_id = p.id {job}
                               ORDER BY m.vote_count IS NULL, m.vote_count DESC, m.id LIMIT 1) AS known_for
                           FROM people p LEFT JOIN person_details d ON d.person_id = p.id
                           WHERE p.id IN ({marks})""", ids)
    return {r["id"]: {"profile_path": r["profile_path"], "known_for": r["known_for"]} for r in rows}
