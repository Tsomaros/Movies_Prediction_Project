"""Full TMDB poster URLs from a stored poster_path.

    poster(path)  -> {"small": .../w342/x.jpg, "large": .../w780/x.jpg}, or None when there is no poster
    profile(path) -> a person's photo: {"small": .../w185/x.jpg, "large": .../h632/x.jpg}, or None
"""

from __future__ import annotations

IMAGE_BASE = "https://image.tmdb.org/t/p/"
SIZES = {"small": "w342", "large": "w780"}


def poster(path: str | None) -> dict[str, str] | None:
    if not path:
        return None
    return {name: f"{IMAGE_BASE}{size}{path}" for name, size in SIZES.items()}


PROFILE_SIZES = {"small": "w185", "large": "h632"}


def profile(path: str | None) -> dict[str, str] | None:
    if not path:
        return None
    return {name: f"{IMAGE_BASE}{size}{path}" for name, size in PROFILE_SIZES.items()}
