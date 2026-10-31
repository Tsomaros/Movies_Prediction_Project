"""Fake trimmed film records for the cleaning and build tests, made with the real trim_movie."""

from ml.data.pull import trim_movie
from tests.data.test_pull import raw_movie

PULLED_AT = "2026-10-21T12:00:00+00:00"

# A small CPI table: 2019 dollars x 130/110 = 2025 dollars.
TEST_CPI = {2015: 100.0, 2016: 102.0, 2018: 108.0, 2019: 110.0, 2020: 111.0, 2021: 116.0, 2022: 125.0,
            2023: 127.0, 2024: 128.0, 2025: 130.0, 2026: 133.0}


def film(movie_id: int, pulled_at: str = PULLED_AT, **overrides) -> dict:
    """A trimmed record; overrides replace fields of the raw /movie/{id} response before trimming."""
    raw = raw_movie(movie_id)
    raw.update(overrides)
    return trim_movie(raw, pulled_at)
