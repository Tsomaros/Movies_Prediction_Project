"""Read-only queries for the public movie pages.

    fts_query(text)                     -> a safe FTS5 query: every word as a quoted prefix ("tom"* "han"*), or None
    search(con, q, genre, year_from, year_to, language, has_money, sort, page, page_size)
                                        -> (rows for that page, total matching)
    movie(con, movie_id)                -> one film's facts, people, money and score, or None
    film_keywords(con, movie_id)        -> the film's TMDB keyword ids (for its themes)

User text never reaches FTS5 as syntax: words are pulled out with a Unicode regex and quoted, so input like
`"`, `AND`, `*`, `-` or `NEAR(` can't break or change the query. Every function takes a connection
opened read-only (backend/app/deps.py) and only runs SELECTs.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

SORTS = {  # name -> ORDER BY; ties broken by id so pages never overlap
    "popularity": "m.popularity IS NULL, m.popularity DESC, m.id",
    "newest": "m.release_date IS NULL, m.release_date DESC, m.id",
    "title": "m.title COLLATE NOCASE, m.year, m.id",
    "score": "m.vote_average DESC, m.vote_count DESC, m.id",  # films with a usable score only
}
CREW_JOBS = ("Director", "Screenplay", "Writer", "Producer", "Original Music Composer", "Director of Photography",
             "Editor")  # the order shown
TOP_CAST = 15
GENRES_SQL = """(SELECT json_group_array(name) FROM (SELECT g.name FROM movie_genres mg JOIN genres g ON g.id = mg.genre_id
                 WHERE mg.movie_id = m.id ORDER BY mg.ord))"""
SUMMARY = f"""m.id, m.title, m.year, m.release_date, m.poster_path, m.original_language, m.vote_average, m.vote_count,
              m.score_ok, m.popularity, {GENRES_SQL} AS genres"""


def fts_query(text: str | None) -> str | None:
    words = re.findall(r"\w+", text or "")
    return " ".join(f'"{w}"*' for w in words) or None


def search(con: sqlite3.Connection, q: str | None = None, genre: str | None = None, year_from: int | None = None,
           year_to: int | None = None, language: str | None = None, has_money: bool = False,
           sort: str = "popularity", page: int = 1, page_size: int = 24) -> tuple[list[dict[str, Any]], int]:
    joins, where, args = "", ["m.release_date IS NOT NULL"], []
    if q is not None:
        match = fts_query(q)
        if match is None:  # only punctuation: nothing can match
            return [], 0
        joins = "JOIN movies_fts ON movies_fts.rowid = m.id"
        where.append("movies_fts MATCH ?")
        args.append(match)
    if genre:
        where.append("EXISTS (SELECT 1 FROM movie_genres mg JOIN genres g ON g.id = mg.genre_id "
                     "WHERE mg.movie_id = m.id AND g.name = ?)")
        args.append(genre)
    if year_from is not None:
        where.append("m.year >= ?")
        args.append(year_from)
    if year_to is not None:
        where.append("m.year <= ?")
        args.append(year_to)
    if language:
        where.append("m.original_language = ?")
        args.append(language)
    if has_money:
        where.append("m.budget IS NOT NULL AND m.revenue IS NOT NULL AND NOT m.money_suspect")
    if sort == "score":
        where.append("m.score_ok")
    clause = f"FROM movies m {joins} WHERE {' AND '.join(where)}"
    total = con.execute(f"SELECT COUNT(*) {clause}", args).fetchone()[0]
    rows = con.execute(f"SELECT {SUMMARY} {clause} ORDER BY {SORTS[sort]} LIMIT ? OFFSET ?",
                       [*args, page_size, (page - 1) * page_size]).fetchall()
    return [_summary(r) for r in rows], total


def _summary(r: sqlite3.Row) -> dict[str, Any]:
    out = dict(r)
    out["genres"] = json.loads(out["genres"]) if out["genres"] else []
    out["score_ok"] = bool(out["score_ok"])
    return out


def movie(con: sqlite3.Connection, movie_id: int) -> dict[str, Any] | None:
    r = con.execute(f"""SELECT {SUMMARY}, m.original_title, m.tagline, m.overview, m.month, m.runtime, m.status,
                               m.us_certification, m.budget, m.revenue, m.budget_2025, m.revenue_2025, m.money_suspect,
                               m.money_suspect_reason, m.revenue_incomplete, c.id AS collection_id,
                               c.name AS collection_name
                        FROM movies m LEFT JOIN collections c ON c.id = m.collection_id WHERE m.id = ?""",
                    (movie_id,)).fetchone()
    if r is None:
        return None
    out = _summary(r)
    out["companies"] = [dict(x) for x in con.execute(
        """SELECT co.id, co.name, co.origin_country FROM movie_companies mc JOIN companies co ON co.id = mc.company_id
           WHERE mc.movie_id = ? ORDER BY co.name COLLATE NOCASE""", (movie_id,))]
    out["countries"] = [x[0] for x in con.execute(
        "SELECT country FROM movie_countries WHERE movie_id = ? ORDER BY country", (movie_id,))]
    out["spoken_languages"] = [x[0] for x in con.execute(
        "SELECT language FROM movie_languages WHERE movie_id = ? ORDER BY language", (movie_id,))]
    out["cast"] = [dict(x) for x in con.execute(
        """SELECT p.id, p.name, c.character, c.ord AS "order" FROM movie_cast c JOIN people p ON p.id = c.person_id
           WHERE c.movie_id = ? ORDER BY c.ord LIMIT ?""", (movie_id, TOP_CAST))]
    order = " ".join(f"WHEN '{job}' THEN {i}" for i, job in enumerate(CREW_JOBS))
    out["crew"] = [dict(x) for x in con.execute(
        f"""SELECT p.id, p.name, c.job FROM movie_crew c JOIN people p ON p.id = c.person_id
            WHERE c.movie_id = ? ORDER BY CASE c.job {order} ELSE 99 END, p.name""", (movie_id,))]
    return out


def film_keywords(con: sqlite3.Connection, movie_id: int) -> set[int]:
    return {x[0] for x in con.execute("SELECT keyword_id FROM movie_keywords WHERE movie_id = ?", (movie_id,))}
