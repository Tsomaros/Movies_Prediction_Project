"""GET /people/{id}/career and GET /people/{id}/career/model: the person page's Career section (Day 14.8).

/career is the chart and the score and revenue track-record forecasts (no model call). /career/model scores
"Their usual film" and "Something new" with the film model (score and revenue, from one predict() call), through
the same PredictionService (validation and cache) as POST /predict, and keeps each answer in app.state.career_models; `genre` asks for one chip's "Something new" only. The film model
has no writer input, so role=writing is a 404 there. Both count toward the predict rate limit (RATE_LIMIT a
minute per IP) and are cacheable for an hour. A bad genre is a 422 whose detail names the problem.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from backend.app.deps import get_db, get_predictions
from backend.app.repo.career import Role, career_films
from backend.app.routers.movies import CACHE
from backend.app.routers.people import MAX_ID
from backend.app.routers.predict import ERRORS, rate_limited
from backend.app.schemas.career import CareerModelResponse, CareerResponse
from backend.app.schemas.errors import Message
from backend.app.services.career_forecast import MODEL_ROLES, NoCredits, career_response, person_exists
from backend.app.services.career_model import GenreAlreadyDone, UnknownGenre
from backend.app.services.prediction import PredictionService
from ml.data.clean import MIN_VOTES

router = APIRouter(tags=["movies"], dependencies=[Depends(rate_limited)])
NOT_FOUND = {404: {"model": Message, "description": "No such person, or no credits in this role"}}
ROLE = Query(None, description="acting, directing or writing; default: their role with the most films")
NO_WRITER = "The film model has no writer input"


def _person(con: sqlite3.Connection, person_id: int) -> None:
    if not (0 < person_id <= MAX_ID and person_exists(con, person_id)):
        raise HTTPException(status_code=404, detail="Person not found")


def _no_credits() -> HTTPException:
    return HTTPException(status_code=404, detail="No credits in this role")


@router.get("/people/{person_id}/career", response_model=CareerResponse, responses={**ERRORS, **NOT_FOUND},
            summary="One person's scores and box office over the years in one role, and track-record forecasts of "
                    "their next film")
def career(person_id: int, request: Request, response: Response, role: Optional[Role] = ROLE,
           con: sqlite3.Connection = Depends(get_db)):
    _person(con, person_id)
    try:
        out = career_response(con, request.app.state.career, person_id, role)
    except NoCredits:
        raise _no_credits() from None
    response.headers["Cache-Control"] = CACHE
    return out


@router.get("/people/{person_id}/career/model", response_model=CareerModelResponse, response_model_exclude_unset=True,
            responses={**ERRORS, **NOT_FOUND},
            summary='The film model\'s score and revenue for "Their usual film" and "Something new" (actor or '
                    'director)')
def career_model(person_id: int, request: Request, response: Response,
                 role: Role = Query(..., description="acting or directing (writing: 404, the model has no writer "
                                                     "input)"),
                 genre: Optional[int] = Query(None, description="A genre id from `chips`: only that \"Something "
                                                                "new\""),
                 con: sqlite3.Connection = Depends(get_db),
                 predictions: PredictionService = Depends(get_predictions)):
    _person(con, person_id)
    if role not in MODEL_ROLES:
        raise HTTPException(status_code=404, detail=NO_WRITER)
    films = career_films(con, person_id, role, MIN_VOTES)
    if not films:
        raise _no_credits()
    if not any(f["rated"] for f in films):  # nothing to build their usual film from (model_available is false)
        raise HTTPException(status_code=404, detail="No rated films in this role")
    next_year = request.app.state.clock().year + 1
    try:
        out = request.app.state.career_models.response(con, predictions, person_id, role, genre, next_year)
    except (UnknownGenre, GenreAlreadyDone) as e:
        message = "Unknown genre" if isinstance(e, UnknownGenre) else "Genre already done"
        return JSONResponse(status_code=422, content={"detail": message, "errors": {"genre": message}})
    response.headers["Cache-Control"] = CACHE
    return out
