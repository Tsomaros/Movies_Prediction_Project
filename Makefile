.PHONY: setup data test

# Create .venv and install the locked dependencies
setup:
	uv sync

# Pull films from TMDB into data/raw/ (resumable)
data:
	uv run python -m ml.data.pull

# Run the offline test suite
test:
	uv run pytest
