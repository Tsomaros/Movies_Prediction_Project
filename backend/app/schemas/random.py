"""Response model for GET /random ("Surprise me", Day 14.5).

    RandomMovie  -> the browse card plus the runtime
    RandomPick   -> the pick (or None with the reason), posters for the shuffle and how many films it was picked from
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.app.schemas.movies import MovieSummary
from backend.app.schemas.prediction import Poster

Source = Literal["all", "watchlist"]
Reason = Literal["watchlist_empty", "no_match", "all_seen"]


class RandomMovie(MovieSummary):
    runtime: Optional[int] = Field(description="Minutes; None when unknown")


class RandomPick(BaseModel):
    movie: Optional[RandomMovie] = Field(description="None when there is nothing to pick (see reason)")
    reason: Optional[Reason] = Field(description="watchlist_empty: no films on the watchlist; no_match: the filters "
                                                 "match no film; all_seen: every match is watched or already shown")
    shuffle: list[Poster] = Field(description="Up to 8 posters of other candidates, for the reveal")
    pool: int = Field(description="How many films the pick was made from (0 with a reason)")
