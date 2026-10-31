"""Read-only queries for the person pages (Day 14.6) and the extras on autocomplete hits.

    person(con, person_id)          -> the name plus TMDB details (None where TMDB had none), or None
    credits(con, person_id)         -> {role: film summaries}, newest first: acting (with character), directing,
                                       writing, production, music, camera, editing (with their jobs) - Day 14.7
    main_role(department, roles)    -> the role the page opens on: TMDB's department if they have it, else the most films
    stats(con, person_id, role, films)
                                    -> one role's film count, years, top genres, average score, box office, and the actor
                                       and director (not for directing) they shared the most of those films with
    extras(con, ids, role)          -> {id: {profile_path, known_for}} for autocomplete hits (known_for: their
                                       most-voted film in that role)

Films are the /movies card rows (repo/movies.SUMMARY). The average score uses films with a usable score
(score_ok: 50+ votes), the box office trusted revenue in 2025 dollars only; the top actor and director need
2+ shared films (ties: TMDB popularity, then name), and are never the person themself. A stat with nothing to go
on is None.
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
                         FROM people p LEFT JOIN person_details d ON d.person_id = p.id
                         WHERE p.id = ? AND p.id NOT IN (SELECT id FROM fresh_people)""",  # a face the refresher
                      (person_id,)).fetchone()  # added (only in new films) has no page (V1.2)
    return dict(row) if row else None


ROLES = [  # (role, label, crew jobs); acting is movie_cast. The order is the page's role switch.
    ("acting", "Acting", ()), ("directing", "Directing", ("Director",)), ("writing", "Writing", ("Screenplay", "Writer")),
    ("production", "Production", ("Producer",)), ("music", "Music", ("Original Music Composer",)),
    ("camera", "Camera", ("Director of Photography",)), ("editing", "Editing", ("Editor",)),
]
DEPARTMENTS = {"Acting": "acting", "Directing": "directing", "Writing": "writing", "Production": "production",
               "Sound": "music", "Camera": "camera", "Editing": "editing"}  # TMDB's known_for_department -> role


def credits(con: sqlite3.Connection, person_id: int) -> dict[str, list[dict[str, Any]]]:
    """{role: films}, newest first, only roles with films. Acting films carry `character`, crew films their `jobs`
    in that role (a film written as Screenplay and Writer appears once, with both)."""
    out: dict[str, list[dict[str, Any]]] = {}
    cast = [{**_summary(r), "character": r["character"], "jobs": []} for r in con.execute(
        f"""SELECT {SUMMARY}, c.character FROM movie_cast c JOIN movies m ON m.id = c.movie_id
            WHERE c.person_id = ? ORDER BY {NEWEST}""", (person_id,))]
    if cast:
        out["acting"] = cast
    rows = con.execute(f"""SELECT {SUMMARY}, c.job FROM movie_crew c JOIN movies m ON m.id = c.movie_id
                           WHERE c.person_id = ? ORDER BY {NEWEST}, c.job""", (person_id,)).fetchall()
    for role, _, jobs in ROLES[1:]:
        films: dict[int, dict[str, Any]] = {}
        for r in rows:
            if r["job"] in jobs:
                films.setdefault(r["id"], {**_summary(r), "character": None, "jobs": []})["jobs"].append(r["job"])
        if films:
            out[role] = list(films.values())  # dicts keep the newest-first order of the rows
    return out


def main_role(department: str | None, roles: dict[str, list[dict[str, Any]]]) -> str | None:
    """TMDB's department when they have credits in it, else the role with the most films (ties: ROLES order)."""
    if DEPARTMENTS.get(department or "") in roles:
        return DEPARTMENTS[department]
    return max(roles, key=lambda r: (len(roles[r]), -[x[0] for x in ROLES].index(r)), default=None)


def _top(con: sqlite3.Connection, table: str, ids: list[int], person_id: int) -> dict[str, Any] | None:
    """The person in `table` (cast, or directors) of the most of these films, not the person themself."""
    row = con.execute(f"""SELECT p.id, p.name, COUNT(DISTINCT x.movie_id) AS shared_films
                          FROM {table} x JOIN people p ON p.id = x.person_id
                          LEFT JOIN person_details d ON d.person_id = p.id
                          WHERE x.movie_id IN ({','.join('?' * len(ids))}) AND x.person_id != ?
                          GROUP BY p.id HAVING shared_films >= ?
                          ORDER BY shared_films DESC, d.tmdb_popularity IS NULL, d.tmdb_popularity DESC, p.name
                          LIMIT 1""", (*ids, person_id, MIN_SHARED)).fetchone()
    return dict(row) if row else None


DIRECTORS = "(SELECT movie_id, person_id FROM movie_crew WHERE job = 'Director')"


def stats(con: sqlite3.Connection, person_id: int, role: str, films: list[dict[str, Any]]) -> dict[str, Any]:
    """One role's stats from its films (credits()[role]): the counts come from the films already read."""
    years = [f["year"] for f in films if f["year"] is not None]
    scored = [f["vote_average"] for f in films if f["score_ok"]]
    money = [f["revenue_2025"] for f in films if f["revenue_2025"] is not None]  # SUMMARY blanks doubted figures
    genres = Counter(g for f in films for g in f["genres"])
    ids = [f["id"] for f in films]
    return {
        "film_count": len(films),
        "first_year": min(years) if years else None,
        "last_year": max(years) if years else None,
        "top_genres": [{"name": g, "films": n} for g, n in sorted(genres.items(), key=lambda t: (-t[1], t[0]))[:3]],
        "avg_score": {"value": round(sum(scored) / len(scored), 1), "films": len(scored)} if scored else None,
        "box_office_2025": {"total": sum(money), "films": len(money), "of": len(films)} if money else None,
        "top_actor": _top(con, "movie_cast", ids, person_id) if ids else None,
        "top_director": _top(con, DIRECTORS, ids, person_id) if ids and role != "directing" else None,
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
