"""GET /people?role=director|actor&q=: director and actor autocomplete, most films first (at most 10).

A match is a word of the name starting with q ("hanks", "tom ha"). n_films counts films in that role.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from backend.app.deps import get_lookups
from backend.app.schemas.errors import VALIDATION
from backend.app.schemas.lookup import Match
from backend.app.services.autocomplete import LIMIT, QUERY, respond
from backend.app.services.lookups import Lookups

router = APIRouter(tags=["form support"], responses=VALIDATION)


@router.get("/people", response_model=list[Match], summary="Director and actor autocomplete")
def people(response: Response, role: Literal["director", "actor"] = Query(..., description="director or actor"),
           q: str = QUERY, limit: int = LIMIT, lookups: Lookups = Depends(get_lookups)):
    return respond(response, lookups, role, q, limit)
