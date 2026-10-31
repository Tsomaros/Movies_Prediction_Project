"""Shared by the autocomplete routers (people, companies, collections): parameters, caching and the search.

    QUERY, LIMIT       -> the query parameters every autocomplete endpoint takes
    respond(response, lookups, kind, q, limit) -> the matches, with an hour-long Cache-Control
"""

from __future__ import annotations

from typing import Any

from fastapi import Query, Response

from backend.app.services.search.lookups import LIMIT as MAX_LIMIT
from backend.app.services.search.lookups import Lookups

CACHE = "public, max-age=3600"
QUERY = Query(..., min_length=1, max_length=100, description="The start of any word of the name (case-insensitive)")
LIMIT = Query(MAX_LIMIT, ge=1, le=MAX_LIMIT, description=f"At most this many results (1-{MAX_LIMIT})")


def respond(response: Response, lookups: Lookups, kind: str, q: str, limit: int) -> list[dict[str, Any]]:
    response.headers["Cache-Control"] = CACHE
    return lookups.search(kind, q, limit)
