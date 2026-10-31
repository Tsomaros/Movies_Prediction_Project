"""GET /companies?q=: production company (studio) autocomplete, most films first (at most 10)."""

from fastapi import APIRouter, Depends, Response

from backend.app.deps import get_lookups
from backend.app.schemas.errors import VALIDATION
from backend.app.schemas.lookup import Match
from backend.app.services.search.autocomplete import LIMIT, QUERY, respond
from backend.app.services.search.lookups import Lookups

router = APIRouter(tags=["form support"], responses=VALIDATION)


@router.get("/companies", response_model=list[Match], summary="Studio autocomplete")
def companies(response: Response, q: str = QUERY, limit: int = LIMIT, lookups: Lookups = Depends(get_lookups)):
    return respond(response, lookups, "company", q, limit)
