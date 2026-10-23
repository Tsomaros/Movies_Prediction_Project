"""Keyword themes: the most common TMDB keywords grouped into a few story themes creators can pick.

    top_keywords(con)                  -> the N_KEYWORDS most common keywords in train films (id, name, n_films)
    cluster_keywords(vectors, k, seed) -> one cluster label per keyword (KMeans on MiniLM vectors)
    propose(con, embedder)             -> unnamed clusters, largest first, for naming by hand
    load_themes(path)                  -> {theme name: set of keyword ids} from the committed themes.json
    theme_flags(keyword_ids, themes)   -> {theme name: 0/1} for one film

Only train films (<=2015) choose the keywords, so later films can't shape the themes. The clusters
were cleaned and named by hand and saved in themes.json (27 themes; keywords that don't describe the
story, such as places and production tags, are listed as dropped). A film has a theme when any of
its keywords is in it.

CLI: uv run python -m ml.features.themes [--k 30]   (print the proposed clusters)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from ml.data.build_db import DB_FILE
from ml.features.text import Embedder

THEMES_FILE = Path("ml/features/themes.json")
N_KEYWORDS = 300
N_CLUSTERS = 30  # the clustering themes.json was cleaned from; 20 mixed unrelated keywords more often
SEED = 0


def top_keywords(con: sqlite3.Connection, n: int = N_KEYWORDS) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT k.id, k.name, COUNT(*) AS n_films
        FROM movie_keywords mk
        JOIN keywords k ON k.id = mk.keyword_id
        JOIN movies m ON m.id = mk.movie_id
        WHERE m.split = 'train'
        GROUP BY k.id
        ORDER BY n_films DESC, k.id
        LIMIT ?
        """,
        con,
        params=(n,),
    )


def cluster_keywords(vectors: np.ndarray, k: int = N_CLUSTERS, seed: int = SEED) -> np.ndarray:
    """KMeans on L2-normalised vectors, so distance follows cosine similarity."""
    from sklearn.cluster import KMeans  # training only: scikit-learn is not in the app's image

    return KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(vectors)


def propose(con: sqlite3.Connection, embedder: Embedder, k: int = N_CLUSTERS) -> list[pd.DataFrame]:
    """The top keywords split into k clusters, largest first; within a cluster, most common first."""
    keywords = top_keywords(con)
    keywords["cluster"] = cluster_keywords(embedder.embed(keywords["name"].tolist()), k)
    groups = [g.sort_values("n_films", ascending=False) for _, g in keywords.groupby("cluster")]
    return sorted(groups, key=lambda g: -g["n_films"].sum())


def load_themes(path: Path = THEMES_FILE) -> dict[str, set[int]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {t["name"]: {kw["id"] for kw in t["keywords"]} for t in data["themes"]}


def theme_flags(keyword_ids: Iterable[int], themes: dict[str, set[int]]) -> dict[str, int]:
    ids = set(keyword_ids)
    return {name: int(bool(ids & members)) for name, members in themes.items()}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Print the proposed keyword clusters.")
    parser.add_argument("--k", type=int, default=N_CLUSTERS)
    args = parser.parse_args()
    with sqlite3.connect(DB_FILE) as con:
        for i, g in enumerate(propose(con, Embedder(), args.k)):
            print(f"[{i}] {len(g)} keywords, {g['n_films'].sum():,} keyword uses: " + ", ".join(g["name"]))


if __name__ == "__main__":
    main()
