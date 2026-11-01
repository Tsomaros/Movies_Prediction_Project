"""Parity: the serving path and the training path give the same feature row for the same film.

Serving (ml/predict.py) calls build_features(form, api_as_of(form), ctx); training (build_table) calls
build_features(film_to_form(...), release day, ctx). Both use the one function in ml/features/build.py.
This test takes 50 random films (fixed seed) that have a row in the stored `features` table, rebuilds
each row from the film's own database data at its release date (the date training uses) and compares
every feature_list.json column with the stored row (np.allclose, equal_nan=True, default tolerances).

The synopsis columns (synopsis_00..15) are the one place the two paths
differ on purpose: training embeds with the full MiniLM model, the app with its 8-bit copy
(text.APP_MODEL). So the rebuild is done twice:
- with the cached full-model vector, as training does: ALL columns must match;
- through ctx.embed (the 8-bit model, as the app does): every column except synopsis_* must match
  exactly; the synopsis_* columns are only required to stay close (SYNOPSIS_ATOL, measured worst 0.04),
  because they are the PCA numbers of a slightly different embedding.
Skipped without data/movies.db, the features table or the embeddings cache.
"""

import json
import sqlite3

import numpy as np
import pandas as pd
import pytest

from ml.data.build_db import DB_FILE
from ml.features.build import FEATURE_LIST_FILE, FeatureContext, FilmForms, build_features, film_to_form
from ml.features.history import day_number
from ml.features.synopsis import EMBEDDINGS_FILE

SAMPLE = 50
SEED = 20261101
SYNOPSIS_ATOL = 0.1  # 8-bit vs full model; the measured worst gap over these 50 films is 0.040

pytestmark = [pytest.mark.real_data,
              pytest.mark.skipif(not (DB_FILE.exists() and EMBEDDINGS_FILE.exists()),
                                 reason="needs data/movies.db and data/overview_embeddings.npz")]


@pytest.fixture(scope="module")
def parity():
    con = sqlite3.connect(f"file:{DB_FILE.resolve().as_posix()}?mode=ro", uri=True)
    try:
        has_table = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'features'").fetchone()
        if not has_table:
            pytest.skip("no features table (run make features)")
        names = [f["name"] for f in json.loads(FEATURE_LIST_FILE.read_text(encoding="utf-8"))]
        stored = pd.read_sql_query("SELECT * FROM features", con).set_index("movie_id")
        sample = stored.sample(SAMPLE, random_state=SEED)
        ctx = FeatureContext.load(con)
        films = FilmForms.from_db(con)
        with np.load(EMBEDDINGS_FILE) as cache:
            ids, vectors = cache["ids"], cache["vectors"]
        vector_of = dict(zip(ids.tolist(), vectors))
        out = []
        for movie_id, row in sample.iterrows():
            form = film_to_form(movie_id, films, ctx)
            as_of = day_number(films.movies.at[movie_id, "release_date"])
            out.append((movie_id, row[names].to_numpy(dtype=float), names,
                        build_features(form, as_of, ctx, vector_of.get(movie_id)),
                        build_features(form, as_of, ctx)))  # no vector: ctx.embed, the app's 8-bit model
        return out
    finally:
        con.close()


def test_training_inputs_rebuild_every_stored_column(parity):
    assert len(parity) == SAMPLE
    for movie_id, stored, names, trained, _ in parity:
        rebuilt = np.array([trained[n] for n in names], dtype=float)
        assert np.allclose(rebuilt, stored, equal_nan=True), (movie_id, [
            n for n, a, b in zip(names, rebuilt, stored) if not np.allclose(a, b, equal_nan=True)])


def test_serving_embedding_matches_all_but_the_synopsis_numbers(parity):
    worst = 0.0
    for movie_id, stored, names, _, served in parity:
        rebuilt = np.array([served[n] for n in names], dtype=float)
        syn = np.array([n.startswith("synopsis_") for n in names])
        assert np.allclose(rebuilt[~syn], stored[~syn], equal_nan=True), (movie_id, [
            n for n, a, b in zip(names, rebuilt, stored) if not np.allclose(a, b, equal_nan=True) and not n.startswith("synopsis_")])
        if syn.any():
            gap = np.nanmax(np.abs(rebuilt[syn] - stored[syn]))
            worst = max(worst, gap)
    assert worst < SYNOPSIS_ATOL, worst
