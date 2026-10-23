"""POST /predict/sweep: one film with one field tried at several values (the release-month sweep).

The frontend sends the 12 months of the planned year; runtime and budget work the same way. The sweep
shares the predict endpoints' rate limit and counts as one request, and every point goes through the
prediction cache, so a second sweep of the same film costs nothing. A bad form or value gets the usual 422,
keyed "form.runtime" or "values.3".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.deps import get_predictions
from backend.app.routers.predict import ERRORS, rate_limited
from backend.app.schemas.form import SweepRequest
from backend.app.schemas.prediction import SweepResponse
from backend.app.services.prediction import PredictionService

router = APIRouter(tags=["predict"])


@router.post("/predict/sweep", response_model=SweepResponse, dependencies=[Depends(rate_limited)], responses=ERRORS,
             summary="Predict one film with one field (release month, runtime or budget) at 2-12 values")
def sweep(request: SweepRequest, service: PredictionService = Depends(get_predictions)) -> dict:
    return service.sweep(request.form.to_form(), request.field, request.values)
