"""GET /random: "Surprise me", one random film (Day 14.5).

source=all picks from the whole database above the quality floor (random_pick.FLOOR; gems=true removes it,
a poster is always needed) and, when logged in, never a watched film. Logged out it works too, also on a
server with no accounts database. source=watchlist picks from the user's watchlist, with no floor: 401 when
logged out, 503 without an accounts database. Optional filters: genre, decade (1960, 1970 ... 2020),
language, max_runtime (a film with no runtime is left out). exclude = the ids already shown in this tab
(comma-separated, at most MAX_EXCLUDE), so "Spin again" never repeats a film.
Nothing to pick is not an error: a 200 with movie None and the reason. 60 spins a minute per client IP.
Every answer is private and never cached (it is random and may depend on the user).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.deps import get_db, limit, maybe_user, no_store
from backend.app.errors import unprocessable
from backend.app.repo import movies as repo
from backend.app.routers.movies import _summary
from backend.app.schemas.errors import VALIDATION, Message
from backend.app.schemas.form import Genre
from backend.app.schemas.random import RandomPick, Source
from backend.app.services import random_pick
from backend.app.services.posters import poster
from backend.app.userdb import repo as userdb

router = APIRouter(tags=["movies"], dependencies=[Depends(no_store)])
MAX_EXCLUDE = 200
ERRORS = {**VALIDATION, 401: {"model": Message, "description": "Watchlist mode needs a login"},
          429: {"model": Message, "description": "Too many spins in a minute; see Retry-After"},
          503: {"model": Message, "description": "Watchlist mode on a server without accounts"}}
SPINS = Depends(limit("random", "Too many spins in a minute. Please wait a moment and try again."))


def _entries(request: Request, user: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if user is None:
        return []
    with request.app.state.userdb.connection() as conn:
        return userdb.entries(conn, user["id"])


@router.get("/random", response_model=RandomPick, responses=ERRORS, dependencies=[SPINS],
            summary="Surprise me: a random film you haven't seen, or one from your watchlist")
def random_film(
    request: Request,
    source: Source = "all",
    genre: Optional[Genre] = None,
    decade: Optional[int] = Query(None, ge=1960, le=2020, multiple_of=10, description="1960, 1970 ... 2020"),
    language: Optional[str] = Query(None, pattern=r"^[a-z]{2}$", description="Original language code (en, fr...)"),
    max_runtime: Optional[int] = Query(None, ge=60, le=240, description="Longest runtime in minutes"),
    gems: bool = Query(False, description="Include hidden gems: no vote/score floor (whole-database mode)"),
    exclude: str = Query("", pattern=r"^(\d+(,\d+)*)?$", max_length=2000,
                         description="Ids already shown, comma-separated (at most 200)"),
    con: sqlite3.Connection = Depends(get_db),
    user: Optional[dict[str, Any]] = Depends(maybe_user),
):
    today = request.app.state.clock().date()  # a film not yet released is never picked
    shown = [int(i) for i in exclude.split(",") if i]
    if len(shown) > MAX_EXCLUDE:
        return unprocessable({"exclude": f"at most {MAX_EXCLUDE} ids"})
    filters = {"genre": genre, "decade": decade, "language": language, "max_runtime": max_runtime}
    if source == "watchlist":
        if request.app.state.userdb is None:
            raise HTTPException(status_code=503, detail="Accounts are not set up on this server")
        if user is None:
            raise HTTPException(status_code=401, detail="Please log in first")
        listed = [e["movie_id"] for e in _entries(request, user) if e["status"] == "plan_to_watch"]
        if not listed:
            return {"movie": None, "reason": "watchlist_empty", "shuffle": [], "pool": 0}
        candidates, seen = repo.random_candidates(con, **filters, ids=listed, today=today), []
    else:
        floor = None if gems else random_pick.FLOOR
        candidates = repo.random_candidates(con, **filters, floor=floor, today=today)
        seen = [e["movie_id"] for e in _entries(request, user) if e["status"] == "watched"]
    chosen, reason, left = random_pick.pick(candidates, seen, shown)
    if chosen is None:
        return {"movie": None, "reason": reason, "shuffle": [], "pool": 0}
    paths = repo.posters(con, random_pick.shuffle_ids(left, chosen))
    return {"movie": _summary(repo.summaries(con, [chosen])[chosen]), "reason": None,
            "shuffle": [poster(p) for p in paths.values()], "pool": len(left)}
