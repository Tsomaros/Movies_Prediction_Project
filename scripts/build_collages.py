"""The start page's two poster collages: frontend/public/collages/movies.webp and series.webp.

    uv run python scripts/build_collages.py          # make collages
    uv run python scripts/build_collages.py --only movies

- Movies: the 24 most popular films with a poster in data/movies.db (read-only).
- Series: TMDB's popular TV list, pages 1-2 (20 shows a page), token from .env.
- The w185 posters are tiled in rows (each row starts 8 further along the list, so a poster repeats only every third row),
  turned by ANGLE degrees and cropped to SIZE, so the corners are always covered.
- Saved as WebP, lowering the quality until the file is under MAX_BYTES.

The images are committed, so building the app never needs TMDB. TMDB's terms allow caching their images for
up to 6 months: rerun this at least that often.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sqlite3
import sys
from pathlib import Path

import httpx
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.data.tmdb_client import TMDBClient  # noqa: E402

DB = Path("data/movies.db")
OUT = Path("frontend/public/collages")
POSTER_URL = "https://image.tmdb.org/t/p/w185"
COUNT = 24
SIZE = (1200, 1000)  # the saved image; the page covers its panel with it and pans across it
TILE = (185, 278)  # a w185 poster
GAP = 10
ANGLE = -6
MAX_BYTES = 160_000


def movie_posters(db: Path = DB, count: int = COUNT) -> list[str]:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT poster_path FROM movies WHERE poster_path IS NOT NULL ORDER BY popularity DESC LIMIT ?", (count,)
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


async def _series(count: int) -> list[str]:
    paths: list[str] = []
    async with TMDBClient.from_env() as tmdb:
        for page in (1, 2):
            body = await tmdb.get("/tv/popular", {"language": "en-US", "page": page}) or {}
            paths += [s["poster_path"] for s in body.get("results", []) if s.get("poster_path") and not s.get("adult")]
    return paths[:count]


def series_posters(count: int = COUNT) -> list[str]:
    return asyncio.run(_series(count))


def download(paths: list[str]) -> list[Image.Image]:
    with httpx.Client(timeout=30) as http:
        images = []
        for path in paths:
            r = http.get(POSTER_URL + path)
            r.raise_for_status()
            images.append(Image.open(io.BytesIO(r.content)).convert("RGB").resize(TILE))
    return images


def collage(posters: list[Image.Image]) -> Image.Image:
    """Rows of posters on a canvas big enough to stay covered after turning, then the centre crop."""
    w, h = SIZE
    side = int((w**2 + h**2) ** 0.5) + 2 * TILE[1]
    canvas = Image.new("RGB", (side, side), (12, 12, 14))
    step_x, step_y = TILE[0] + GAP, TILE[1] + GAP
    for row in range(side // step_y + 1):
        for col in range(side // step_x + 1):
            poster = posters[(row * 8 + col) % len(posters)]
            canvas.paste(poster, (col * step_x - (row % 2) * step_x // 2, row * step_y))
    turned = canvas.rotate(ANGLE, resample=Image.Resampling.BICUBIC)
    left, top = (side - w) // 2, (side - h) // 2
    return turned.crop((left, top, left + w, top + h))


def save(image: Image.Image, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    for quality in range(75, 29, -5):
        buf = io.BytesIO()
        image.save(buf, "WEBP", quality=quality, method=6)
        if buf.tell() <= MAX_BYTES:
            break
    path.write_bytes(buf.getvalue())
    print(f"{path}: {buf.tell():,} bytes (quality {quality})")
    return buf.tell()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", choices=["movies", "series"])
    args = parser.parse_args()
    sources = {"movies": movie_posters, "series": series_posters}
    for name, source in sources.items():
        if args.only and name != args.only:
            continue
        paths = source()
        if len(paths) < COUNT:
            raise SystemExit(f"{name}: only {len(paths)} posters, need {COUNT}")
        save(collage(download(paths)), OUT / f"{name}.webp")


if __name__ == "__main__":
    main()
