"""GET /collections?q=: franchise (TMDB collection) autocomplete, most films first (at most 10)."""

from fastapi import APIRouter, Depends, Response

from backend.app.deps import get_lookups
from backend.app.schemas.errors import VALIDATION
from backend.app.schemas.lookup import Match
from backend.app.services.search.autocomplete import LIMIT, QUERY, respond
from backend.app.services.search.lookups import Lookups

router = APIRouter(tags=["form support"], responses=VALIDATION)


@router.get("/collections", response_model=list[Match], summary="Franchise autocomplete")
def collections(response: Response, q: str = QUERY, limit: int = LIMIT, lookups: Lookups = Depends(get_lookups)):
    return respond(response, lookups, "collection", q, limit)
