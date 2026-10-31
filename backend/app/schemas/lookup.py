"""Response models for the form-support endpoints.

    Match        -> one autocomplete result (people, companies, collections)
    FieldSpec    -> one form field from contract.describe(): its kind, limits and choices
    Options      -> GET /meta/options: every dropdown value and limit in one call
    Health       -> GET /health
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Match(BaseModel):
    id: int
    name: str
    n_films: int = Field(description="Films in our data in this role (directed, acted in, produced, in the franchise)")


class FieldSpec(BaseModel):
    """A creator-form field as ml.features.contract.Field describes it (limits that don't apply are left out)."""

    name: str
    kind: Literal["int", "float", "text", "choice", "choices", "code", "codes", "ref", "refs"]
    required: bool
    help: str
    min: Optional[float] = Field(None, description="int / float: smallest value; text: shortest length")
    max: Optional[float] = Field(None, description="int / float: largest value; text: longest length")
    choices: Optional[list[str]] = Field(None, description="choice / choices: the allowed values")
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    pattern: Optional[str] = Field(None, description="code / codes: the regular expression a code must match")


class CodeCount(BaseModel):
    code: str
    films: int


class Options(BaseModel):
    fields: list[FieldSpec] = Field(description="Every form field from the contract, themes filled in")
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


class Fresh(BaseModel):
    refreshed_at: Optional[str] = Field(description="When the new and upcoming films were last merged into the database; None before the first refresh")
    films: Optional[int]


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
    fresh: Fresh = Field(description="The small database of new and upcoming films (V1.2)")
