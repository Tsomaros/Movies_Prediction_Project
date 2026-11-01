"""GET /health: is the API up, which models and database it serves, and how the prediction cache is doing.

Used by the Docker healthcheck, the smoke script (Day 9), an uptime monitor and the app's wake-up screen (V1.5), so it
is cheap: the build's numbers (`database`) are read once at startup (lifespan, `app.state.build_info`; the count leaves
out films the refresher adds, so it cannot change while the process runs) and a request only runs `SELECT 1` on its
read-only connection, so a missing or unreadable database still makes it fail instead of reporting "ok". Never cached.
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
    con.execute("SELECT 1").fetchone()
    if state.build_info is None:  # startup could not read it (it is cached here once it can)
        state.build_info = repo.build_info(con)
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "ok",
        "api_version": request.app.version,
        "model_version": manifest.get("version", "unknown"),
        "models": {t: m.get("trained_on", "") for t, m in manifest.get("models", {}).items()},
        "database": state.build_info,
        "started_at": datetime.fromtimestamp(state.started, timezone.utc).isoformat(timespec="seconds"),
        "uptime_seconds": round(time.time() - state.started, 1),
        "load_seconds": state.load_seconds,
        "prediction_cache": {"size": len(cache), "max_size": cache.size, "hits": cache.hits, "misses": cache.misses},
        "fresh": state.fresh.status() if hasattr(state, "fresh") else {"refreshed_at": None, "films": None},
    }
