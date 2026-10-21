.PHONY: setup data db test

# Create .venv and install the locked dependencies
setup:
	uv sync

# Pull films from TMDB into data/raw/ (resumable), then build the database
data:
	uv run python -m ml.data.pull
	uv run python -m ml.data.build_db

# Rebuild data/movies.db from the raw pull only
db:
	uv run python -m ml.data.build_db

# Run the offline test suite
test:
	uv run pytest
