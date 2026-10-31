"""Read-only queries for the public movie pages.

    fts_query(text)                     -> a safe FTS5 query: every word as a quoted prefix ("tom"* "han"*), or None
    search(con, q, genre, year_from, year_to, language, score_min, sort, page, page_size)
                                        -> (rows for that page, total matching)
    movie(con, movie_id)                -> one film's facts, people (the cast with their TMDB photo path), money and
                                           score, or None
    summaries(con, ids)                 -> {id: summary, with runtime} for the films among ids that exist (one query)
    random_candidates(con, genre, decade, language, max_runtime, floor, ids)
                                        -> the ids of the films a "Surprise me" spin may pick (Day 14.5)
    posters(con, ids)                   -> {id: poster_path} for the films among ids that have a poster
    ids_present(con, ids)               -> the ids among them that are films in this database (V1.2: the refresher)
    fresh_ids(con, ids)                 -> the ids among them that the refresher keeps up to date (fresh_films, V1.3)
    film_keywords(con, movie_id)        -> the film's TMDB keyword ids (for its themes)

User text never reaches FTS5 as syntax: words are pulled out with a Unicode regex and quoted, so input like
`"`, `AND`, `*`, `-` or `NEAR(` can't break or change the query. Every function takes a connection
opened read-only (backend/app/deps.py) and only runs SELECTs.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from typing import Any

SORTS = {  # name -> ORDER BY; ties broken by id so pages never overlap
    "popularity": "m.popularity IS NULL, m.popularity DESC, m.id",
    "newest": "m.release_date IS NULL, m.release_date DESC, m.id",
    "title": "m.title COLLATE NOCASE, m.year, m.id",
    "score": "m.vote_average DESC, m.vote_count DESC, m.id",  # films with SCORE_SORT_MIN_VOTES (500) votes or more only
    "revenue": "m.revenue_2025 DESC, m.id",  # films with a trusted revenue only, in 2025 dollars
    "soonest": "m.release_date IS NULL, m.release_date ASC, m.id",  # the next release first (the Coming soon list)
}
CREW_JOBS = ("Director", "Screenplay", "Writer", "Producer", "Original Music Composer", "Director of Photography",
             "Editor")  # the order shown
TOP_CAST = 15
SCORE_SORT_MIN_VOTES = 500  # the "Highest score" sort and the Top rated row: a film needs this many votes (our models' own floor, score_ok, stays 50)
GENRES_SQL = """(SELECT json_group_array(n) FROM (
    SELECT (SELECT g.name FROM genres g WHERE g.id = mg.genre_id) AS n
    FROM movie_genres mg WHERE mg.movie_id = m.id ORDER BY mg.ord LIMIT 100))"""
# The LIMIT keeps the inner query apart from the aggregate, and the name is looked up by id instead of joined.
SUMMARY_COLS = """m.id, m.title, m.year, m.release_date, m.poster_path, m.original_language, m.vote_average, m.vote_count,
              m.score_ok, m.popularity, CASE WHEN m.money_suspect THEN NULL ELSE m.revenue_2025 END AS revenue_2025"""
SUMMARY = f"""{SUMMARY_COLS},
              {GENRES_SQL} AS genres"""  # the card row in one query: person pages; the film pages and lists add genres_for()


def fts_query(text: str | None) -> str | None:
    words = re.findall(r"\w+", text or "")
    return " ".join(f'"{w}"*' for w in words) or None


def search(con: sqlite3.Connection, q: str | None = None, genre: str | None = None, year_from: int | None = None,
           year_to: int | None = None, language: str | None = None, score_min: float | None = None,
           sort: str = "popularity", page: int = 1, page_size: int = 24, *, when: str | None = None,
           today: date | None = None) -> tuple[list[dict[str, Any]], int]:
    """score_min keeps films of any vote count (the page shows the votes next to the score); sorting by score
    keeps only films with SCORE_SORT_MIN_VOTES (500) votes or more, so a 10.0 from 2 votes, or a 9.1 from 80, never
    tops the list.

    With `today` (V1.2): when="released" / "upcoming" keeps the films of that window (services.fresh.windows); with
    neither `when` nor a text search a film not yet released is left out, so a coming-soon film is found only
    through when="upcoming", a search or its page."""
    joins, where, args = "", ["m.release_date IS NOT NULL"], []
    if q is not None:
        match = fts_query(q)
        if match is None:  # only punctuation: nothing can match
            return [], 0
        joins = "JOIN movies_fts ON movies_fts.rowid = m.id"
        where.append("movies_fts MATCH ?")
        args.append(match)
    if today is not None:
        if when is not None:
            from backend.app.services.fresh import windows

            first, last = windows(today)[when]
            where.append("m.release_date BETWEEN ? AND ?")
            args.extend((first.isoformat(), last.isoformat()))
        elif q is None:
            where.append("m.release_date <= ?")
            args.append(today.isoformat())
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
    if score_min is not None:
        # "+" keeps SQLite off the vote_count index: nearly every film has votes, and walking it took 0.63 s against
        # 0.11 s for a plain scan of the table
        where.append("+m.vote_count > 0 AND m.vote_average >= ?")
        args.append(score_min)
    if sort == "score":
        where.append("m.vote_count >= ?")
        args.append(SCORE_SORT_MIN_VOTES)
    if sort == "revenue":
        where.append("m.revenue_2025 IS NOT NULL AND NOT m.money_suspect")
    clause = f"FROM movies m {joins} WHERE {' AND '.join(where)}"
    total = con.execute(f"SELECT COUNT(*) {clause}", args).fetchone()[0]
    # two steps: the ids of the page (a sort without per-row subqueries), then the page's summaries
    page_ids = [r[0] for r in con.execute(f"SELECT m.id {clause} ORDER BY {SORTS[sort]} LIMIT ? OFFSET ?",
                                          [*args, page_size, (page - 1) * page_size])]
    found = summaries(con, page_ids)
    return [found[i] for i in page_ids if i in found], total


def genres_for(con: sqlite3.Connection, ids: list[int]) -> dict[int, list[str]]:
    """Each film's genre names in TMDB's order, for a page of films: two flat queries instead of a subquery per
    film (V1.2: 17x faster for the newest list)."""
    if not ids:
        return {}
    names = {r[0]: r[1] for r in con.execute("SELECT id, name FROM genres")}
    out: dict[int, list[str]] = {i: [] for i in ids}
    for movie_id, genre_id in con.execute(f"SELECT movie_id, genre_id FROM movie_genres "
                                           f"WHERE movie_id IN ({','.join('?' * len(ids))}) ORDER BY movie_id, ord", list(ids)):
        if genre_id in names:
            out[movie_id].append(names[genre_id])
    return out


def _summary(r: sqlite3.Row) -> dict[str, Any]:
    out = dict(r)
    out["genres"] = (json.loads(out["genres"]) if out["genres"] else []) if "genres" in out else []
    out["score_ok"] = bool(out["score_ok"])
    return out


def summaries(con: sqlite3.Connection, ids: list[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    rows = con.execute(f"SELECT {SUMMARY_COLS}, m.runtime FROM movies m WHERE m.id IN ({','.join('?' * len(ids))})",
                       list(ids))
    films = {r["id"]: _summary(r) for r in rows}
    for movie_id, names in genres_for(con, list(films)).items():
        films[movie_id]["genres"] = names
    return films


def random_candidates(con: sqlite3.Connection, genre: str | None = None, decade: int | None = None,
                      language: str | None = None, max_runtime: int | None = None,
                      floor: tuple[int, float] | None = None, ids: list[int] | None = None,
                      today: date | None = None) -> list[int]:
    """floor = (fewest votes, lowest score), or None for no floor. ids limits the films to those (a watchlist);
    without ids every film needs a poster, because the reveal is a poster shuffle. A film with no runtime is
    left out under max_runtime. With `today`, a film not yet released is never a candidate (V1.2)."""
    where, args = ["m.release_date IS NOT NULL"], []
    if today is not None:
        where.append("m.release_date <= ?")
        args.append(today.isoformat())
    if ids is not None:
        if not ids:
            return []
        where.append(f"m.id IN ({','.join('?' * len(ids))})")
        args.extend(ids)
    else:
        where.append("m.poster_path IS NOT NULL")
    if floor is not None:
        where.append("m.vote_count >= ? AND m.vote_average >= ?")
        args.extend(floor)
    if genre:
        where.append("EXISTS (SELECT 1 FROM movie_genres mg JOIN genres g ON g.id = mg.genre_id "
                     "WHERE mg.movie_id = m.id AND g.name = ?)")
        args.append(genre)
    if decade is not None:
        where.append("m.year BETWEEN ? AND ?")
        args.extend((decade, decade + 9))
    if language:
        where.append("m.original_language = ?")
        args.append(language)
    if max_runtime is not None:
        where.append("m.runtime <= ?")
        args.append(max_runtime)
    return [r[0] for r in con.execute(f"SELECT m.id FROM movies m WHERE {' AND '.join(where)}", args)]


def posters(con: sqlite3.Connection, ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = con.execute(f"SELECT id, poster_path FROM movies WHERE poster_path IS NOT NULL "
                       f"AND id IN ({','.join('?' * len(ids))})", list(ids))
    return {r[0]: r[1] for r in rows}


def fresh_ids(con: sqlite3.Connection, ids: list[int]) -> set[int]:
    """The ids among them whose film the refresher keeps up to date (their answers are cached for minutes only)."""
    if not ids:
        return set()
    return {r[0] for r in con.execute(f"SELECT id FROM fresh_films WHERE id IN ({','.join('?' * len(ids))})", list(ids))}


def ids_present(con: sqlite3.Connection, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    return {r[0] for r in con.execute(f"SELECT id FROM movies WHERE id IN ({','.join('?' * len(ids))})", list(ids))}


def _rows_by_id(con: sqlite3.Connection, table: str, columns: str, ids: list[int]) -> list[sqlite3.Row]:
    """The rows of a lookup table for a few ids."""
    if not ids:
        return []
    return con.execute(f"SELECT {columns} FROM {table} WHERE id IN ({','.join('?' * len(ids))})", list(ids)).fetchall()


def movie(con: sqlite3.Connection, movie_id: int) -> dict[str, Any] | None:
    r = con.execute(f"""SELECT {SUMMARY_COLS}, m.original_title, m.tagline, m.overview, m.month, m.runtime, m.status,
                               m.us_certification, m.budget, m.revenue, m.budget_2025, m.revenue_2025, m.money_suspect,
                               m.money_suspect_reason, m.revenue_incomplete, m.collection_id
                        FROM movies m WHERE m.id = ?""", (movie_id,)).fetchone()
    if r is None:
        return None
    out = _summary(r)
    out["genres"] = genres_for(con, [movie_id])[movie_id]
    out["collection_name"] = None
    if out["collection_id"] is not None:
        found = _rows_by_id(con, "collections", "id, name", [out["collection_id"]])
        out["collection_name"] = found[0]["name"] if found else None
        if not found:
            out["collection_id"] = None  # the old LEFT JOIN found no collection either
    company_ids = [x[0] for x in con.execute("SELECT company_id FROM movie_companies WHERE movie_id = ?", (movie_id,))]
    out["companies"] = sorted((dict(x) for x in _rows_by_id(con, "companies", "id, name, origin_country", company_ids)),
                              key=lambda c: (c["name"] or "").casefold())
    out["countries"] = [x[0] for x in con.execute(
        "SELECT country FROM movie_countries WHERE movie_id = ? ORDER BY country", (movie_id,))]
    out["spoken_languages"] = [x[0] for x in con.execute(
        "SELECT language FROM movie_languages WHERE movie_id = ? ORDER BY language", (movie_id,))]
    out["cast"] = [dict(x) for x in con.execute(
        """SELECT p.id, p.name, c.character, c.ord AS "order", d.profile_path,
                  p.id NOT IN (SELECT id FROM fresh_people) AS linked
           FROM movie_cast c JOIN people p ON p.id = c.person_id LEFT JOIN person_details d ON d.person_id = p.id
           WHERE c.movie_id = ? ORDER BY c.ord LIMIT ?""", (movie_id, TOP_CAST))]
    jobs = {(x[0], x[1]) for x in con.execute("SELECT person_id, job FROM movie_crew WHERE movie_id = ?", (movie_id,))}
    people = {x["id"]: x["name"] for x in _rows_by_id(con, "people", "id, name", sorted({p for p, _ in jobs}))}
    added = {x[0] for x in con.execute(
        f"SELECT id FROM fresh_people WHERE id IN ({','.join('?' * len(people))})", list(people))} if people else set()
    rank = {job: i for i, job in enumerate(CREW_JOBS)}
    out["crew"] = [{"id": p, "name": people[p], "job": job, "linked": p not in added}
                   for p, job in sorted((j for j in jobs if j[0] in people), key=lambda j: (rank.get(j[1], 99), people[j[0]]))]
    return out


def film_keywords(con: sqlite3.Connection, movie_id: int) -> set[int]:
    return {x[0] for x in con.execute("SELECT keyword_id FROM movie_keywords WHERE movie_id = ?", (movie_id,))}
