"""Synopsis features: MiniLM overview embeddings reduced to N_COMPONENTS numbers with PCA.

    embed_overviews(con, embedder)   -> (movie ids, (n, 384) vectors), cached in data/overview_embeddings.npz;
                                        only films whose overview is new or changed are embedded again
    fit_pca(vectors)                 -> {"mean", "components", "explained_variance_ratio"} (fit on train films only)
    save_pca / load_pca              -> ml/artifacts/synopsis_pca.json (committed, small)
    synopsis_features(vector, pca)   -> synopsis_00..15 and has_synopsis for one film

A film without a synopsis gets the train mean vector, which is all zeros after PCA, and has_synopsis = 0.

CLI: uv run python -m ml.features.synopsis   (embed the overviews, then fit and save the PCA)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.data.build_db import DB_FILE
from ml.features.text import MODEL_REVISION, Embedder

EMBEDDINGS_FILE = Path("data/overview_embeddings.npz")
PCA_FILE = Path("ml/artifacts/synopsis_pca.json")
N_COMPONENTS = 16
FEATURE_NAMES = [f"synopsis_{i:02d}" for i in range(N_COMPONENTS)] + ["has_synopsis"]


def _text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def embed_overviews(
    con: sqlite3.Connection, embedder: Embedder | None = None, cache: Path = EMBEDDINGS_FILE
) -> tuple[np.ndarray, np.ndarray]:
    films = pd.read_sql_query("SELECT id, overview FROM movies WHERE overview IS NOT NULL ORDER BY id", con)
    films["hash"] = films["overview"].map(_text_hash)

    known: dict[str, np.ndarray] = {}
    cached_ids = None
    if cache.exists():
        with np.load(cache) as old:  # closed again before the cache is replaced (Windows locks open files)
            if str(old["revision"]) == MODEL_REVISION:  # a different model means every vector is stale
                known = dict(zip(old["hashes"], old["vectors"]))
                cached_ids, cached_hashes = old["ids"], old["hashes"]
    todo = films[~films["hash"].isin(known)].drop_duplicates("hash")
    if len(todo):
        embedder = embedder or Embedder()
        print(f"Embedding {len(todo):,} overviews ({len(films) - films['hash'].isin(todo['hash']).sum():,} cached) ...")
        start = time.perf_counter()
        known.update(zip(todo["hash"], embedder.embed(todo["overview"].tolist())))
        print(f"  done in {time.perf_counter() - start:.0f} s")

    vectors = np.stack([known[h] for h in films["hash"]]).astype(np.float32)
    unchanged = (cached_ids is not None and np.array_equal(cached_ids, films["id"].to_numpy())
                 and np.array_equal(cached_hashes, films["hash"].to_numpy().astype("U40")))
    if unchanged:
        return films["id"].to_numpy(), vectors
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp.npz")
    np.savez(tmp, ids=films["id"].to_numpy(), hashes=films["hash"].to_numpy().astype("U40"), vectors=vectors,
             revision=np.array(MODEL_REVISION))
    tmp.replace(cache)
    return films["id"].to_numpy(), vectors


def fit_pca(vectors: np.ndarray, n_components: int = N_COMPONENTS) -> dict[str, Any]:
    from sklearn.decomposition import PCA  # training only: scikit-learn is not in the app's image

    pca = PCA(n_components=n_components, random_state=0).fit(vectors)
    return {
        "mean": pca.mean_.tolist(),
        "components": pca.components_.tolist(),
        "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
    }


def save_pca(pca: dict[str, Any], about: str, path: Path = PCA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"about": about, **pca}) + "\n", encoding="utf-8")


def load_pca(path: Path = PCA_FILE) -> dict[str, np.ndarray]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"mean": np.array(data["mean"], dtype=np.float32), "components": np.array(data["components"], dtype=np.float32)}


def synopsis_features(vector: np.ndarray | None, pca: dict[str, np.ndarray]) -> dict[str, float]:
    if vector is None:
        values = np.zeros(len(pca["components"]))
    else:
        values = (np.asarray(vector, dtype=np.float32) - pca["mean"]) @ pca["components"].T
    out = {name: float(v) for name, v in zip(FEATURE_NAMES, values)}
    out["has_synopsis"] = int(vector is not None)
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    with sqlite3.connect(DB_FILE) as con:
        ids, vectors = embed_overviews(con)
        train = set(pd.read_sql_query("SELECT id FROM movies WHERE split = 'train'", con)["id"])
    in_train = np.isin(ids, list(train))
    pca = fit_pca(vectors[in_train])
    explained = sum(pca["explained_variance_ratio"])
    save_pca(pca, f"PCA of MiniLM overview embeddings (revision {MODEL_REVISION[:8]}), fitted on "
                  f"{in_train.sum():,} train films (<=2015); {N_COMPONENTS} components explain {explained:.1%} of the variance.")
    print(f"Wrote {PCA_FILE}: fitted on {in_train.sum():,} train overviews; {N_COMPONENTS} components explain {explained:.1%}")


if __name__ == "__main__":
    main()
