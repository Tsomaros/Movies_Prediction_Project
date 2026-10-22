"""Response models for the form-support endpoints.

    Match        -> one autocomplete result (people, companies, collections)
    Options      -> GET /meta/options: every dropdown value and limit in one call
    Health       -> GET /health
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class Match(BaseModel):
    id: int
    name: str
    n_films: int = Field(description="Films in our data in this role (directed, acted in, produced, in the franchise)")


class CodeCount(BaseModel):
    code: str
    films: int


class Options(BaseModel):
    fields: list[dict[str, Any]] = Field(description="Every form field from the contract, themes filled in")
    genres: list[str]
    certifications: list[str]
    themes: list[str]
    languages: list[CodeCount] = Field(description="The most common original languages, ISO 639-1 codes")
    countries: list[CodeCount] = Field(description="The most common production countries, ISO 3166-1 codes")
    release_years: list[int] = Field(description="Suggested release years: this year to 4 years ahead")
    months: list[int]


class Database(BaseModel):
    built_at: Optional[str]
    films: int


class Health(BaseModel):
    status: str
    api_version: str
    model_version: str
    models: dict[str, str] = Field(description="What each model was trained on")
    database: Database
    started_at: str
    uptime_seconds: float
    load_seconds: float
    prediction_cache: dict[str, int]
