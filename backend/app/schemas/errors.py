"""Error response models, so the OpenAPI schema (and the frontend types generated from it) shows the real bodies.

    FieldErrors  -> every 422 (backend/app/errors.py): {"detail": "Some fields need fixing", "errors": {path: msg}}
    Message      -> 404 and 429: {"detail": "..."}
    VALIDATION   -> `responses=` for a router whose endpoints take a body or query parameters; declaring the 422
                    replaces FastAPI's default HTTPValidationError, which our handler never sends
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FieldErrors(BaseModel):
    detail: str = Field(description='Always "Some fields need fixing"')
    errors: dict[str, str] = Field(description='One message per field, keyed by its dotted path ("actors.2", '
                                               '"variants.1.budget", "q")')


class Message(BaseModel):
    detail: str


VALIDATION: dict[int | str, dict[str, Any]] = {
    422: {"model": FieldErrors, "description": "Some fields need fixing"},
}
