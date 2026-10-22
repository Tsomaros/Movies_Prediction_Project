"""POST /predict and POST /predict/compare: a creator's form in, ranges, drivers, comparables and warnings out.

Both are plain `def` endpoints, so FastAPI runs them in its thread pool (a prediction takes about 150 ms
of CPU). Together they share one rate limit per client IP (RATE_LIMIT a minute, 429 with Retry-After).
A form that breaks the contract's rules gets a 422 with one message per field (backend/app/errors.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.deps import get_predictions
from backend.app.schemas.form import CompareRequest, PredictForm
from backend.app.schemas.prediction import CompareResponse, Prediction
from backend.app.services.prediction import PredictionService

router = APIRouter(tags=["predict"])
TOO_MANY = "Too many predictions from your address. Please try again in a minute."


def rate_limited(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    wait = request.app.state.rate_limiter.hit(client)
    if wait is not None:
        raise HTTPException(status_code=429, detail=TOO_MANY, headers={"Retry-After": str(wait)})


ERRORS = {422: {"description": 'Some fields need fixing: {"detail": ..., "errors": {field: message}}'},
          429: {"description": "Too many prediction requests from this address; see Retry-After"}}


@router.post("/predict", response_model=Prediction, dependencies=[Depends(rate_limited)], responses=ERRORS,
             summary="Predict budget, revenue and score ranges for a planned film")
def predict(form: PredictForm, service: PredictionService = Depends(get_predictions)) -> dict:
    out, cached = service.predict(form.to_form())
    return {**out, "cached": cached}


@router.post("/predict/compare", response_model=CompareResponse, dependencies=[Depends(rate_limited)],
             responses=ERRORS, summary="Predict a base form and up to 3 variants, with the differences")
def compare(request: CompareRequest, service: PredictionService = Depends(get_predictions)) -> dict:
    return service.compare(request.base.to_form(), [v.to_form() for v in request.variants])
