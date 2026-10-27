"""Response models for the person pages' Career section (Day 14.8).

    CareerResponse       -> GET /people/{id}/career: their dated films in one role, the career line, the best
                            film and the track-record forecast of their next film
    CareerModelResponse  -> GET /people/{id}/career/model: the score model on "Their usual film" and
                            "Something new" (only `new` when a genre chip was asked for)
    CareerRole, RoleCount, CareerFilmOut, LinePoint, BestFilm, ForecastExplain, ForecastTest, TrackForecast,
    SlotPerson, RecipeLabels, RecipeOut, ModelScoreRange, ModelFilm, NewFilm, Chip
                         -> their parts
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

CareerRole = Literal["acting", "directing", "writing"]


class RoleCount(BaseModel):
    role: CareerRole
    film_count: int = Field(description="Dated films in this role")
    rated_count: int = Field(description="Of those, films with a usable score (50+ votes)")


class CareerFilmOut(BaseModel):
    movie_id: int
    title: str
    year: int
    release_date: Optional[str] = Field(description="YYYY-MM-DD, when TMDB has the day")
    score: Optional[float] = Field(description="TMDB's average score (1-10)")
    vote_count: int
    rated: bool = Field(description="50+ votes and a score: a solid dot that counts for the line and the forecast; "
                                    "otherwise a faint dot only")
    lead: Optional[bool] = Field(description="Acting: billed in the top 3; None for crew roles")
    character: Optional[str] = Field(description="Acting: who they played")
    poster_small: Optional[str] = Field(description="A TMDB poster (w342), when there is one")


class LinePoint(BaseModel):
    year: int
    value: float = Field(description="A centred mean over 5 rated films (fewer at the ends)")


class BestFilm(BaseModel):
    movie_id: int
    title: str
    year: int
    score: float


class ForecastExplain(BaseModel):
    n_rated: int = Field(description="Rated films the forecast uses")
    half_life: Optional[float] = Field(description="Years after which a film counts half; None: every film the same")
    own_share: float = Field(description="How much their weighted average is trusted (0-1); the database average "
                                         "gets the rest")
    own_avg: float = Field(description="Their weighted average score")
    db_avg: float = Field(description="The role's average score over rated films of the 10 latest years")


class ForecastTest(BaseModel):
    coverage: float = Field(description="Share of real next films from 2019 on inside a range built this way")
    n_people: int = Field(description="People whose next films were tested")


class TrackForecast(BaseModel):
    status: Literal["ok", "not_enough_films"] = Field(description="not_enough_films below 5 rated films")
    low: Optional[float] = Field(description="The 80% range of their next film's score; None without a forecast")
    mid: Optional[float]
    high: Optional[float]
    explain: Optional[ForecastExplain] = Field(description="The numbers behind it; None without a forecast")
    test: ForecastTest = Field(description="The backtest of this role's settings")


class CareerResponse(BaseModel):
    person_id: int
    role: CareerRole = Field(description="The role asked for, else their role with the most films")
    roles_available: list[RoleCount] = Field(description="Roles with 5+ rated films, plus the one shown")
    films: list[CareerFilmOut] = Field(description="Oldest first; films without a year are left out")
    line: list[LinePoint] = Field(description="One point per rated film, oldest first")
    best_film: Optional[BestFilm] = Field(description="Highest score (ties: more votes, then newer); None without "
                                                      "rated films")
    forecast: TrackForecast
    model_available: bool = Field(description="Acting or directing with 1+ rated film: /career/model answers")


class SlotPerson(BaseModel):
    id: int
    name: Optional[str]


PersonSlot = Union[SlotPerson, Literal["new"]]


class RecipeLabels(BaseModel):
    genres: list[str] = Field(description="Genre names")
    themes: list[str]
    collaborators: list[str] = Field(description="The named people other than the person")


class RecipeOut(BaseModel):
    genres: list[int] = Field(description="TMDB genre ids")
    themes: list[str]
    language: str
    runtime: int
    release_month: int
    release_year: int = Field(description="Next year")
    certification: str
    country: Optional[str]
    director: PersonSlot = Field(description='A person, or "new" for a new director')
    actors: list[PersonSlot] = Field(description='3 slots as shown on the card; the model gets "new" actors up to 5')
    budget_2025: Optional[int] = Field(description="Their median known budget in 2025 $, for the predictor pre-fill "
                                                   "only: the score model never gets a budget")
    labels: RecipeLabels


class ModelScoreRange(BaseModel):
    low: float = Field(description="The score model's calibrated 10th percentile")
    mid: float = Field(description="Its median")
    high: float = Field(description="Its 90th percentile")


class ModelFilm(BaseModel):
    recipe: RecipeOut
    prediction: ModelScoreRange


class NewFilm(ModelFilm):
    note: Optional[str] = Field(description="Set when they have worked in every genre, so their usual genres are used")


class Chip(BaseModel):
    genre_id: int
    name: str
    default: bool = Field(description="The genre of the default pick")


class CareerModelResponse(BaseModel):
    usual: Optional[ModelFilm] = Field(None, description='"Their usual film"; left out when a genre was asked for')
    new: NewFilm = Field(description='"Something new": the default pick, or the asked genre')
    chips: Optional[list[Chip]] = Field(None, description="Up to 4 genres they've never done; left out when a genre "
                                                          "was asked for")
