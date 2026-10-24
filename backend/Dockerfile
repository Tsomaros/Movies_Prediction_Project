# The backend image: the FastAPI app with the database and the app's models baked in.
#
#   uv run python scripts/slim_db.py                          # build/movies.db: data/movies.db minus training tables
#   uv run python -m ml.features.build prebuilt               # build/context.joblib: the track records, prebuilt
#   docker build -f backend/Dockerfile -t movie-prediction-api .   # (make docker-build does all three)
#
# Build context = the repository root; .dockerignore lets in only pyproject.toml, uv.lock, ml/, backend/ and
# build/movies.db + build/context.joblib, and keeps out the <=2015 .joblib models, the full MiniLM, caches and the rest.

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

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MOVIES_DB=/app/data/movies.db \
    MODELS_DIR=/app/ml/artifacts/final \
    CONTEXT_FILE=/app/data/context.joblib \
    MALLOC_ARENA_MAX=2 \
    CORS_ORIGINS=http://localhost:5173     FORWARDED_ALLOW_IPS=127.0.0.1
USER app
EXPOSE 8000

# Startup takes about 10-15 s (models, feature context, lookups), hence the start period
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status != 200)"]

# One worker: each worker loads every model, and the prediction cache and rate limiter live in its memory.
# uvicorn reads X-Forwarded-For/-Proto only from FORWARDED_ALLOW_IPS (compose: nginx; Render: its proxy), so
# request.client.host is the visitor and https sets the Secure cookie. USER_DATABASE_URL comes from the host.
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
