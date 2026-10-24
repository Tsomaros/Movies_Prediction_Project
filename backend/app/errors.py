"""One error shape for every 422, whether the JSON shape or the form's rules are wrong.

    install(app)  -> handlers for RequestValidationError (Pydantic) and InvalidForm (ml.features.contract)

Every 422 body is {"detail": "Some fields need fixing", "errors": {field: message}}, with the field as a
dotted path: "runtime" for /predict, "base.runtime" or "variants.1.budget" for /predict/compare,
"form.runtime" or "values.3" for /predict/sweep, and
"q" or "page" for query parameters. The contract's rules apply to the /predict endpoints only; the
accounts endpoints get Pydantic's messages ("body", "rating", "watched_on").
A user database that can't be reached (Neon waking up too slowly, or down) answers 503, not 500. A shape error also lists every rule problem the contract finds in the
same body, with the contract's message where it has one, so a wrong type reads the same as a wrong value
("must be a number", "unknown field", "required") and one response names everything to fix.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import OperationalError
from psycopg_pool import PoolTimeout

from backend.app.schemas.form import MAX_SWEEP, MAX_VARIANTS, MIN_SWEEP
from backend.app.services.prediction import merge
from backend.app.settings import API_PREFIX
from ml.features.contract import FIELDS_BY_NAME, validate
from ml.predict import InvalidForm

DETAIL = "Some fields need fixing"
PYDANTIC_WORDS = {"missing": "required", "extra_forbidden": "unknown field"}


def unprocessable(errors: dict[str, str]) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": DETAIL, "errors": errors})


def _contract_errors(body: Any) -> dict[str, str]:
    """The contract's messages for every form in a request body, keyed like the API's paths."""
    if not isinstance(body, dict):
        return {}
    if "form" in body:  # a sweep: the form, plus each value checked as the swept field
        form = body["form"] if isinstance(body["form"], dict) else {}
        out = {f"form.{k}": v for k, v in validate(form)[1].items()}
        field, values = body.get("field"), body.get("values")
        if isinstance(field, str) and field in FIELDS_BY_NAME and isinstance(values, list):
            for i, value in enumerate(values):
                problem = validate({field: value})[1].get(field)
                if problem:
                    out[f"values.{i}"] = problem
        return out
    forms: dict[str, Any] = {}
    if "base" in body or "variants" in body:  # a compare request
        base = body.get("base") if isinstance(body.get("base"), dict) else {}
        forms["base."] = base
        for i, changes in enumerate(body.get("variants") or []):
            if isinstance(changes, dict):
                forms[f"variants.{i}."] = merge(base, changes)
    else:
        forms[""] = body
    out = {}
    for prefix, form in forms.items():
        _, errors = validate(form)  # themes are checked later by the service, with the real names
        out.update({f"{prefix}{k}": v for k, v in errors.items()})
    return out


def _path(loc: tuple[Any, ...]) -> str:
    """("body", "variants", 1, "actors", 2, "int") -> "variants.1.actors": stop at the form field."""
    parts = [str(p) for p in loc[1:]] if loc and loc[0] in ("body", "query", "path") else [str(p) for p in loc]
    out = []
    for p in parts:
        out.append(p)
        if p in FIELDS_BY_NAME:
            break
    return ".".join(out) or "body"


def _pydantic_message(error: dict[str, Any]) -> str:
    if error["type"] in PYDANTIC_WORDS:
        return PYDANTIC_WORDS[error["type"]]
    if error["type"] in ("too_short", "too_long") and tuple(error["loc"])[-1:] == ("variants",):
        return f"needs 1 to {MAX_VARIANTS} variants"
    if error["type"] in ("too_short", "too_long") and tuple(error["loc"])[-1:] == ("values",):
        return f"needs {MIN_SWEEP} to {MAX_SWEEP} values"
    msg = error["msg"]
    return msg[0].lower() + msg[1:]


def install(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def shape_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # every rule problem, not only the fields with a wrong shape
        errors = _contract_errors(exc.body) if request.url.path.startswith(f"{API_PREFIX}/predict") else {}
        for error in exc.errors():
            errors.setdefault(_path(tuple(error["loc"])), _pydantic_message(error))
        return unprocessable(errors)

    @app.exception_handler(InvalidForm)
    async def rule_error(request: Request, exc: InvalidForm) -> JSONResponse:
        return unprocessable(exc.errors)

    @app.exception_handler(OperationalError)
    @app.exception_handler(PoolTimeout)
    async def userdb_down(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "The accounts database isn't answering. Please try again "
                                                                "in a few seconds."}, headers={"Retry-After": "5"})
