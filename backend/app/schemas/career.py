"""Response models for the person pages' Career section (Day 14.8).

    CareerResponse       -> GET /people/{id}/career: their dated films in one role and, per metric (score and
                            revenue), the career line, the best film and the track-record forecast of their next film
    CareerModelResponse  -> GET /people/{id}/career/model: the film model's score and revenue ranges for "Their
                            usual film" and "Something new" (only `new` when a genre chip was asked for)
    CareerRole, RoleCount, CareerFilmOut, LinePoint, BestFilm, ForecastExplain, ForecastTest, TrackForecast,
    CareerMetric, CareerMetrics, SlotPerson, RecipeLabels, RecipeOut, ModelScoreRange, ModelRevenueRange,
    ModelPrediction, ModelFilm, NewFilm, Chip
                         -> their parts

Revenue is always in whole 2025 dollars, from trusted figures only (known, not doubted, not incomplete).
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
    revenue: Optional[float] = Field(description="Worldwide box office in 2025 $ when it is trusted (known, not "
                                                 "doubted, not incomplete): a dot in the revenue view")
    vote_count: int
    rated: bool = Field(description="50+ votes and a score: a solid dot that counts for the line and the forecast; "
                                    "otherwise a faint dot only")
    lead: Optional[bool] = Field(description="Acting: billed in the top 3; None for crew roles")
    character: Optional[str] = Field(description="Acting: who they played")
    poster_small: Optional[str] = Field(description="A TMDB poster (w342), when there is one")


class LinePoint(BaseModel):
    year: int
    value: float = Field(description="A centred mean over 5 films with a value (fewer at the ends); revenue: the "
                                     "geometric mean, in 2025 $")


class BestFilm(BaseModel):
    movie_id: int
    title: str
    year: int
    value: float = Field(description="Its score, or its trusted revenue in 2025 $")


class ForecastExplain(BaseModel):
    n_films: int = Field(description="Films the forecast uses: rated films (score) or films with a trusted "
                                     "revenue (revenue)")
    half_life: Optional[float] = Field(description="Years after which a film counts half; None: every film the same")
    own_share: float = Field(description="How much their weighted average is trusted (0-1); the database average "
                                         "gets the rest")
    own_avg: float = Field(description="Their weighted average: a score, or the weighted geometric mean revenue in "
                                       "2025 $")
    db_avg: float = Field(description="The role's average over the 10 latest years: the mean score of rated films, "
                                      "or the geometric mean revenue in 2025 $ of trusted-revenue films")


class ForecastTest(BaseModel):
    coverage: float = Field(description="Share of real next films from 2019 on inside a range built this way")
    n_people: int = Field(description="People whose next films were tested")
    within_2x: Optional[float] = Field(None, description="Revenue only: share of those next films whose revenue was "
                                                         "within 2x of the middle; None for the score")


class TrackForecast(BaseModel):
    status: Literal["ok", "not_enough_films"] = Field(description="not_enough_films below 5 films with a value")
    low: Optional[float] = Field(description="The 80% range of their next film's score, or of its revenue in 2025 $; "
                                             "None without a forecast")
    mid: Optional[float]
    high: Optional[float]
    explain: Optional[ForecastExplain] = Field(description="The numbers behind it; None without a forecast")
    test: ForecastTest = Field(description="The backtest of this role's settings for this metric")


class CareerMetric(BaseModel):
    line: list[LinePoint] = Field(description="One point per film with a value, oldest first")
    best_film: Optional[BestFilm] = Field(description="Highest value (ties: more votes, then newer); None without "
                                                      "films with a value")
    forecast: TrackForecast


class CareerMetrics(BaseModel):
    score: CareerMetric = Field(description="Rated films' scores (50+ votes)")
    revenue: CareerMetric = Field(description="Trusted revenues, in 2025 $")


class CareerResponse(BaseModel):
    person_id: int
    role: CareerRole = Field(description="The role asked for, else their role with the most films")
    roles_available: list[RoleCount] = Field(description="Roles with 5+ rated films, plus the one shown")
    films: list[CareerFilmOut] = Field(description="Oldest first; films without a year are left out")
    metrics: CareerMetrics
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
    budget_2025: Optional[int] = Field(description="Their median trusted budget in 2025 $, given to the model as "
                                                   "the budget (revenue mode given); None: the model estimates it. "
                                                   "The score model never uses a budget")
    labels: RecipeLabels


class ModelScoreRange(BaseModel):
    low: float = Field(description="The score model's calibrated 10th percentile")
    mid: float = Field(description="Its median")
    high: float = Field(description="Its 90th percentile")


class ModelRevenueRange(BaseModel):
    low: float = Field(description="The revenue model's calibrated 10th percentile, 2025 $")
    mid: float = Field(description="Its median")
    high: float = Field(description="Its 90th percentile")
    mode: Literal["given", "estimated"] = Field(description="given: with the recipe's budget_2025; estimated: with "
                                                            "the budget model's estimate")


class ModelPrediction(BaseModel):
    score: ModelScoreRange
    revenue: ModelRevenueRange


class ModelFilm(BaseModel):
    recipe: RecipeOut
    prediction: ModelPrediction = Field(description="From one predict() call: the score and the revenue ranges")


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
