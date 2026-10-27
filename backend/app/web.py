"""The built React app, served by the API itself in production (Day 15: one container, one origin on Render).

    install(app, web_dir) -> gzip, two safety headers, and a last route that serves web_dir (the Vite `dist/`):
                             a file that exists is sent as it is, any other path gets index.html (client-side
                             routes such as /predict or /movies/603), and an unknown /api path stays a JSON 404

Caching as nginx did it before Day 15: Vite's hashed /assets/ for a year (immutable), everything else
`no-cache`, so a new build is picked up on the next visit. /docs and /openapi.json are FastAPI's own routes and match first.
Without WEB_DIR (tests, `make api`, the Vite dev server) nothing is installed.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.middleware.gzip import GZipMiddleware

YEAR = "public, max-age=31536000, immutable"
HEADERS = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "strict-origin-when-cross-origin"}
# Python 3.11 has no .webp type and the slim image no /etc/mime.types: the collages went out as octet-stream
mimetypes.add_type("image/webp", ".webp")


def install(app: FastAPI, web_dir: Path) -> None:
    root = web_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise ValueError(f"WEB_DIR {web_dir} has no index.html (build the app with `npm run build`)")

    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def safety_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        for name, value in HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def web(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            cache = YEAR if path.startswith("assets/") else "no-cache"
            return FileResponse(file, headers={"Cache-Control": cache})
        if path.startswith("assets/"):  # an old bundle name after a new build: a 404, not the app
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
