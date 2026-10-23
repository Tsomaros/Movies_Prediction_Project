"""Response models for the public movie pages.

    MovieList    -> GET /movies: one page of summaries, with the total for the pager
    MovieDetail  -> GET /movies/{id}: facts, people, money, score, posters and similar films

Money is shown as stored: nominal US dollars as TMDB reports them, and the same in 2025 dollars. A figure
our cleaning rules doubt (`money.suspect`) is still shown, with the reason, but never trained on.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.app.schemas.prediction import Comparable, Poster

Sort = Literal["popularity", "newest", "title", "score", "revenue"]


class MovieSummary(BaseModel):
    id: int
    title: str
    year: Optional[int]
    release_date: Optional[str]
    genres: list[str]
    original_language: Optional[str]
    score: Optional[float] = Field(description="TMDB vote average (0-10); None when nobody voted")
    votes: int
    score_ok: bool = Field(description="At least 50 votes: the score is used by our models")
    popularity: Optional[float] = Field(description="TMDB popularity when pulled (display and sorting only)")
    revenue_2025: Optional[float] = Field(description="Worldwide revenue in 2025 dollars; None when unknown or doubted")
    poster: Optional[Poster]


class MovieList(BaseModel):
    items: list[MovieSummary]
    total: int
    page: int
    page_size: int
    pages: int


class Ref(BaseModel):
    id: int
    name: Optional[str]


class Company(Ref):
    origin_country: Optional[str]


class CastMember(Ref):
    character: Optional[str]
    order: Optional[int]


class CrewMember(Ref):
    job: str


class Money(BaseModel):
    budget: Optional[int] = Field(description="Nominal US dollars, as reported; None when unknown")
    revenue: Optional[int]
    budget_2025: Optional[float] = Field(description="In 2025 dollars (US CPI)")
    revenue_2025: Optional[float]
    suspect: bool = Field(description="Our cleaning rules doubt these figures (shown, never trained on)")
    suspect_reason: Optional[str]
    revenue_incomplete: bool = Field(description="Released less than 182 days before the data was pulled")


class Score(BaseModel):
    average: Optional[float]
    votes: int
    usable: bool


class MovieDetail(MovieSummary):
    original_title: Optional[str]
    tagline: Optional[str]
    overview: Optional[str]
    runtime: Optional[int]
    status: Optional[str]
    certification: Optional[str] = Field(description="US certification as TMDB lists it")
    spoken_languages: list[str]
    themes: list[str] = Field(description="Our story themes, from the film's TMDB keywords")
    franchise: Optional[Ref]
    companies: list[Company]
    countries: list[str]
    cast: list[CastMember]
    crew: list[CrewMember]
    money: Money
    rating: Score
    similar: list[Comparable] = Field(description="Films like this one, from any year (never itself)")
