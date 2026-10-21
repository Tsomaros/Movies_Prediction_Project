.PHONY: setup model data db features test

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

# Run the offline test suite
test:
	uv run pytest
