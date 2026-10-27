# The app's one image (Day 15): FastAPI with the database and the app's models baked in, serving the built React
# app beside the API on one origin. The same image runs in docker compose and on Render.
#
#   uv run python scripts/slim_db.py                          # build/movies.db: data/movies.db minus training tables
#   uv run python -m ml.features.build prebuilt               # build/context.joblib: the track records, prebuilt
#   docker build -f backend/Dockerfile -t movie-prediction .  # (make docker-build does all three)
#
# Build context = the repository root; .dockerignore lets in only pyproject.toml, uv.lock, ml/, backend/, the
# frontend's sources and build/movies.db + build/context.joblib, and keeps out the <=2015 .joblib models, the
# full MiniLM, node_modules, caches and the rest.
# Build args (make deploy passes them): VITE_SENTRY_DSN, the frontend's Sentry project (public by design, it ends
# up in the bundle); APP_RELEASE, the git commit, Sentry's release on both sides.

# ---------------------------------------------------------------- web: the React app's production build
FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ARG VITE_SENTRY_DSN=""
ARG APP_RELEASE=""
RUN VITE_SENTRY_DSN="$VITE_SENTRY_DSN" VITE_APP_RELEASE="$APP_RELEASE" npm run build

# ---------------------------------------------------------------- builder: the locked runtime dependencies
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Runtime only: no dev group (pytest, jupyter) and no ml group (optuna, matplotlib)
RUN uv sync --frozen --no-default-groups --no-install-project

# ---------------------------------------------------------------- runtime
FROM python:3.11-slim
# LightGBM needs the OpenMP runtime, which the slim image doesn't have
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY ml/ ml/
COPY backend/ backend/
COPY build/movies.db data/movies.db
COPY build/context.joblib data/context.joblib
COPY --from=web /web/dist web/
ARG APP_RELEASE=""

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MOVIES_DB=/app/data/movies.db \
    MODELS_DIR=/app/ml/artifacts/final \
    CONTEXT_FILE=/app/data/context.joblib \
    WEB_DIR=/app/web \
    APP_RELEASE=$APP_RELEASE \
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=1 \
    PORT=8000 \
    CORS_ORIGINS=http://localhost:5173 \
    FORWARDED_ALLOW_IPS=127.0.0.1
USER app
EXPOSE 8000

# Startup takes about 10-15 s (models, feature context, lookups), hence the start period
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import os, sys, urllib.request; sys.exit(urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/v1/health', timeout=4).status != 200)"]

# One worker: each worker loads every model, and the prediction cache and rate limiter live in its memory.
# uvicorn reads X-Forwarded-For/-Proto only from FORWARDED_ALLOW_IPS (compose: nginx; Render: its proxy), so
# request.client.host is the visitor and https sets the Secure cookie. USER_DATABASE_URL, SENTRY_DSN and
# CORS_ORIGINS come from the host. PORT: Render may set its own; the shell form lets uvicorn read it.
CMD exec uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT" --workers 1
