"""The logged-in user's lists: GET /me/movies, PUT and DELETE /me/movies/{id}, GET /me/movies/status (Day 14).

A film is in at most one list: watched (with a date, today in Athens unless given, and an optional 1-10
rating) or plan to watch (neither; moving a film there clears them). For a watched film, a date or rating
left out of the body keeps its current value; "rating": null clears the rating. The database enforces this too.
GET /me/movies joins two databases: it reads every entry of the user (at most MAX_ENTRIES) from Postgres,
fetches those films from SQLite in one query, then sorts and pages in Python. A film that left the movie
database is skipped. Unknown film -> 404; the 501st entry -> 409; more than 30 writes a minute -> 429.
Every answer is private and never cached.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date, timedelta
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.deps import current_user, get_db, get_userdb, no_store, now, same_origin_write, write_limited
from backend.app.errors import unprocessable
from backend.app.repo import movies as movies_repo
from backend.app.routers.movies import _summary
from backend.app.schemas.accounts import Entry, EntryRequest, MyMovieList, MySort, Status, StatusList
from backend.app.schemas.errors import VALIDATION, Message
from backend.app.services.auth import today_athens
from backend.app.userdb import repo

router = APIRouter(tags=["my movies"], dependencies=[Depends(no_store), Depends(same_origin_write)])
MAX_ENTRIES = 500
MAX_STATUS_IDS = 48  # one browse page at the largest page size
PAGE_SIZE = 24
ERRORS = {**VALIDATION, 401: {"model": Message, "description": "Not logged in"},
          403: {"model": Message, "description": "Not sent from the app"}}
WRITE_ERRORS = {**ERRORS, 404: {"model": Message, "description": "No such film"},
                409: {"model": Message, "description": "The list is full"},
                429: {"model": Message, "description": "Too many changes in a minute; see Retry-After"}}
WRITE = [Depends(write_limited)]


def film_or_404(con: sqlite3.Connection, movie_id: int) -> dict[str, Any]:
    found = movies_repo.summaries(con, [movie_id])
    if movie_id not in found:
        raise HTTPException(status_code=404, detail=f"No film with id {movie_id}")
    return found[movie_id]


def order(items: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    """Newest added first, then (stable) by the chosen sort: title A-Z, rating high-low, watched date new-old."""
    items = sorted(items, key=lambda i: i["entry"]["added_at"], reverse=True)
    if sort == "title":
        return sorted(items, key=lambda i: i["movie"]["title"].casefold())
    if sort == "rating":
        return sorted(items, key=lambda i: i["entry"]["rating"] or 0, reverse=True)
    if sort == "watched":
        return sorted(items, key=lambda i: i["entry"]["watched_on"] or date.min, reverse=True)
    return items


@router.get("/me/movies", response_model=MyMovieList, responses=ERRORS, summary="One of my lists, a page at a time")
def my_movies(status: Status = "watched", sort: MySort = "added", page: int = Query(1, ge=1, le=1000),
              user: dict = Depends(current_user), conn: psycopg.Connection = Depends(get_userdb),
              con: sqlite3.Connection = Depends(get_db)):
    rows = [r for r in repo.entries(conn, user["id"]) if r["status"] == status]
    films = movies_repo.summaries(con, [r["movie_id"] for r in rows])
    items = order([{"movie": _summary(films[r["movie_id"]]), "entry": r} for r in rows if r["movie_id"] in films], sort)
    start = (page - 1) * PAGE_SIZE
    return {"items": items[start:start + PAGE_SIZE], "total": len(items), "page": page, "page_size": PAGE_SIZE,
            "pages": math.ceil(len(items) / PAGE_SIZE), "counts": repo.counts(conn, user["id"])}


@router.get("/me/movies/status", response_model=StatusList, responses=ERRORS,
            summary="Which of these films (up to 48) are in my lists")
def statuses(ids: str = Query(..., max_length=600, description="Comma-separated film ids"),
             user: dict = Depends(current_user), conn: psycopg.Connection = Depends(get_userdb)):
    parts = [p.strip() for p in ids.split(",") if p.strip()]
    if not all(p.isdigit() for p in parts):
        return unprocessable({"ids": "must be film ids separated by commas"})
    if len(parts) > MAX_STATUS_IDS:
        return unprocessable({"ids": f"at most {MAX_STATUS_IDS} films at a time"})
    return {"items": repo.statuses(conn, user["id"], {int(p) for p in parts})}


@router.put("/me/movies/{movie_id}", response_model=Entry, dependencies=WRITE, responses=WRITE_ERRORS,
            summary="Put a film in a list, with its watched date and rating")
def set_entry(movie_id: int, body: EntryRequest, request: Request, user: dict = Depends(current_user),
              conn: psycopg.Connection = Depends(get_userdb), con: sqlite3.Connection = Depends(get_db)):
    film_or_404(con, movie_id)
    today = today_athens(now(request))
    if body.watched_on is not None and not date(1900, 1, 1) <= body.watched_on <= today + timedelta(days=1):
        return unprocessable({"watched_on": "must be a date between 1900 and today"})
    with conn.transaction():
        repo.lock_user(conn, user["id"])
        old = repo.entry(conn, user["id"], movie_id)
        if old is None and repo.count_entries(conn, user["id"]) >= MAX_ENTRIES:
            raise HTTPException(status_code=409, detail=f"Your lists are full ({MAX_ENTRIES} films). Remove one first.")
        was_watched = old is not None and old["status"] == "watched"
        if body.status == "plan_to_watch":
            watched_on, rating = None, None
        else:  # a field left out keeps its value (a click on "Watched" never drops a rating); null clears the rating
            watched_on = body.watched_on or (old["watched_on"] if was_watched else None) or today
            rating = body.rating if "rating" in body.model_fields_set else (old["rating"] if was_watched else None)
        return repo.set_entry(conn, user["id"], movie_id, body.status, watched_on, rating)


@router.delete("/me/movies/{movie_id}", status_code=204, dependencies=WRITE, responses=WRITE_ERRORS,
               summary="Take a film out of my lists (its notes stay)")
def delete_entry(movie_id: int, user: dict = Depends(current_user), conn: psycopg.Connection = Depends(get_userdb),
                 con: sqlite3.Connection = Depends(get_db)) -> None:
    film_or_404(con, movie_id)
    repo.delete_entry(conn, user["id"], movie_id)
