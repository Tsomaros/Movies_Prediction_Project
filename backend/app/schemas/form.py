"""Request models for the prediction endpoints, mirroring the creator form in ml/features/contract.py.

    PredictForm      -> POST /predict: one creator form
    FormChanges      -> one compare variant: only the fields it changes (null clears an optional field)
    CompareRequest   -> POST /predict/compare: {base, variants (1-3)}

These models check the JSON shape (types, unknown fields) and document it in /docs and the OpenAPI
schema the frontend types are generated from. The rules (allowed values, limits, list sizes, known
themes) stay in ml.features.contract.validate, the one source of truth, which predict() runs; the
limits are copied into the schema only as documentation (`json_schema_extra`), never enforced twice.
Types are strict: "2026" is not a year and true is not an id.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from ml.features.contract import CERTIFICATIONS, FIELDS_BY_NAME, GENRES

MAX_VARIANTS = 3

Genre = Literal[GENRES]  # type: ignore[valid-type]
Certification = Literal[CERTIFICATIONS]  # type: ignore[valid-type]


class RefObject(BaseModel):
    """A person, company or franchise: an id from autocomplete, a typed name, or both."""

    model_config = ConfigDict(strict=True, extra="forbid")
    id: Optional[int] = None
    name: Optional[str] = None


Ref = Union[int, str, RefObject]  # an id, a name, or {id, name}


def _doc(name: str) -> dict[str, Any]:
    """Description and limits from the contract, for the schema only."""
    f = FIELDS_BY_NAME[name]
    extra = {k: v for k, v in (("minimum", f.min), ("maximum", f.max), ("minItems", f.min_items),
                               ("maxItems", f.max_items)) if v is not None}
    if f.kind == "text" and f.max is not None:
        extra = {"maxLength": int(f.max)}
    return {"description": f.help, "json_schema_extra": extra}


class FormFields(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    genres: Optional[list[Genre]] = Field(None, **_doc("genres"))
    release_year: Optional[int] = Field(None, **_doc("release_year"))
    release_month: Optional[int] = Field(None, **_doc("release_month"))
    runtime: Optional[int] = Field(None, **_doc("runtime"))
    language: Optional[str] = Field(None, **_doc("language"))
    certification: Optional[Certification] = Field(None, **_doc("certification"))
    director: Optional[Ref] = Field(None, **_doc("director"))
    actors: Optional[list[Ref]] = Field(None, **_doc("actors"))
    themes: Optional[list[str]] = Field(None, description="Story themes; the names come from GET /meta/options",
                                        json_schema_extra={"minItems": 1, "maxItems": 5})
    companies: Optional[Union[list[Ref], Ref]] = Field(None, **_doc("companies"))
    countries: Optional[Union[list[str], str]] = Field(None, **_doc("countries"))
    franchise: Optional[Ref] = Field(None, **_doc("franchise"))
    synopsis: Optional[str] = Field(None, **_doc("synopsis"))
    budget: Optional[float] = Field(None, **_doc("budget"))

    def to_form(self) -> dict[str, Any]:
        """The fields the client sent, as plain JSON values for contract.validate."""
        return self.model_dump(mode="json", exclude_unset=True)


REQUIRED = [f.name for f in FIELDS_BY_NAME.values() if f.required]


class PredictForm(FormFields):
    """A creator's planned film. Required: genres, release_year, release_month, runtime, language,
    certification, director, actors (5-10) and themes; the rest is optional. Leave budget out and it is
    estimated. A required field that is missing gets a readable "required" error from the contract."""

    model_config = ConfigDict(strict=True, extra="forbid", json_schema_extra={"required": REQUIRED})


class FormChanges(FormFields):
    """What one variant changes in the base form: only the fields listed; null clears an optional field
    (to_form keeps explicit nulls, so they reach the merge)."""


class CompareRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    base: PredictForm
    variants: list[FormChanges] = Field(..., min_length=1, max_length=MAX_VARIANTS,
                                        description=f"1 to {MAX_VARIANTS} variants of the base form")
