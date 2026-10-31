"""The end-to-end test's raw pull: 200 fake TMDB films (2005-2020) made with the real trim_movie, plus messy ones.

    records()   -> the trimmed records, in file order
    MESSY       -> id -> what is wrong with that film (each one should trip one cleaning rule)
    uv run python -m tests.fixtures.mini_raw   (rewrites tests/fixtures/mini_raw.jsonl; tests check it is current)

The normal films are made so the models have something to learn: 20 directors and 60 actors who come back
across the years, budgets that grow with the director's level, revenue about 2.5x the budget with noise, and
scores tied to the director. About 30 films are French (enough for the currency rule's language cap), a few
are sequels in a collection. Keywords are real TMDB ids from ml/features/themes.json, so the films get the
"heist" theme (every fifth film, keyword 395) or "friendship" (keyword 3230), as the app's themes would give.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from tests.factories import film
from tests.features.test_features import credits

FILE = Path(__file__).with_name("mini_raw.jsonl")
PULLED_AT = "2026-10-21T12:00:00+00:00"
YEARS = range(2005, 2021)
GENRES = [(28, "Action"), (18, "Drama"), (35, "Comedy"), (27, "Horror"), (53, "Thriller")]
COMPANIES = [(1, "Big Studio", "US"), (2, "Small Films", "GB"), (3, "Indie House", "US"), (4, "Paris Pictures", "FR")]
SAGA = {"id": 77, "name": "Mini Saga", "poster_path": None}
MESSY = {
    9001: "budget 0 (unknown)",
    9002: "budget $7 (shorthand for millions)",
    9003: "revenue under 0.0001x its budget",
    9004: "a French budget entered in local currency (far above the French cap)",
    9005: "runtime 0",
    9006: "runtime 900 minutes",
    9007: "not released yet (Post Production)",
    9008: "pulled twice: the later pull must win",
    9009: "blank title (falls back to the original title)",
    9010: "no votes (score 0.0 means none)",
    9011: "no genres at all",
    9012: "released 80 days before the pull (revenue still coming in)",
}


def _normal(i: int, rng: np.random.Generator) -> dict:
    movie_id = 1 + i
    year = YEARS[i % len(YEARS)]
    director = i % 20
    level = 1 + director % 4  # bigger directors make bigger films
    budget = int(level * 8_000_000 * rng.lognormal(0, 0.4))
    revenue = int(budget * 2.5 * rng.lognormal(0, 0.6))
    genre = [{"id": g, "name": n} for g, n in GENRES[i % 5: i % 5 + 1 + i % 2]]
    actors = [(2000 + (i * 7 + k * 13) % 60, f"Actor {(i * 7 + k * 13) % 60}") for k in range(5)]
    company = COMPANIES[(i // 3) % 4]
    french = i % 7 == 0
    return film(
        movie_id, pulled_at=PULLED_AT, release_date=f"{year}-{1 + i % 12:02d}-{1 + i % 27:02d}",
        title=f"Mini Film {movie_id}", original_title=f"Mini Film {movie_id}",
        original_language="fr" if french else "en", genres=genre,
        overview=f"Story {movie_id}: a {genre[0]['name'].lower()} tale.", runtime=85 + i % 60,
        budget=budget, revenue=revenue, vote_count=60 + i * 3, vote_average=round(5.0 + level * 0.5 + rng.normal(0, 0.4), 1),
        popularity=round(float(rng.uniform(1, 50)), 2),
        belongs_to_collection=SAGA if i % 25 == 3 else None,
        production_companies=[{"id": company[0], "name": company[1], "origin_country": company[2], "logo_path": None}],
        production_countries=[{"iso_3166_1": "FR" if french else company[2], "name": ""}],
        keywords={"keywords": [{"id": 395, "name": "heist"}] if i % 5 == 0 else [{"id": 3230, "name": "friendship"}]},
        credits=credits(1000 + director, f"Director {director}", actors),
    )


def _messy() -> list[dict]:
    base = dict(pulled_at=PULLED_AT, release_date="2012-06-15", genres=[{"id": 18, "name": "Drama"}],
                belongs_to_collection=None, credits=credits(1000, "Director 0", [(2000, "Actor 0")]))
    later = "2026-10-21T18:00:00+00:00"
    return [
        film(9001, **base, title="Messy Zero Budget", budget=0),
        film(9002, **base, title="Messy Seven", budget=7),
        film(9003, **base, title="Messy Token Box Office", budget=50_000_000, revenue=1_000),
        film(9004, **{**base, "original_language": "fr"}, title="Messy Francs", budget=900_000_000_000),
        film(9005, **base, title="Messy Runtime Zero", runtime=0),
        film(9006, **base, title="Messy Miniseries", runtime=900),
        film(9007, **base, title="Messy Unreleased", status="Post Production"),
        film(9008, **base, title="Messy Old Pull"),
        film(9008, **{**base, "pulled_at": later}, title="Messy New Pull"),
        film(9009, **base, title="", original_title="Le Titre Original"),
        film(9010, **base, title="Messy No Votes", vote_count=0, vote_average=0.0),
        film(9011, **{**base, "genres": []}, title="Messy No Genres"),
        film(9012, **{**base, "release_date": "2026-08-02"}, title="Messy Still Earning"),
    ]


def records() -> list[dict]:
    rng = np.random.default_rng(9)
    return [_normal(i, rng) for i in range(200)] + _messy()


def main() -> None:
    FILE.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records()), encoding="utf-8")
    print(f"wrote {len(records())} records to {FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
