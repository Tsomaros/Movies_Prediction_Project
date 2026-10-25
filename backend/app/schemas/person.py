"""Response models for the person pages (Day 14.6).

    PersonMatch   -> GET /people: an autocomplete hit plus a photo thumbnail and the film they're known for
    PersonDetail  -> GET /people/{id}: TMDB details (None where TMDB had none), stats from our data, and films
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from backend.app.schemas.lookup import Match
from backend.app.schemas.movies import MovieSummary
from backend.app.schemas.prediction import Poster


class PersonMatch(Match):
    thumb: Optional[str] = Field(None, description="A small TMDB photo (w185), when TMDB has one")
    known_for: Optional[str] = Field(None, description="Title of their most-voted film in this role")


class PersonRef(BaseModel):
    id: int
    name: Optional[str]
    shared_films: int


class GenreCount(BaseModel):
    name: str
    films: int


class AvgScore(BaseModel):
    value: float
    films: int = Field(description="Films with a usable score (50+ votes) it averages")


class BoxOffice(BaseModel):
    total: float = Field(description="Worldwide revenue in 2025 dollars, trusted figures only")
    films: int = Field(description="Films with a trusted revenue")
    of: int = Field(description="All their films as cast")


class PersonStats(BaseModel):
    film_count: int = Field(description="Films as cast in our data")
    first_year: Optional[int]
    last_year: Optional[int]
    top_genres: list[GenreCount]
    avg_score: Optional[AvgScore]
    box_office_2025: Optional[BoxOffice]
    top_costar: Optional[PersonRef] = Field(description="2+ shared films; ties by TMDB popularity, then name")
    top_director: Optional[PersonRef] = Field(description="Directed 2+ of their films")


class CastCredit(MovieSummary):
    character: Optional[str]


class PersonDetail(BaseModel):
    id: int
    name: Optional[str]
    photo: Optional[Poster] = Field(description="small: w185, large: h632")
    biography: Optional[str] = Field(description="Plain text; paragraphs separated by blank lines")
    birthday: Optional[str]
    deathday: Optional[str]
    place_of_birth: Optional[str]
    known_for_department: Optional[str]
    imdb_url: Optional[str]
    homepage: Optional[str] = Field(description="http(s) only")
    tmdb_url: str
    stats: PersonStats
    cast_credits: list[CastCredit] = Field(description="Newest first")
    crew_credits: dict[str, list[MovieSummary]] = Field(description="Key crew jobs (Director, Writer...), newest first")
