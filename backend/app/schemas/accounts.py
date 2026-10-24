"""Request and response models for the demo account: login, lists, ratings and notes (Day 14).

    LoginRequest   -> POST /auth/login
    Me             -> POST /auth/login, POST /auth/demo, GET /auth/me: {"user": User or null}
    EntryRequest   -> PUT /me/movies/{id}: the list, and for watched films the date and rating
    Entry          -> one list entry (PUT /me/movies/{id}, GET /me/movies/status)
    MyMovieList    -> GET /me/movies: one tab's page of films with their entries, plus every tab's count
    StatusList     -> GET /me/movies/status: the entries among up to 48 films
    NoteRequest    -> POST /me/movies/{id}/notes, PATCH /me/notes/{id}
    Note, NoteList -> one film's notes; NotePage -> GET /me/notes, every note with its film

A film's card (`movie`) is the same MovieSummary as GET /movies, so the frontend reuses its grid.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from backend.app.schemas.movies import MovieSummary

Status = Literal["watched", "plan_to_watch"]
MySort = Literal["added", "title", "rating", "watched"]
MAX_NOTE = 2000
NoteBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NOTE)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    password: str = Field(min_length=1, max_length=200)


class User(BaseModel):
    id: int
    username: str
    is_demo: bool


class Me(BaseModel):
    user: Optional[User]


class EntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status
    watched_on: Optional[dt.date] = Field(None, description="Watched films only; today (Athens) when left out")
    rating: Optional[int] = Field(None, ge=1, le=10, description="Watched films only, 1-10; left out keeps the current "
                                                                 "rating, null clears it")


class Entry(BaseModel):
    movie_id: int
    status: Status
    watched_on: Optional[dt.date]
    rating: Optional[int]
    added_at: dt.datetime
    updated_at: dt.datetime


class Counts(BaseModel):
    watched: int
    plan_to_watch: int
    notes: int


class MyMovie(BaseModel):
    movie: MovieSummary
    entry: Entry


class MyMovieList(BaseModel):
    items: list[MyMovie]
    total: int
    page: int
    page_size: int
    pages: int
    counts: Counts


class StatusList(BaseModel):
    items: list[Entry] = Field(description="Only the films that are in a list")


class NoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: NoteBody


class Note(BaseModel):
    id: int
    movie_id: int
    body: str
    created_at: dt.datetime
    updated_at: dt.datetime


class NoteList(BaseModel):
    items: list[Note]


class NoteWithMovie(Note):
    movie: Optional[MovieSummary] = Field(description="None if the film has left the movie database")


class NotePage(BaseModel):
    items: list[NoteWithMovie]
    total: int
    page: int
    page_size: int
    pages: int
    counts: Counts
