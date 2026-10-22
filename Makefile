.PHONY: setup model data db features tune train evaluate test test-fast coverage api docker-build docker-run smoke

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

# Build the features table in data/movies.db (needs `make model`; new overviews are embedded, the rest is cached)
features:
	uv run python -m ml.features.build

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

# The quick loop: skip the slow end-to-end tests and the ones on the real data and models
test-fast:
	uv run pytest -m "not slow and not real_data"

# The whole suite with line and branch coverage of ml/ and backend/ (terminal report)
coverage:
	uv run pytest --cov --cov-report=term

# Run the API on http://localhost:8000 with reload (docs at /docs); loads the app's models once (about 15 s)
api:
	uv run uvicorn backend.app.main:app --reload --port 8000

# The backend image: the slim database copy, the prebuilt track records (build/), then the image (needs Docker)
docker-build:
	uv run python scripts/slim_db.py
	uv run python -m ml.features.build prebuilt
	docker compose build

# Start the backend container in the background and wait until its healthcheck passes (about 15 s)
docker-run:
	docker compose up -d --wait

# Check a running API: make smoke, or make smoke URL=https://... for the live one
URL ?= http://localhost:8000
smoke:
	uv run python scripts/smoke.py --base-url $(URL)
