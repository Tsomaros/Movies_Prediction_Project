"""GET /health: is the API up, which models and database it serves, and how the prediction cache is doing.

Used by the Docker healthcheck and the smoke script (Day 9). It touches the database (a COUNT), so a
missing or unreadable database makes it fail instead of reporting "ok". Never cached.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response

from backend.app.deps import get_db
from backend.app.repo import meta as repo
from backend.app.schemas.lookup import Health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health, summary="Status, model version and database build")
def health(request: Request, response: Response, con: sqlite3.Connection = Depends(get_db)):
    state = request.app.state
    manifest = getattr(state.predictor, "manifest", {})
    cache = state.predictions
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "ok",
        "api_version": request.app.version,
        "model_version": manifest.get("version", "unknown"),
        "models": {t: m.get("trained_on", "") for t, m in manifest.get("models", {}).items()},
        "database": repo.build_info(con),
        "started_at": datetime.fromtimestamp(state.started, timezone.utc).isoformat(timespec="seconds"),
        "uptime_seconds": round(time.time() - state.started, 1),
        "load_seconds": state.load_seconds,
        "prediction_cache": {"size": len(cache), "max_size": cache.size, "hits": cache.hits, "misses": cache.misses},
    }
