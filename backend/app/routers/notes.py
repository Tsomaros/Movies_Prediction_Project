"""The logged-in user's private notes: GET and POST /me/movies/{id}/notes, GET /me/notes, PATCH and DELETE
/me/notes/{note_id} (Day 14).

Notes work like a journal: many per film, on any film (listed or not), newest first, 1-2,000 characters
(after trimming; the database checks the length too). Someone else's note answers 404, the same as a note
that doesn't exist, so its existence never shows. The 201st note -> 409; more than 30 writes a minute
(shared with the lists) -> 429. Every answer is private and never cached.
"""

from __future__ import annotations

import math
import sqlite3

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.deps import current_user, get_db, get_userdb, no_store, same_origin_write
from backend.app.repo import movies as movies_repo
from backend.app.routers.movies import _summary
from backend.app.routers.my_movies import ERRORS, PAGE_SIZE, WRITE, WRITE_ERRORS, film_or_404
from backend.app.schemas.accounts import Note, NoteList, NotePage, NoteRequest
from backend.app.schemas.errors import Message
from backend.app.userdb import repo

router = APIRouter(tags=["notes"], dependencies=[Depends(no_store), Depends(same_origin_write)])
MAX_NOTES = 200
NOT_YOURS = {**WRITE_ERRORS, 404: {"model": Message, "description": "No such note"}}


@router.get("/me/movies/{movie_id}/notes", response_model=NoteList, responses={**ERRORS, 404: WRITE_ERRORS[404]},
            summary="My notes on one film, newest first")
def film_notes(movie_id: int, user: dict = Depends(current_user), conn: psycopg.Connection = Depends(get_userdb),
               con: sqlite3.Connection = Depends(get_db)):
    film_or_404(con, movie_id)
    return {"items": repo.notes_for(conn, user["id"], movie_id)}


@router.post("/me/movies/{movie_id}/notes", response_model=Note, status_code=201, dependencies=WRITE,
             responses=WRITE_ERRORS, summary="Add a note to a film")
def add_note(movie_id: int, body: NoteRequest, user: dict = Depends(current_user),
             conn: psycopg.Connection = Depends(get_userdb), con: sqlite3.Connection = Depends(get_db)):
    film_or_404(con, movie_id)
    with conn.transaction():
        repo.lock_user(conn, user["id"])
        if repo.count_notes(conn, user["id"]) >= MAX_NOTES:
            raise HTTPException(status_code=409, detail=f"You have {MAX_NOTES} notes, the most allowed. Delete one first.")
        return repo.add_note(conn, user["id"], movie_id, body.body)


@router.get("/me/notes", response_model=NotePage, responses=ERRORS, summary="All my notes, newest first, with their films")
def all_notes(page: int = Query(1, ge=1, le=1000), user: dict = Depends(current_user),
              conn: psycopg.Connection = Depends(get_userdb), con: sqlite3.Connection = Depends(get_db)):
    rows, total = repo.notes_page(conn, user["id"], PAGE_SIZE, (page - 1) * PAGE_SIZE)
    films = movies_repo.summaries(con, list({r["movie_id"] for r in rows}))
    items = [{**r, "movie": _summary(films[r["movie_id"]]) if r["movie_id"] in films else None} for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": PAGE_SIZE,
            "pages": math.ceil(total / PAGE_SIZE), "counts": repo.counts(conn, user["id"])}


@router.patch("/me/notes/{note_id}", response_model=Note, dependencies=WRITE, responses=NOT_YOURS, summary="Edit my note")
def edit_note(note_id: int, body: NoteRequest, user: dict = Depends(current_user),
              conn: psycopg.Connection = Depends(get_userdb)):
    note = repo.update_note(conn, user["id"], note_id, body.body)
    if note is None:
        raise HTTPException(status_code=404, detail="No such note")
    return note


@router.delete("/me/notes/{note_id}", status_code=204, dependencies=WRITE, responses=NOT_YOURS, summary="Delete my note")
def delete_note(note_id: int, user: dict = Depends(current_user), conn: psycopg.Connection = Depends(get_userdb)) -> None:
    if not repo.delete_note(conn, user["id"], note_id):
        raise HTTPException(status_code=404, detail="No such note")
