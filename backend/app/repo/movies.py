"""Read-only queries for the public movie pages.

    fts_query(text)                     -> a safe FTS5 query: every word as a quoted prefix ("tom"* "han"*), or None
    search(con, q, genre, year_from, year_to, language, score_min, sort, page, page_size)
                                        -> (rows for that page, each with `fresh`, total matching): 4 queries
    movie(con, movie_id)                -> one film's facts, people (the cast with their TMDB photo path), money and
                                           score, or None
    summaries(con, ids)                 -> {id: summary, with runtime and genres} for the films among ids that exist (two queries)
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
WALK_SORTS = ("popularity", "score", "revenue", "title", "newest")  # the sorts with an index in build_db.SORT_INDEXES
WIDE_YEARS = 20  # search(): a year range this wide is not selective
WALK_MIN_MATCHES = 5000  # a text search matching this many films walks the sort's index (search)
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


# ---------------------------------------------------------------- lists


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

    With `today` (V1.2): when="released" / "upcoming" keeps the films of that window (services/fresh/pull.windows); with
    neither `when` nor a text search a film not yet released is left out, so a coming-soon film is found only
    through when="upcoming", a search or its page."""
    # V1.5: a unary "+" on a column keeps the planner off that column's index. A date filter such as
    # "release_date <= today" matches nearly every film, yet the planner would walk idx_movies_release for it and
    # fetch the table row of each (0.27 s for a count, against 8 ms from the year index). So the date terms never
    # use an index here, except in a `when` window, where the range is the point.
    plain = q is None and when is None  # no window and no text: the sorts' own indexes (build_db.SORT_INDEXES) serve
    rel = "+m.release_date" if plain else "m.release_date"
    # on the score sort a wide year range (20+ years, or open ended) is left to the vote_count index, which finds the few
    # films with 500+ votes; a narrow range is better served by the year index
    wide = (year_to if year_to is not None else 2100) - (year_from if year_from is not None else 1800) >= WIDE_YEARS
    year = "+m.year" if plain and sort == "score" and wide else "m.year"
    joins, where, args = "", ["+m.release_date IS NOT NULL"], []
    if q is not None:
        match = fts_query(q)
        if match is None:  # only punctuation: nothing can match
            return [], 0
        joins = "JOIN movies_fts ON movies_fts.rowid = m.id"
        where.append("movies_fts MATCH ?")
        args.append(match)
    if today is not None:
        if when is not None:
            from backend.app.services.fresh.pull import windows

            first, last = windows(today)[when]
            where.append("m.release_date BETWEEN ? AND ?")
            args.extend((first.isoformat(), last.isoformat()))
        elif q is None:
            where.append(f"{rel} <= ?")
            args.append(today.isoformat())
    if genre:
        where.append("EXISTS (SELECT 1 FROM movie_genres mg JOIN genres g ON g.id = mg.genre_id "
                     "WHERE mg.movie_id = m.id AND g.name = ?)")
        args.append(genre)
    if year_from is not None:
        where.append(f"{year} >= ?")
        args.append(year_from)
    if year_to is not None:
        where.append(f"{year} <= ?")
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
    # the revenue count is the one that wants the date range: its partial index (build_db.SORT_INDEXES) is on release_date
    count_clause = clause.replace("+m.release_date", "m.release_date") if plain and sort == "revenue" else clause
    total = con.execute(f"SELECT COUNT(*) {count_clause}", args).fetchone()[0]
    ids_clause = clause
    if q is not None and total >= WALK_MIN_MATCHES and sort in WALK_SORTS:
        # a common word matches most films: walking the sort's index and asking the match set whether each film is in
        # it beats sorting every match (18 ms against 54 for "the"); a rare word keeps the match-driven plan
        ids_clause = clause.replace(joins, "").replace("movies_fts MATCH ?", "+m.id IN (SELECT rowid FROM movies_fts "
                                                                              "WHERE movies_fts MATCH ?)")
    # two steps: the ids of the page (a sort without per-row subqueries), then the page's summaries
    page_ids = [r[0] for r in con.execute(f"SELECT m.id {ids_clause} ORDER BY {SORTS[sort]} LIMIT ? OFFSET ?",
                                          [*args, page_size, (page - 1) * page_size])]
    found = summaries(con, page_ids, with_fresh=True)
    return [found[i] for i in page_ids if i in found], total


def genres_for(con: sqlite3.Connection, ids: list[int]) -> dict[int, list[str]]:
    """Each film's genre names in TMDB's order, for a page of films: one flat query (the names are joined by id)
    instead of a subquery per film (V1.2: 17x faster for the newest list)."""
    if not ids:
        return {}
    out: dict[int, list[str]] = {i: [] for i in ids}
    for movie_id, name in con.execute(f"SELECT mg.movie_id, g.name FROM movie_genres mg JOIN genres g ON g.id = mg.genre_id "
                                      f"WHERE mg.movie_id IN ({','.join('?' * len(ids))}) ORDER BY mg.movie_id, mg.ord",
                                      list(ids)):
        out[movie_id].append(name)
    return out


def _summary(r: sqlite3.Row) -> dict[str, Any]:
    out = dict(r)
    out["genres"] = (json.loads(out["genres"]) if out["genres"] else []) if "genres" in out else []
    out["score_ok"] = bool(out["score_ok"])
    return out


def summaries(con: sqlite3.Connection, ids: list[int], with_fresh: bool = False) -> dict[int, dict[str, Any]]:
    """The cards of the films among ids, genres included: two queries. with_fresh adds `fresh` (the refresher keeps
    the film up to date, fresh_films) to each, in the same query."""
    if not ids:
        return {}
    fresh = ", m.id IN (SELECT id FROM fresh_films) AS fresh" if with_fresh else ""
    rows = con.execute(f"SELECT {SUMMARY_COLS}, m.runtime{fresh} FROM movies m WHERE m.id IN ({','.join('?' * len(ids))})",
                       list(ids))
    films = {r["id"]: _summary(r) for r in rows}
    if with_fresh:
        for film in films.values():
            film["fresh"] = bool(film["fresh"])
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
    where, args = ["+m.release_date IS NOT NULL"], []  # "+": see search(); a date filter must not walk idx_movies_release
    if today is not None:
        where.append("+m.release_date <= ?")
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


# ---------------------------------------------------------------- ids


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


# ---------------------------------------------------------------- one film


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
