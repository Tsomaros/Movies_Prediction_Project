"""The FastAPI app: one router file per resource, all under /api/v1, with docs at /docs.

    create_app(settings=None, predictor=None, lookups=None)
                -> a new app; tests pass a small Predictor (and settings pointing at a small database), so
                   the real models are never loaded
    app         -> the app uvicorn serves: uv run uvicorn backend.app.main:app

The lifespan hook runs once at startup and keeps on app.state:
- predictor: the app's models, feature context and comparables index, after the manifest check (about 11-14 s);
- lookups:   the autocomplete indexes (about 2-3 s, about 33 MB);
- career, career_models: the career forecast's settings (CAREER_FILE, loaded first: a missing file stops the
  start) and the cache of /career/model answers (Day 14.8);
- predictions, rate_limiter: the prediction cache (CACHE_SIZE entries) and the per-IP limit (RATE_LIMIT a minute);
- started:   the time it finished, plus load_seconds, for /health;
- userdb, demo_seed, limiters: the user-database pool (None without USER_DATABASE_URL: /auth and /me then
  answer 503), the demo account's starting set and the login/demo/write limits (Day 14) and the
  "Surprise me" limit (Day 14.5).
app.state.clock gives the current UTC time to the accounts side (tests freeze it).
Then memory freed while loading is handed back to the system (release_free_memory, Linux only).
The database itself is never held open: every request gets its own read-only connection (deps.get_db).
A new endpoint is a new module in backend/app/routers/ with a `router`, added to ROUTERS below.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager, closing
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app import errors
from backend.app.deps import connect_read_only
from backend.app.routers import (auth, career, collections, companies, health, meta, model_card, movies, my_movies,
                                 notes, people, predict, random, sweep)
from backend.app.services.career_forecast import load_career_artifact
from backend.app.services.career_model import CareerModelCache
from backend.app.services.lookups import Lookups
from backend.app.services.prediction import PredictionService
from backend.app.services.ratelimit import RateLimiter
from backend.app.settings import API_PREFIX, Settings
from backend.app.userdb.pool import make_pool
from backend.app.userdb.seed import load_seed
from ml.predict import Predictor

log = logging.getLogger("uvicorn.error")

ROUTERS = (predict, sweep, movies, people, career, companies, collections, meta, model_card, health, auth, my_movies,
           notes, random)
LIMITS = {"login": 5, "demo": 10, "write": 30, "random": 60}  # a minute: writes per user, the others per client IP
DESCRIPTION = (
    "Budget, revenue and audience-score ranges for a planned film, with the drivers behind them and "
    "comparable past films, plus search over the 79,199 films in our TMDB data. This product uses the "
    "TMDB API but is not endorsed or certified by TMDB."
)


def release_free_memory() -> bool:
    """Hand memory freed during loading back to the system (glibc's malloc_trim; Linux only, else a no-op).

    In Docker this gave back about 130 MB after startup on Day 9. Returns whether it ran."""
    if not sys.platform.startswith("linux"):
        return False
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):  # not glibc (e.g. musl): nothing to trim
        return False
    return True


def create_app(settings: Settings | None = None, predictor: Predictor | None = None,
               lookups: Lookups | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        start = time.perf_counter()
        app.state.career = load_career_artifact(settings.career_file)  # a few KB; fails before the slow loads
        app.state.career_models = CareerModelCache()
        app.state.predictor = predictor or Predictor.load(settings.models_dir, settings.db_path,
                                                          context_file=settings.context_file)
        if lookups is None:
            with closing(connect_read_only(settings.db_path)) as con:
                app.state.lookups = Lookups.from_db(con)
        else:
            app.state.lookups = lookups
        app.state.predictions = PredictionService(app.state.predictor, settings.cache_size)
        app.state.rate_limiter = RateLimiter(settings.rate_limit)
        app.state.limiters = {name: RateLimiter(n) for name, n in LIMITS.items()}
        app.state.userdb = make_pool(settings.user_database_url) if settings.user_database_url else None
        app.state.demo_seed = load_seed()
        release_free_memory()
        app.state.load_seconds = round(time.perf_counter() - start, 1)
        app.state.started = time.time()
        log.info("loaded the models and lookups in %.1f s (model version %s)", app.state.load_seconds,
                 getattr(app.state.predictor, "manifest", {}).get("version", "?"))
        yield
        if app.state.userdb is not None:
            app.state.userdb.close()

    app = FastAPI(title="Movie Prediction API", version="1.0.0", description=DESCRIPTION, lifespan=lifespan)
    app.state.settings = settings
    app.state.clock = lambda: datetime.now(timezone.utc)
    # The app and the API share one origin (Vite's proxy, nginx), so the cookie needs no CORS credentials
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["*"])
    errors.install(app)
    for module in ROUTERS:
        app.include_router(module.router, prefix=API_PREFIX)
    return app


app = create_app()
