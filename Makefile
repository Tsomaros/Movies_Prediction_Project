.PHONY: setup model data db people people-db features career tune train evaluate test test-fast test-pg coverage api userdb docker-build docker-run deploy smoke web-setup web web-test gen-api collages

# Create .venv and install the locked dependencies (then `make model` for the text model)
setup:
	uv sync

# Download the pinned MiniLM ONNX model and tokenizer into ml/artifacts/minilm/ (about 90 MB, once)
model:
	uv run python -m ml.features.text

# Pull films from TMDB into data/raw/ (resumable), then build the database and the features table
data:
	uv run python -m ml.data.pull
	uv run python -m ml.data.build_db
	uv run python -m ml.features.build

# Rebuild data/movies.db from the raw pull only (this drops the features table: run `make features` after)
db:
	uv run python -m ml.data.build_db

# TMDB person details for the person pages: cast members with 2+ films (Day 14.6) and every crew member (Day 14.7)
# -> data/raw/tmdb_people.jsonl (resumable, about 3 h 20 min from scratch), then person_details in data/movies.db (rerunnable; `make db` loads it too)
people:
	uv run python -m ml.data.people pull

people-db:
	uv run python -m ml.data.people load

# Build the features table in data/movies.db (needs `make model`; new overviews are embedded, the rest is cached)
features:
	uv run python -m ml.features.build

# The career forecast's backtest (Day 14.8): h, k, q per role, tuned before 2019, tested 2019+ (a few seconds)
career: ml/artifacts/career_forecast.json

ml/artifacts/career_forecast.json: data/movies.db
	uv run python -m ml.career.backtest

# Tune the LightGBM settings on backtest folds 1-2 (15 minutes per target); writes ml/artifacts/*_params.json
tune:
	uv run python -m ml.models.tune

# Calibrate the ranges on folds 1-2, then fit both models on train and save them to ml/artifacts/
train:
	uv run python -m ml.models.calibrate
	uv run python -m ml.models.train

# Evaluate every model on validation, breakdowns and the rolling backtest; writes reports/ (test split untouched)
evaluate:
	uv run python -m ml.eval.evaluate

# Run the offline test suite (about 2 min; the real-data tests need data/movies.db and the app's models)
test:
	uv run pytest

# The quick loop: skip the slow end-to-end tests, the ones on the real data and models, and the Postgres ones
test-fast:
	uv run pytest -m "not slow and not real_data and not pg"

# The accounts tests against the compose Postgres (started here; each run uses a throwaway database)
test-pg:
	docker compose up -d --wait db
	uv run pytest -m pg

# The whole suite with line and branch coverage of ml/ and backend/ (terminal report)
coverage:
	uv run pytest --cov --cov-report=term

# Run the API on http://localhost:8000 with reload (docs at /docs); loads the app's models once (about 15 s)
api:
	uv run uvicorn backend.app.main:app --reload --port 8000

# The user database at USER_DATABASE_URL (.env): apply the migrations, then (re)create the demo account and
# its starting set (needs DEMO_PASSWORD; refuses seed films missing from data/movies.db)
userdb:
	uv run python -m backend.app.userdb.migrate
	uv run python -m backend.app.userdb.seed

# The image: the slim database copy, the prebuilt track records (build/), then the app's one image (needs Docker)
docker-build: ml/artifacts/career_forecast.json
	uv run python scripts/slim_db.py
	uv run python -m ml.features.build prebuilt
	docker compose build

# Start the app and Postgres in the background and wait until their healthchecks pass (about 15 s); the app is on :8080
docker-run:
	docker compose up -d --wait

# Build the image from this commit, push it to GHCR and deploy it on Render (scripts/deploy.py; needs
# docker login ghcr.io and RENDER_DEPLOY_HOOK in .env)
deploy:
	uv run python scripts/deploy.py

# Check the running app: the API at URL and the frontend at WEB (make smoke WEB= skips the frontend);
# make smoke URL=https://... WEB=https://... for the live one
URL ?= http://localhost:8000
WEB ?= http://localhost:8080
smoke:
	uv run python scripts/smoke.py --base-url $(URL) $(if $(WEB),--web-url $(WEB))

# The start page's poster collages -> frontend/public/collages/ (needs data/movies.db and TMDB_READ_TOKEN;
# commit the images, rerun at least every 6 months for TMDB's caching rule)
collages:
	uv run python scripts/build_collages.py

# The frontend (frontend/, needs Node 24): install the locked packages once
web-setup:
	cd frontend && npm ci

# The Vite dev server on http://localhost:5173; /api is proxied to make api on port 8000
web:
	cd frontend && npm run dev

# Types, lint and the Vitest tests of the frontend
web-test:
	cd frontend && npm run check

# Regenerate frontend/src/api/schema.d.ts from the running API's /openapi.json (start make api first)
gen-api:
	cd frontend && npm run gen:api
