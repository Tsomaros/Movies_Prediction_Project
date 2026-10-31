"""POST /auth/login, POST /auth/demo, POST /auth/logout and GET /auth/me: the demo account's sessions (Day 14).

A login stores the SHA-256 of a random token in the sessions table and the token in the mp_session cookie
(httpOnly, SameSite=Lax, path /, Secure on https, a fixed 7 days). Logout deletes the row, so an old cookie
stops working at once. GET /auth/me answers {"user": null} when logged out, not a 401, so the header can
ask quietly. The demo button never hashes a password; the first demo login after midnight Athens time
restores the starting set (userdb/seed.reset_if_due). A wrong username or password always gets the same
message. Limits per client IP: password login 5 a minute, demo login 10 a minute.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.app.deps import (COOKIE, get_userdb, limit, no_store, now, optional_user, same_origin_write)
from backend.app.schemas.accounts import LoginRequest, Me
from backend.app.schemas.errors import VALIDATION, Message
from backend.app.services.platform.auth import new_token, today_athens, token_hash, verify_password
from backend.app.userdb import repo
from backend.app.userdb.seed import reset_if_due

router = APIRouter(tags=["auth"], dependencies=[Depends(no_store), Depends(same_origin_write)])
SESSION_DAYS = 7
WRONG = "Wrong username or password"
ERRORS = {403: {"model": Message, "description": "Not sent from the app"},
          429: {"model": Message, "description": "Too many attempts from this address; see Retry-After"},
          503: {"model": Message, "description": "Accounts are off or the database is unreachable"}}


def _public(user: dict[str, Any]) -> dict[str, Any]:
    return {"id": user["id"], "username": user["username"], "is_demo": user["is_demo"]}


def _start_session(request: Request, response: Response, conn: psycopg.Connection, user: dict[str, Any]) -> dict:
    token = new_token()
    repo.create_session(conn, user["id"], token_hash(token), now(request) + timedelta(days=SESSION_DAYS))
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 24 * 3600, path="/", httponly=True, samesite="lax",
                        secure=request.url.scheme == "https")
    return {"user": _public(user)}


@router.post("/auth/login", response_model=Me, summary="Log in with a username and password",
             dependencies=[Depends(limit("login", "Too many login attempts from your address. Please try again in a minute."))],
             responses={**VALIDATION, **ERRORS, 401: {"model": Message, "description": WRONG}})
def login(body: LoginRequest, request: Request, response: Response, conn: psycopg.Connection = Depends(get_userdb)):
    user = repo.user_by_name(conn, body.username)
    if not verify_password(user["password_hash"] if user else None, body.password):
        raise HTTPException(status_code=401, detail=WRONG)
    return _start_session(request, response, conn, user)


@router.post("/auth/demo", response_model=Me, summary="Log in to the shared demo account with one click",
             dependencies=[Depends(limit("demo", "Too many demo logins from your address. Please try again in a minute."))],
             responses=ERRORS)
def demo(request: Request, response: Response, conn: psycopg.Connection = Depends(get_userdb)):
    user = repo.demo_user(conn)
    if user is None:
        raise HTTPException(status_code=503, detail="The demo account isn't set up yet")
    reset_if_due(conn, user["id"], request.app.state.demo_seed, today_athens(now(request)), now(request))
    return _start_session(request, response, conn, user)


@router.post("/auth/logout", status_code=204, summary="Log out: the session ends for good", responses=ERRORS)
def logout(request: Request, response: Response, conn: psycopg.Connection = Depends(get_userdb)) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        repo.delete_session(conn, token_hash(token))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax", secure=request.url.scheme == "https")


@router.get("/auth/me", response_model=Me, summary="Who is logged in ({\"user\": null} when nobody)", responses=ERRORS)
def me(user: Optional[dict[str, Any]] = Depends(optional_user)):
    return {"user": _public(user) if user else None}
