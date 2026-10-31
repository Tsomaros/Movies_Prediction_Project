"""Passwords, session tokens and the demo account's clock.

    hash_password(password)          -> an argon2id hash at OWASP's minimum (19 MiB, 2 passes, 1 lane)
    verify_password(hash, password)  -> True or False (never raises); a None hash still costs one verify,
                                        so an unknown username takes as long as a wrong password
    new_token()                      -> a random 32-byte token, URL-safe text, for the session cookie
    token_hash(token)                -> its SHA-256, the only form stored in the sessions table
    today_athens(now=None)           -> the date in Athens, which decides when the nightly demo reset is due

argon2's default of 64 MiB per hash is too much for a 512 MB server; the demo button never hashes, so the
common path costs nothing. A plain SHA-256 is enough for the token: it is random, not a password.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Optional
from zoneinfo import ZoneInfo

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

HASHER = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
ATHENS = ZoneInfo("Europe/Athens")


def hash_password(password: str) -> str:
    return HASHER.hash(password)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return HASHER.hash(secrets.token_urlsafe(16))


def verify_password(password_hash: Optional[str], password: str) -> bool:
    try:
        return HASHER.verify(password_hash or _dummy_hash(), password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def today_athens(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(ATHENS).date()
