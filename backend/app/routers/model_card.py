"""GET /model-card: how accurate the served models are, for the results page's "How accurate is this?" panel.

The numbers come from MODELS_DIR/model_card.json (written by `uv run python -m ml.eval.model_card` from the
Day 6 test and the 2026 holdout), plus the database's size and years. The card must belong to the models
being served: a card written for another model version is a 503, never quietly shown. Read once per process
and cached for an hour by clients, like /meta/options.
"""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.app.deps import get_db
from backend.app.repo import meta as repo
from backend.app.schemas.errors import Message
from backend.app.schemas.model_card import ModelCard
from ml.eval.model_card import CARD_FILE

router = APIRouter(tags=["model card"])
STALE = "The model card doesn't match the models being served; rerun `uv run python -m ml.eval.model_card`."


@router.get("/model-card", response_model=ModelCard, response_model_exclude_none=True,
            responses={503: {"model": Message, "description": "The model card is missing or out of date"}},
            summary="Test results, data range and version of the served models")
def model_card(request: Request, response: Response, con: sqlite3.Connection = Depends(get_db)):
    state = request.app.state
    if getattr(state, "model_card", None) is None:
        version = getattr(state.predictor, "manifest", {}).get("version")
        try:
            card = json.loads((state.settings.models_dir / CARD_FILE).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail=STALE)
        if card["model_version"] != version:
            raise HTTPException(status_code=503, detail=STALE)
        first, last = repo.year_range(con)
        state.model_card = {**card, "data": {**repo.build_info(con), "first_year": first, "last_year": last}}
    response.headers["Cache-Control"] = "public, max-age=3600"
    return state.model_card
