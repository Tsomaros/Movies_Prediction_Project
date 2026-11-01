"""A Server-Timing header on every response, and a warning for slow requests (V1.5).

    ServerTimingMiddleware(app)  -> pure ASGI middleware: `Server-Timing: app;dur=<ms>` and a log line when
                                    a request took more than SLOW_MS
    SLOW_MS                      -> 500

The time runs from the request reaching the middleware to the response headers being ready, which is
when the header has to be written (so streamed bodies are not counted). It adds no thread hops, unlike
BaseHTTPMiddleware. Only http requests are touched; lifespan and websocket scopes pass through.
"""

from __future__ import annotations

import logging
import time

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("uvicorn.error")

SLOW_MS = 500.0


class ServerTimingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()

        async def send_with_timing(message: Message) -> None:
            if message["type"] == "http.response.start":
                ms = (time.perf_counter() - start) * 1000
                MutableHeaders(scope=message)["Server-Timing"] = f"app;dur={ms:.1f}"
                if ms > SLOW_MS:
                    log.warning("slow request: %s %s took %.0f ms (status %s)", scope["method"], scope["path"], ms,
                                message["status"])
            await send(message)

        await self.app(scope, receive, send_with_timing)
