"""Response models for the prediction endpoints: the output of ml.predict.Predictor.predict, documented.

    Prediction       -> POST /predict
    CompareResponse  -> POST /predict/compare: the base, each variant and their differences

Money is in 2025 US dollars, scores on TMDB's 0-10 scale. Field names are the ones predict() returns, so
the API passes its output through unchanged and adds only `cached` and the comparables' poster URLs.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Target = Literal["budget", "revenue", "score"]


class Range(BaseModel):
    low: float
    middle: float
    high: float
    text: str = Field(description='The range as text, e.g. "$5.2M–$62M" or "6.2–7.6"')
    middle_text: str
    rough: bool = Field(description="A rough estimate: the range is unusually wide (never for score)")


class BudgetComparison(BaseModel):
    low: float
    middle: float
    high: float
    text: str = Field(description='"Similar films usually cost $X–Y"')
    budget: Optional[float] = None
    position: Optional[Literal["below", "at the low end", "within", "at the high end", "above"]] = None
    ratio: Optional[float] = Field(None, description="The given budget divided by the middle")
    sentence: Optional[str] = None


class BudgetRange(Range):
    given: Optional[float] = Field(description="The budget from the form, if any")
    comparison: BudgetComparison


class RevenueRange(Range):
    mode: Literal["given", "estimated"] = Field(description="Whether the budget came from the form or was estimated")
    budget_used: float


class ScoreRange(Range):
    note: str


class Driver(BaseModel):
    group: str
    label: str
    direction: Literal["up", "down"]
    strength: Literal["strong", "moderate", "slight"]
    estimated: bool = Field(description="The driver is the estimated budget (budget left out of the form)")
    value: Any = None
    text: str


class Drivers(BaseModel):
    up: list[Driver]
    down: list[Driver]


class TargetDrivers(BaseModel):
    budget: Drivers
    revenue: Drivers
    score: Drivers


class Poster(BaseModel):
    small: str
    large: str


class Comparable(BaseModel):
    id: int
    title: str
    year: int
    poster_path: Optional[str]
    poster: Optional[Poster]
    budget: Optional[float] = Field(description="2025 $, None when not reported")
    revenue: Optional[float]
    score: float
    similarity: float
    why: list[str] = Field(description='Up to 3 short reasons, strongest first, e.g. "Also Action, Drama", "Similar budget"')


class Warning(BaseModel):
    code: Literal["big_budget", "new_director", "new_actors", "no_country", "no_studio", "future_release"]
    text: str


class Prediction(BaseModel):
    model_version: str
    as_of: str = Field(description="The date the film is judged at: the 1st of its release month")
    budget: BudgetRange
    revenue: RevenueRange
    score: ScoreRange
    drivers: TargetDrivers
    comparables: list[Comparable]
    warnings: list[Warning]
    cached: bool = Field(description="Served from the prediction cache")


class Shift(BaseModel):
    ratio: Optional[float] = Field(None, description="Money: the variant's middle divided by the base's")
    points: Optional[float] = Field(None, description="Score: the variant's middle minus the base's")


class Differences(BaseModel):
    changed_fields: list[str]
    budget: Shift
    revenue: Shift
    score: Shift
    mode_changed: bool = Field(description="The revenue mode differs from the base's (a budget was added or removed)")


class Variant(BaseModel):
    prediction: Prediction
    differences: Differences


class CompareResponse(BaseModel):
    base: Prediction
    variants: list[Variant]
