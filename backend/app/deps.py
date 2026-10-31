"""Request dependencies: the read-only database connection and the objects loaded at startup.

    connect_read_only(path)   -> a sqlite3 connection that can't write (mode=ro); a missing file is an error
    get_db(request)           -> one connection per request, closed after it (use with Depends)
    get_predictor(request)    -> the Predictor loaded once by the lifespan hook
    get_lookups(request)      -> the autocomplete indexes built once by the lifespan hook
    get_predictions(request)  -> the PredictionService (cache + compare) around the Predictor

The accounts side (Day 14):
    get_userdb(request)       -> a connection from the user-database pool; 503 when accounts are off
    now(request)              -> the current UTC time from app.state.clock (tests freeze it)
    client_ip(request)        -> the visitor's address for the per-IP limits: the CLIENT_IP_HEADER header when that
                                 setting names one and the request has it (on Render, a header its edge sets;
                                 X-Forwarded-For can't be used there: a visitor's own value reaches the app as the
                                 client), else the connection's address
    optional_user / current_user
                              -> the logged-in user ({id, username, is_demo}) from the mp_session cookie, or
                                 None / 401
    maybe_user                -> the logged-in user, or None when logged out or when accounts are off (no 503)
    same_origin_write         -> 403 for a write whose Origin isn't the API's own or one of CORS_ORIGINS,
                                 415 for a body that isn't JSON (with SameSite=Lax, this stops cross-site writes)
    limit(name, message)      -> a dependency that counts one request per client IP on app.state.limiters[name]
    write_limited             -> 30 writes a minute per user, on app.state.limiters["write"]
    no_store                  -> Cache-Control: private, no-store (every /auth and /me answer)

Endpoints are plain `def` functions, so FastAPI runs them in its thread pool; the connection is made in
one thread and used in another, hence check_same_thread=False (each connection serves one request only).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

import psycopg
from fastapi import Depends, HTTPException, Request, Response

from backend.app.services.platform.auth import token_hash
from backend.app.services.search.lookups import Lookups
from backend.app.services.prediction import PredictionService
from backend.app.userdb import repo as userdb
from ml.predict import Predictor

COOKIE = "mp_session"
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


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


def get_userdb(request: Request) -> Iterator[psycopg.Connection]:
    pool = request.app.state.userdb
    if pool is None:
        raise HTTPException(status_code=503, detail="Accounts are not set up on this server")
    with pool.connection() as conn:
        yield conn


def now(request: Request) -> datetime:
    return request.app.state.clock()


def client_ip(request: Request) -> str:
    header = request.app.state.settings.client_ip_header
    value = request.headers.get(header, "").split(",")[0].strip() if header else ""
    return value or (request.client.host if request.client else "unknown")


def optional_user(request: Request, conn: psycopg.Connection = Depends(get_userdb)) -> Optional[dict[str, Any]]:
    token = request.cookies.get(COOKIE)
    return userdb.session_user(conn, token_hash(token), now(request)) if token else None


def maybe_user(request: Request) -> Optional[dict[str, Any]]:
    token, pool = request.cookies.get(COOKIE), request.app.state.userdb
    if token is None or pool is None:
        return None
    with pool.connection() as conn:
        return userdb.session_user(conn, token_hash(token), now(request))


def current_user(user: Optional[dict[str, Any]] = Depends(optional_user)) -> dict[str, Any]:
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in first")
    return user


def same_origin_write(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    origin = request.headers.get("origin")
    own = f"{request.url.scheme}://{request.headers.get('host', '')}"
    if origin is None or (origin != own and origin not in request.app.state.settings.cors_origins):
        raise HTTPException(status_code=403, detail="This request must come from the app itself")
    has_body = request.headers.get("content-length", "0") != "0" or "transfer-encoding" in request.headers
    if has_body and not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status_code=415, detail="Send the request body as JSON")


def _too_many(wait: int | None, message: str) -> None:
    if wait is not None:
        raise HTTPException(status_code=429, detail=message, headers={"Retry-After": str(wait)})


def limit(name: str, message: str) -> Callable[[Request], None]:
    def limited(request: Request) -> None:
        _too_many(request.app.state.limiters[name].hit(client_ip(request)), message)
    return limited


def write_limited(request: Request, user: dict[str, Any] = Depends(current_user)) -> None:
    _too_many(request.app.state.limiters["write"].hit(f"user:{user['id']}"),
              "Too many changes in a minute. Please wait a moment and try again.")


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
