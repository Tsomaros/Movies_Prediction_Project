"""API settings, read once from environment variables.

    Settings.from_env()  -> the settings below, each with a default that works from the repository root

| Variable      | Default                     | Meaning                                              |
| MOVIES_DB     | data/movies.db              | the SQLite database, always opened read-only         |
| MODELS_DIR    | ml/artifacts/final          | the app's models, manifest and comparables index     |
| CORS_ORIGINS  | http://localhost:5173       | comma-separated browser origins (the Vite dev server) |
| RATE_LIMIT    | 30                          | prediction requests per minute per client IP         |
| CACHE_SIZE    | 1000                        | predictions kept in the LRU cache                    |
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ml.data.build_db import DB_FILE
from ml.predict import FINAL_DIR

API_PREFIX = "/api/v1"


def _origins(text: str) -> tuple[str, ...]:
    return tuple(o.strip() for o in text.split(",") if o.strip())


@dataclass(frozen=True)
class Settings:
    db_path: Path = DB_FILE
    models_dir: Path = FINAL_DIR
    cors_origins: tuple[str, ...] = field(default=("http://localhost:5173",))
    rate_limit: int = 30
    cache_size: int = 1000

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        return cls(
            db_path=Path(env.get("MOVIES_DB", str(DB_FILE))),
            models_dir=Path(env.get("MODELS_DIR", str(FINAL_DIR))),
            cors_origins=_origins(env.get("CORS_ORIGINS", "http://localhost:5173")),
            rate_limit=int(env.get("RATE_LIMIT", "30")),
            cache_size=int(env.get("CACHE_SIZE", "1000")),
        )
