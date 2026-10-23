"""Full TMDB poster URLs from a stored poster_path.

    poster(path)  -> {"small": .../w342/x.jpg, "large": .../w780/x.jpg}, or None when there is no poster
"""

from __future__ import annotations

IMAGE_BASE = "https://image.tmdb.org/t/p/"
SIZES = {"small": "w342", "large": "w780"}


def poster(path: str | None) -> dict[str, str] | None:
    if not path:
        return None
    return {name: f"{IMAGE_BASE}{size}{path}" for name, size in SIZES.items()}
