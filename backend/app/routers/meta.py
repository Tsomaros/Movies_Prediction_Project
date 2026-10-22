"""GET /meta/options: every dropdown value and limit the creator form needs, in one call.

The fields come from ml.features.contract.describe(), the same definitions predict() validates against,
with the 27 theme names (themes.json) filled in. Languages and countries are the most common codes in
our data, as ISO codes only: the browser can name them (Intl.DisplayNames). The answer only changes with
a new database or contract, so it is built once per process and cached for an hour by clients.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from backend.app.deps import get_db
from backend.app.repo import meta as repo
from backend.app.schemas.lookup import Options
from ml.features.contract import CERTIFICATIONS, GENRES, MAX_YEAR, describe

router = APIRouter(tags=["form support"])
N_CODES = 60
YEARS_AHEAD = 4


def build_options(con: sqlite3.Connection, themes: list[str], today: date | None = None) -> dict[str, Any]:
    this_year = (today or date.today()).year
    fields = [{**f, "choices": themes} if f["name"] == "themes" else f for f in describe()]
    return {
        "fields": fields,
        "genres": list(GENRES),
        "certifications": list(CERTIFICATIONS),
        "themes": themes,
        "languages": repo.common_codes(con, "language", N_CODES),
        "countries": repo.common_codes(con, "country", N_CODES),
        "release_years": list(range(this_year, min(this_year + YEARS_AHEAD, MAX_YEAR) + 1)),
        "months": list(range(1, 13)),
    }


@router.get("/meta/options", response_model=Options, summary="Every dropdown value and limit for the form")
def options(request: Request, response: Response, con: sqlite3.Connection = Depends(get_db)):
    state = request.app.state
    if getattr(state, "options", None) is None:
        state.options = build_options(con, sorted(state.predictor.ctx.themes))
    response.headers["Cache-Control"] = "public, max-age=3600"
    return state.options
