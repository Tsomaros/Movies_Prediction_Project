"""Error reports to Sentry (Day 15): unhandled errors only, never personal data.

    start_sentry(dsn, release=None, transport=None)
                -> sentry_sdk.init with FastAPI's integration (automatic once fastapi is installed); called by
                   create_app only when SENTRY_DSN is set. transport is for tests (events kept in memory)

No tracing and no profiling (traces_sample_rate None: nothing is timed or sent per request), no request bodies,
cookies or IPs (Sentry's default leaves personal data out, and scrub also drops the cookie, auth and
forwarded-for headers), and no local variables in the stack frames (the ASGI scope holds every header), so
the mp_session token and creator forms never leave the server. 4xx answers are not errors and aren't sent.
"""

from __future__ import annotations

from typing import Any

import sentry_sdk

DROPPED_HEADERS = {"cookie", "set-cookie", "authorization", "x-forwarded-for"}


def scrub(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    request["headers"] = {k: v for k, v in headers.items() if k.lower() not in DROPPED_HEADERS}
    request.pop("cookies", None)
    request.pop("data", None)
    return event


def start_sentry(dsn: str, release: str | None = None, transport: Any = None) -> None:
    sentry_sdk.init(dsn=dsn, release=release, traces_sample_rate=None, include_local_variables=False,
                    max_request_body_size="never", before_send=scrub, transport=transport)
