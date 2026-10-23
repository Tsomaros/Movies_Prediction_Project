"""Response model for GET /model-card: the app's accuracy numbers, as ml.eval.model_card writes them.

    ModelCard  -> the models' version and training data, the database, the 2019+ test and the 2026 holdout

Money metrics are on the log scale (mae_log; typical_factor = exp(mae_log)), within_2x and coverage are
shares (0-1), a money range's width is high / low; score metrics and widths are in points.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Metrics(BaseModel):
    mae_log: Optional[float] = Field(None, description="Money: mean absolute error of the middle, log scale")
    typical_factor: Optional[float] = Field(None, description="Money: exp(mae_log), the middle is typically off by this factor")
    within_2x: Optional[float] = Field(None, description="Money: share of films whose middle was within 2x of the real figure")
    mae: Optional[float] = Field(None, description="Score: mean absolute error of the middle, in points")
    coverage: float = Field(description="Share of films whose real figure fell inside the 10-90 range")
    width: float = Field(description="Median range width: high / low for money, high - low in points for score")


class Baseline(Metrics):
    name: str


class TargetAccuracy(BaseModel):
    films: int
    model: Metrics
    baseline: Baseline = Field(description="B2, the strongest simple rule, on the same films")


class Targets(BaseModel):
    revenue: TargetAccuracy = Field(description="Revenue with the budget given")
    revenue_estimated: TargetAccuracy = Field(description="Revenue with the budget estimated")
    budget: TargetAccuracy
    score: TargetAccuracy


class Evaluation(BaseModel):
    about: str
    years: str
    run_at: str
    trained_on: Optional[str] = None
    released_by: Optional[str] = Field(None, description="Holdout: films released up to this date count for revenue and score")
    targets: Targets


class Training(BaseModel):
    years: str
    films: dict[str, int] = Field(description="Films each model was trained on")


class Data(BaseModel):
    films: int
    first_year: int
    last_year: int
    built_at: Optional[str]


class ModelCard(BaseModel):
    model_version: str = Field(description="The version of the models this API serves")
    coverage_target: float = Field(description="What share of real figures the ranges are calibrated to cover")
    training: Training
    data: Data
    test: Evaluation = Field(description="The one-time test on 2019+ films (Day 6)")
    holdout: Evaluation = Field(description="The app's own models on films released in 2026")
    sources: dict[str, str] = Field(description="The reports in the repository the numbers come from")
