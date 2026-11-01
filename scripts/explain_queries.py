"""EXPLAIN QUERY PLAN for the app's hot read queries, and a list of full scans of big tables (V1.5, Task 7).

    uv run python scripts/explain_queries.py [--db build/movies.db] [--min-rows 10000] [--plans]

Runs each hot repo function with typical parameters on a read-only connection, records every SELECT it issues (the
connection's trace callback gives the statement with its parameters filled in), then asks SQLite for each one's plan.
Prints the scans of tables with more than --min-rows rows (a SCAN of a big table is the thing to fix; "SCAN ... USING
COVERING INDEX" walks an index, not the table, and is listed apart) and exits 1 if a table scan is left in a query
that is not on the allowed list (ALLOWED: counts and aggregates whose job is to read the whole table, startup-only).
--plans prints every plan. The database must have the sort indexes (build/movies.db, from scripts/slim_db.py).
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.deps import connect_read_only  # noqa: E402
from backend.app.repo import career, meta, people  # noqa: E402
from backend.app.repo import movies as repo  # noqa: E402
from backend.app.services.search import people_search  # noqa: E402

TODAY = date(2026, 11, 1)
TOM_HANKS, NOLAN, FIGHT_CLUB = 31, 525, 550

# name -> a reason, for scans that read the whole table because the question is about all of it
ALLOWED = {
    "random_candidates (no filter)": "returns every film with a poster (about 70,000 ids), picked from in Python",
    "meta.common_codes language": "GROUP BY over every film (once per process, kept on app.state)",
    "meta.common_codes country": "GROUP BY over every film's countries (once per process)",
    "meta.build_info": "COUNT of the films (health)",
    "meta.year_range": "MIN/MAX of the year (index scan)",
    "career.latest_year": "MAX(year) (index scan)",
    "career.population_stats": "a 10-year population of rated films (once per role, then cached by the forecast)",
    "career.recent_genre_lists": "the recent rated films' genres (once per process)",
    "career.recent_films": "the recent rated films (cached by CareerModelCache)",
}


def scenarios(con: sqlite3.Connection) -> dict[str, Callable[[], Any]]:
    def search(**kw: Any) -> Callable[[], Any]:
        return lambda: repo.search(con, today=TODAY, **kw)

    return {
        "browse popularity (home row)": search(sort="popularity", page_size=12),
        "browse score (home row)": search(sort="score", page_size=12),
        "browse revenue (home row)": search(sort="revenue", page_size=12),
        "browse popularity 1990s (home row)": search(sort="popularity", year_from=1990, year_to=1999, page_size=12),
        "browse newest": search(sort="newest"),
        "browse title": search(sort="title"),
        "browse q=the": search(q="the"),
        "browse q=godfather": search(q="godfather"),
        "browse q=the sort=score": search(q="the", sort="score"),
        "browse genre=Drama": search(genre="Drama"),
        "browse genre=Drama year>=2020 score>=7": search(genre="Drama", year_from=2020, score_min=7),
        "browse year_from=2020 score_min=7": search(year_from=2020, score_min=7),
        "browse language=fr": search(language="fr"),
        "browse language=fr sort=score": search(language="fr", sort="score"),
        "browse when=upcoming": search(when="upcoming", sort="soonest"),
        "browse when=released": search(when="released", sort="newest"),
        "movie detail": lambda: repo.movie(con, FIGHT_CLUB),
        "film keywords": lambda: repo.film_keywords(con, FIGHT_CLUB),
        "fresh_ids": lambda: repo.fresh_ids(con, [FIGHT_CLUB, 1, 2]),
        "random_candidates (no filter)": lambda: repo.random_candidates(con, today=TODAY),
        "random_candidates floor + genre + decade": lambda: repo.random_candidates(
            con, genre="Drama", decade=1990, floor=(200, 6.0), today=TODAY),
        "random_candidates language + runtime": lambda: repo.random_candidates(
            con, language="fr", max_runtime=100, today=TODAY),
        "person page (Hanks)": lambda: _person(con, TOM_HANKS),
        "person page (Nolan)": lambda: _person(con, NOLAN),
        "autocomplete extras (actor)": lambda: people.extras(con, [TOM_HANKS, 287, 1245], "actor"),
        "autocomplete extras (director)": lambda: people.extras(con, [NOLAN, 1, 2], "director"),
        "career films (acting)": lambda: career.career_films(con, TOM_HANKS, "acting", 50),
        "career films (directing)": lambda: career.career_films(con, NOLAN, "directing", 50),
        "career roles": lambda: career.roles_available(con, NOLAN, 50),
        "career.population_stats": lambda: career.population_stats(con, "acting", 50, 2025),
        "career.latest_year": lambda: career.latest_year(con),
        "career credited_genres": lambda: career.credited_genres(con, NOLAN, "directing"),
        "career repeat_collaborators": lambda: career.repeat_collaborators(con, NOLAN, "directing", "actor", 3),
        "career film_details": lambda: career.film_details(con, [FIGHT_CLUB, 13, 680]),
        "career.recent_genre_lists": lambda: career.recent_genre_lists(con, 50),
        "career.recent_films": lambda: career.recent_films(con, 50, [18]),
        "meta.common_codes language": lambda: meta.common_codes(con, "language", 40),
        "meta.common_codes country": lambda: meta.common_codes(con, "country", 40),
        "meta.build_info": lambda: meta.build_info(con),
        "meta.year_range": lambda: meta.year_range(con),
        "people search 'tom'": lambda: _people_search(con, "tom"),
        "people search 'ma' (director)": lambda: _people_search(con, "ma", "director"),
    }


def _person(con: sqlite3.Connection, person_id: int) -> None:
    people.person(con, person_id)
    credits = people.credits(con, person_id)
    for role, films in credits.items():
        people.stats(con, person_id, role, films)


_LOOKUPS: list[Any] = []


def _people_search(con: sqlite3.Connection, q: str, role: str = "all") -> Any:
    if not _LOOKUPS:
        from backend.app.services.search.lookups import Lookups

        _LOOKUPS.append(Lookups.from_db(con))
    return people_search.search_people(_LOOKUPS[0], con, q, role)


def table_sizes(con: sqlite3.Connection) -> dict[str, int]:
    names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE '%\\_%\\_%' ESCAPE '\\'")]
    sizes = {}
    for name in names:
        try:
            sizes[name] = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        except sqlite3.Error:
            pass
    return sizes


def aliases(sql: str, tables: set[str]) -> dict[str, str]:
    """alias (or the table's own name) -> table, from the FROM / JOIN clauses of a statement."""
    found: dict[str, str] = {}
    for table, alias in re.findall(r"(?:FROM|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(?!JOIN|WHERE|ON|LEFT|INNER|GROUP|ORDER|LIMIT|WINDOW|USING)(\w+))?", sql, re.I):
        if table in tables:
            found[table] = table
            if alias:
                found[alias] = table
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=Path("build/movies.db"))
    parser.add_argument("--min-rows", type=int, default=10_000)
    parser.add_argument("--plans", action="store_true", help="print every plan")
    args = parser.parse_args()
    con = connect_read_only(args.db)
    sizes = table_sizes(con)
    _people_search(con, "zz")  # builds the in-memory name indexes now, so they are not counted in a scenario
    big = {t for t, n in sizes.items() if n > args.min_rows}
    bad = 0
    for name, run in scenarios(con).items():
        statements: list[str] = []
        con.set_trace_callback(statements.append)
        start = time.perf_counter()
        run()
        elapsed = (time.perf_counter() - start) * 1000
        con.set_trace_callback(None)
        selects = [s for s in dict.fromkeys(statements) if s.lstrip().upper().startswith(("SELECT", "WITH"))]
        report = []
        for sql in selects:
            tables = aliases(sql, set(sizes))
            for _, _, _, detail in con.execute("EXPLAIN QUERY PLAN " + sql):
                m = re.match(r"SCAN (?:TABLE )?(\w+)(?: AS (\w+))?(.*)", detail)
                if args.plans:
                    report.append(f"      {detail}")
                if not m:
                    continue
                table = tables.get(m.group(2) or m.group(1), m.group(1))
                if table in big:
                    kind = "index walk" if "INDEX" in m.group(3) else "TABLE SCAN"
                    report.append(f"    {kind}: {detail}  [{table}: {sizes[table]:,} rows]")
                    if kind == "TABLE SCAN" and name not in ALLOWED:
                        bad += 1
        print(f"{name}: {len(selects)} queries, {elapsed:.1f} ms" + ("" if name not in ALLOWED or not report else f"  (allowed: {ALLOWED[name]})"))
        print("\n".join(report))
    print(f"\n{bad} table scan(s) of tables over {args.min_rows:,} rows outside the allowed list")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
