"""GET /movies (search, filters, sorting, pages) and GET /movies/{id} (one film with similar films).

Both are cacheable for an hour (Cache-Control: public, max-age=3600): the database changes with a new build, plus
the new and upcoming films the refresher merges every 6 hours (services/fresh/), so a list that holds one of those
films (fresh_films), and every `when` window, is cached for ten minutes. `when=released|upcoming` lists a window; without `when`
(and without a text search) a film not yet released is left out. Similar films come from the Day 7 comparables index with
no date rule (any year) and never the film itself; a film outside the index's pool (no usable score)
is matched on its genres, themes, language, era and budget, without a synopsis.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.app.deps import get_db, get_predictor
from backend.app.errors import unprocessable
from backend.app.repo import movies as repo
from backend.app.schemas.errors import VALIDATION, Message
from backend.app.schemas.form import Genre
from backend.app.schemas.movies import MovieDetail, MovieList, Sort, When
from backend.app.services.movies.posters import poster, profile
from ml.features.contract import GENRES
from ml.predict import Predictor

router = APIRouter(tags=["movies"], responses=VALIDATION)
CACHE = "public, max-age=3600"
LIVE_CACHE = "public, max-age=600"
MAX_PAGE_SIZE = 48
N_SIMILAR = 6


def _summary(r: dict[str, Any]) -> dict[str, Any]:
    return {**r, "score": r["vote_average"], "votes": r["vote_count"] or 0, "poster": poster(r["poster_path"])}


@router.get("/movies", response_model=MovieList, summary="Search and browse films")
def list_movies(
    request: Request,
    response: Response,
    q: Optional[str] = Query(None, max_length=200, description="Words to find in the title, original title or overview"),
    genre: Optional[Genre] = None,
    year_from: Optional[int] = Query(None, ge=1900, le=2100),
    year_to: Optional[int] = Query(None, ge=1900, le=2100),
    language: Optional[str] = Query(None, pattern=r"^[a-z]{2}$", description="Original language code (en, fr...)"),
    score_min: Optional[float] = Query(None, ge=0, le=10, description="Lowest TMDB score; films with any number of votes"),
    sort: Sort = Query("popularity", description="popularity (TMDB, when pulled), newest, soonest (the next release "
                                                 "first), title, score (500+ votes only) or revenue (2025 $, trusted "
                                                 "figures only)"),
    when: Optional[When] = Query(None, description="released: out in the last 14 days; upcoming: due in the next 60 "
                                                   "(UTC). Without it, and without q, unreleased films are left out"),
    page: int = Query(1, ge=1, le=10_000),
    page_size: int = Query(24, ge=1, le=MAX_PAGE_SIZE),
    con: sqlite3.Connection = Depends(get_db),
):
    if year_from is not None and year_to is not None and year_from > year_to:
        return unprocessable({"year_to": "must be the same as or after year_from"})
    rows, total = repo.search(con, q, genre, year_from, year_to, language, score_min, sort, page, page_size,
                              when=when, today=request.app.state.clock().date())
    # new and upcoming films change by the day: ten minutes for a window or a page that holds one, an hour otherwise
    fresh = when is not None or bool(repo.fresh_ids(con, [r["id"] for r in rows]))
    response.headers["Cache-Control"] = LIVE_CACHE if fresh else CACHE
    return {"items": [_summary(r) for r in rows], "total": total, "page": page, "page_size": page_size,
            "pages": math.ceil(total / page_size)}


def _similar(predictor: Predictor, film: dict[str, Any], themes: list[str]) -> list[dict[str, Any]]:
    index = predictor.index
    if index is None:
        return []
    row = index.row(film["id"])
    if row is not None:  # the film's own row: its genres, themes and synopsis vector
        genres = [g for g, on in zip(GENRES, index.genres[row]) if on]
        themes = [t for t, on in zip(index.theme_names, index.themes[row]) if on]
        vector = index.vectors[row] if index.vectors[row].any() else None
        budget = index.budget[row]
        log_budget = None if np.isnan(budget) else math.log(budget)
    else:
        genres, vector = [g for g in film["genres"] if g in GENRES], None
        trusted = film["budget_2025"] and not film["money_suspect"]
        log_budget = math.log(film["budget_2025"]) if trusted else None
    found = index.query(genres, themes, film["original_language"], vector, film["year"] or 2000, log_budget,
                        as_of=None, n=N_SIMILAR, exclude=film["id"])
    return [{**f, "poster": poster(f["poster_path"])} for f in found]


@router.get("/movies/{movie_id}", response_model=MovieDetail, responses={404: {"model": Message, "description": "No such film"}},
            summary="One film: facts, cast and crew, money, score and similar films")
def get_movie(movie_id: int, response: Response, con: sqlite3.Connection = Depends(get_db),
              predictor: Predictor = Depends(get_predictor)):
    film = repo.movie(con, movie_id)
    if film is None:
        raise HTTPException(status_code=404, detail=f"No film with id {movie_id}")
    keywords = repo.film_keywords(con, movie_id)
    themes = [name for name, ids in predictor.ctx.themes.items() if keywords & ids]
    response.headers["Cache-Control"] = CACHE
    return {
        **_summary(film),
        "certification": film["us_certification"],
        "themes": themes,
        "franchise": {"id": film["collection_id"], "name": film["collection_name"]} if film["collection_id"] else None,
        "money": {"budget": film["budget"], "revenue": film["revenue"], "budget_2025": film["budget_2025"],
                  "revenue_2025": film["revenue_2025"], "suspect": bool(film["money_suspect"]),
                  "suspect_reason": film["money_suspect_reason"], "revenue_incomplete": bool(film["revenue_incomplete"])},
        "rating": {"average": film["vote_average"], "votes": film["vote_count"] or 0, "usable": film["score_ok"]},
        "cast": [{**c, "photo": profile(c["profile_path"])} for c in film["cast"]],
        "similar": _similar(predictor, film, themes),
    }
