"""Request dependencies: the read-only database connection and the objects loaded at startup.

    connect_read_only(path)   -> a sqlite3 connection that can't write (mode=ro); a missing file is an error
    get_db(request)           -> one connection per request, closed after it (use with Depends)
    get_predictor(request)    -> the Predictor loaded once by the lifespan hook
    get_lookups(request)      -> the autocomplete indexes built once by the lifespan hook
    get_predictions(request)  -> the PredictionService (cache + compare) around the Predictor

Endpoints are plain `def` functions, so FastAPI runs them in its thread pool; the connection is made in
one thread and used in another, hence check_same_thread=False (each connection serves one request only).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator

from fastapi import Request

from backend.app.services.lookups import Lookups
from backend.app.services.prediction import PredictionService
from ml.predict import Predictor


def connect_read_only(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    con = connect_read_only(request.app.state.settings.db_path)
    try:
        yield con
    finally:
        con.close()


def get_predictor(request: Request) -> Predictor:
    return request.app.state.predictor


def get_lookups(request: Request) -> Lookups:
    return request.app.state.lookups


def get_predictions(request: Request) -> PredictionService:
    return request.app.state.predictions
