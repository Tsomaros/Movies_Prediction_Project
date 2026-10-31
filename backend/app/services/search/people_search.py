"""The header's people search (V1.1): actors, directors and writers by name, one page at a time.

    ROLES                                    -> ("all", "actor", "director", "writer")
    usable(q)                                -> the folded query, or None under 2 letters or digits
    search_people(lookups, con, q, role="all", page=1, page_size=24)
                                             -> {total, role_counts, results: [{id, name, profile_path, roles,
                                                known_for}]}

Matching is the autocomplete's in-memory name indexes (services/search/lookups.py): any word of the name starts with q,
accents folded, so "penelope" and "tom ha" work and no query syntax can fail. The roles are the career chart's:
actor = movie_cast, director = the job Director, writer = Screenplay or Writer; people with other crew jobs only
are not listed. role_counts counts people per role (all: anyone in one of them). Ranking: films in the role
(all: distinct films over the three, so an actor-director in the same film counts it once), then TMDB
popularity (none last), name, id. Each result's roles are the ones with a film, most films first; known_for is
their most-voted film over the three roles.
"""

from __future__ import annotations

import json
import math
import sqlite3
from typing import Any

import numpy as np

from backend.app.services.search.lookups import Lookups, _normalise

ROLES = ("all", "actor", "director", "writer")
PEOPLE_ROLES = ROLES[1:]
CREDITS = """SELECT person_id, movie_id FROM movie_cast WHERE person_id IN (SELECT value FROM json_each(:ids))
             UNION ALL
             SELECT person_id, movie_id FROM movie_crew WHERE person_id IN (SELECT value FROM json_each(:ids))
                    AND job IN ('Director', 'Screenplay', 'Writer')"""


def usable(q: str) -> str | None:
    folded = _normalise(q)
    return folded if sum(c.isalnum() for c in folded) >= 2 else None


def _empty() -> dict[str, Any]:
    return {"total": 0, "role_counts": dict.fromkeys(ROLES, 0), "results": []}


def search_people(lookups: Lookups, con: sqlite3.Connection, q: str, role: str = "all", page: int = 1,
                  page_size: int = 24) -> dict[str, Any]:
    folded = usable(q)
    if folded is None:
        return _empty()
    found = {}  # role -> (person ids, films in that role, index entries), all numpy arrays
    for r in PEOPLE_ROLES:
        index = lookups.indexes[r]
        entries = index.matches(folded)
        found[r] = (index.ids[entries], index.n_films[entries].astype(np.int64), entries)
    everyone = np.unique(np.concatenate([found[r][0] for r in PEOPLE_ROLES]))
    role_counts = {"all": len(everyone), **{r: len(found[r][0]) for r in PEOPLE_ROLES}}
    start, stop = (page - 1) * page_size, page * page_size
    ids, films = _all_films(con, found, stop) if role == "all" else found[role][:2]
    total = len(everyone) if role == "all" else len(ids)
    if start >= len(ids):
        return {"total": total, "role_counts": role_counts, "results": []}
    # Only the tie groups the page touches need popularity and names: everyone above them is counted, not sorted.
    by_films = np.sort(films)[::-1]
    high, low = by_films[start], by_films[min(stop, len(ids)) - 1]
    above = int((films > high).sum())
    group = ids[(films >= low) & (films <= high)]
    group_films = dict(zip(group.tolist(), films[(films >= low) & (films <= high)].tolist()))
    names = _names(lookups, found, group)
    popularity = _popularity(con, group.tolist())
    ranked = sorted(group_films, key=lambda i: (-group_films[i], -popularity.get(i, -math.inf), names[i].casefold(), i))
    page_ids = ranked[start - above:stop - above]
    details = _details(con, page_ids)
    results = [{"id": i, "name": names[i], "profile_path": details.get(i, {}).get("profile_path"),
                "roles": _roles(found, i), "known_for": details.get(i, {}).get("known_for")} for i in page_ids]
    return {"total": total, "role_counts": role_counts, "results": results}


def _all_films(con: sqlite3.Connection, found: dict, stop: int) -> tuple[np.ndarray, np.ndarray]:
    """Distinct films over the three roles, exact for everyone who could rank in the first `stop` places.

    A person's distinct count lies between their largest role count and the sum of them. At least `stop` people
    have at least the stop-th largest lower bound, so anyone whose upper bound is below it can't reach the page:
    they are left out, and only people in several roles with a chance get a SQL count.
    """
    all_ids = np.concatenate([found[r][0] for r in PEOPLE_ROLES])
    all_films = np.concatenate([found[r][1] for r in PEOPLE_ROLES])
    ids, inverse, roles = np.unique(all_ids, return_inverse=True, return_counts=True)
    upper, lower = np.zeros(len(ids), np.int64), np.zeros(len(ids), np.int64)
    np.add.at(upper, inverse, all_films)
    np.maximum.at(lower, inverse, all_films)
    floor = np.partition(lower, len(ids) - stop)[len(ids) - stop] if stop <= len(ids) else 0
    films = lower.copy()
    several = (roles > 1) & (upper >= floor)
    if several.any():
        rows = con.execute(f"SELECT person_id, COUNT(DISTINCT movie_id) FROM ({CREDITS}) GROUP BY person_id",
                           {"ids": json.dumps(ids[several].tolist())})
        exact = dict(rows.fetchall())
        films[several] = [exact.get(i, 0) for i in ids[several].tolist()]
    keep = films >= floor
    return ids[keep], films[keep]


def _names(lookups: Lookups, found: dict, ids: np.ndarray) -> dict[int, str]:
    names: dict[int, str] = {}
    for r in PEOPLE_ROLES:
        role_ids, _, entries = found[r]
        hit = np.isin(role_ids, ids)
        names.update((int(i), lookups.indexes[r].name(int(e))) for i, e in zip(role_ids[hit], entries[hit]))
    return names


def _roles(found: dict, person_id: int) -> list[dict[str, Any]]:
    roles = []
    for r in PEOPLE_ROLES:
        role_ids, films, _ = found[r]
        hit = np.flatnonzero(role_ids == person_id)
        if len(hit):
            roles.append({"role": r, "n_films": int(films[hit[0]])})
    return sorted(roles, key=lambda x: -x["n_films"])


def _popularity(con: sqlite3.Connection, ids: list[int]) -> dict[int, float]:
    rows = con.execute("""SELECT person_id, tmdb_popularity FROM person_details
                          WHERE person_id IN (SELECT value FROM json_each(?)) AND tmdb_popularity IS NOT NULL""",
                       (json.dumps(ids),))
    return {r[0]: r[1] for r in rows}


def _details(con: sqlite3.Connection, ids: list[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    out: dict[int, dict[str, Any]] = {}
    for r in con.execute("SELECT person_id, profile_path FROM person_details WHERE person_id IN "
                         "(SELECT value FROM json_each(?))", (json.dumps(ids),)):
        out[r[0]] = {"profile_path": r[1], "known_for": None}
    rows = con.execute(f"""SELECT c.person_id, m.id, m.title, m.year,
                                  ROW_NUMBER() OVER (PARTITION BY c.person_id
                                                     ORDER BY m.vote_count IS NULL, m.vote_count DESC, m.id) AS n
                           FROM ({CREDITS}) c JOIN movies m ON m.id = c.movie_id""", {"ids": json.dumps(ids)})
    for person_id, movie_id, title, year, n in rows:
        if n == 1:
            out.setdefault(person_id, {"profile_path": None})["known_for"] = {"movie_id": movie_id, "title": title,
                                                                              "year": year}
    return out
