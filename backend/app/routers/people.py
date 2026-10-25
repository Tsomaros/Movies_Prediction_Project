"""GET /people?role=director|actor&q=: director and actor autocomplete, most films first (at most 10), and
GET /people/{id}: one person's page (Day 14.6).

A match is a word of the name starting with q ("hanks", "tom ha"; accents folded). n_films counts films in
that role; each hit also has a photo thumbnail and the film they're known for, from one query.
The person page has TMDB's details where the person pull found them (photo, biography, life dates, links),
stats from our own data and their films; cacheable for an hour, like the film pages.
"""

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.app.deps import get_db, get_lookups
from backend.app.repo import people as repo
from backend.app.routers.movies import CACHE, _summary
from backend.app.schemas.errors import VALIDATION, Message
from backend.app.schemas.person import PersonDetail, PersonMatch
from backend.app.services.autocomplete import LIMIT, QUERY, respond
from backend.app.services.lookups import Lookups
from backend.app.services.posters import profile

router = APIRouter(tags=["form support"], responses=VALIDATION)
MAX_ID = 2**63 - 1  # SQLite's largest integer: a bigger id can't exist (and would overflow the driver)


@router.get("/people", response_model=list[PersonMatch], summary="Director and actor autocomplete")
def people(response: Response, role: Literal["director", "actor"] = Query(..., description="director or actor"),
           q: str = QUERY, limit: int = LIMIT, lookups: Lookups = Depends(get_lookups),
           con: sqlite3.Connection = Depends(get_db)):
    hits = respond(response, lookups, role, q, limit)
    more = repo.extras(con, [h["id"] for h in hits], role)
    for h in hits:
        extra = more.get(h["id"], {})
        photo = profile(extra.get("profile_path"))
        h["thumb"], h["known_for"] = photo["small"] if photo else None, extra.get("known_for")
    return hits


@router.get("/people/{person_id}", response_model=PersonDetail, tags=["movies"],
            responses={404: {"model": Message, "description": "No such person"}},
            summary="One person: TMDB details, stats from our data, and their films")
def get_person(person_id: int, response: Response, con: sqlite3.Connection = Depends(get_db)):
    found = repo.person(con, person_id) if 0 < person_id <= MAX_ID else None
    if found is None:
        raise HTTPException(status_code=404, detail="Person not found")
    cast, crew = repo.credits(con, person_id)
    response.headers["Cache-Control"] = CACHE
    return {
        **found,
        "photo": profile(found["profile_path"]),
        "imdb_url": f"https://www.imdb.com/name/{found['imdb_id']}/" if found["imdb_id"] else None,
        "tmdb_url": f"https://www.themoviedb.org/person/{person_id}",
        "stats": repo.stats(con, person_id, cast),
        "cast_credits": [{**_summary(f), "character": f["character"]} for f in cast],
        "crew_credits": {job: [_summary(f) for f in films] for job, films in crew.items()},
    }
