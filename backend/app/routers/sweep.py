"""POST /predict/sweep: one film with one field tried at several values (the release-month sweep).

The frontend sends the 12 months of the planned year; runtime and budget work the same way. The sweep
shares the predict endpoints' rate limit and counts as one request. Only the ranges are computed (no drivers
or comparables), the uncached points in one call per model, and they are cached as ranges-only entries, so a
second sweep of the same film costs almost nothing (X-Cache: hit). A bad form or value gets the usual 422,
keyed "form.runtime" or "values.3".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from backend.app.deps import get_predictions
from backend.app.routers.predict import ERRORS, rate_limited, set_cache_header
from backend.app.schemas.form import SweepRequest
from backend.app.schemas.prediction import SweepResponse
from backend.app.services.prediction import PredictionService

router = APIRouter(tags=["predict"])


@router.post("/predict/sweep", response_model=SweepResponse, dependencies=[Depends(rate_limited)], responses=ERRORS,
             summary="Predict one film with one field (release month, runtime or budget) at 2-12 values")
def sweep(request: SweepRequest, response: Response, service: PredictionService = Depends(get_predictions)) -> dict:
    out, cached = service.sweep(request.form.to_form(), request.field, request.values)
    set_cache_header(response, cached)
    return out
