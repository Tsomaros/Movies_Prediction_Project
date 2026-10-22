# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A movie prediction app: a creator fills in a planned film's form and gets 10th/50th/90th percentile ranges for **budget**, **revenue** and **audience score** (TMDB `vote_average`), calibrated to ~80% coverage. Data is our own TMDB pull (79,199 films, 1960–2025). Only `ml/` exists so far (`ml.predict.predict(form)` is the single entry point the API will call); `backend/` (FastAPI, Day 8) and `frontend/` (React + Vite, Day 10) are placeholders.

The work follows a day-by-day plan: `Movie Prediction App Detailed Plan, Days 1–5.md` and `Days 6–10.md`. `PROGRESS.md` holds each day's checklist, stats, "Changes from the plan" and "Surprises / inputs for Day N+1". Each day's step 0 updates the plan document with decisions made, the last step is wrap-up (README, `PROGRESS.md`, commit), and the user approves before a day is closed. `README.md` is the source of truth for reported numbers and Limitations; keep it in sync with what was actually measured.

## Commands

Requires uv and GNU make (Windows: ezwinports make). Python 3.11 only.

```bash
make setup        # uv sync
make model        # download MiniLM ONNX model to ml/artifacts/minilm/ (once)
make test         # uv run pytest (offline, no network or database needed)
make data         # TMDB pull (needs TMDB_READ_TOKEN in .env) + build_db + features
make db           # rebuild data/movies.db from data/raw/ (DROPS the features table; run make features after)
make features     # features table + ml/features/feature_list.json
make tune         # Optuna, 15 min per target -> ml/artifacts/*_params.json, reports/experiments.csv
make train        # ml.models.calibrate then ml.models.train -> ml/artifacts/
make evaluate     # validation + breakdowns + backtest -> reports/ (never touches test)
uv run python -m ml.eval.final all-data   # retrain the app's models on 1960-2025 -> ml/artifacts/final/
uv run python -m ml.explain.comparables   # comparables index -> ml/artifacts/final/comparables.npz (gitignored)
uv run python -m ml.predict manifest      # checksums of the app's files -> ml/artifacts/final/manifest.json
```

`ml.eval.final test` was run once on Day 6 (`reports/final_test.md`) and refuses to run again. The git tags `pre-test` and `final-models` mark the frozen state before and after it.

Single test: `uv run pytest tests/test_models.py::test_name`. `tests/test_golden.py` runs `predict()` on the real all-data models (skipped without the database, `.joblib` files or comparables index) and compares with `tests/golden/predictions.json`; rewrite that snapshot only on purpose with `UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py`. Every module with a CLI runs as `uv run python -m ml.<pkg>.<module>`.

Not in git (rebuilt by the commands above): `data/raw/`, `data/movies.db`, `data/overview_embeddings.npz`, `ml/artifacts/minilm/`, `ml/artifacts/*.joblib`, `ml/artifacts/final/*.joblib`, `ml/artifacts/final/comparables.npz`. The JSON settings/calibration/metadata in `ml/artifacts/` and everything in `reports/` are committed.

## Hard rules

- **Pre-release inputs only.** Post-release fields (`popularity`, `vote_count`, `vote_average`, `revenue`) are never features. The creator form in `ml/features/contract.py` defines every allowed input.
- **Time-based splits:** train ≤2015, validation 2016–18, test 2019+ (constants in `ml/data/clean.py`). The test split is locked: `ml.eval.splits.load(..., "test")` raises `TestSetLocked` unless `final=True`, and only `ml/eval/final.py` may pass it (enforced by `tests/test_final.py`). The test was opened once on Day 6; models must not be changed because of its results. Never fit, early-stop or calibrate on 2016–18 either; it is the honest check.
- **Leak safety** (tested in `tests/test_features.py`): only films released strictly before a film's date count; an earlier film's revenue/score counts only once it is 182 days old (its budget from release); top-N vocabularies, themes and PCA are fit on train years only; a film is a franchise film only if its collection already had an earlier entry.
- **Every model is compared with baselines B0–B2** through the same harness.
- TMDB `0` budget/revenue means unknown. Money is compared in 2025 dollars via `data/cpi_us_annual.csv` (add a row before pulling a new year).

## Architecture

Pipeline: `ml/data` (pull → clean → SQLite) → `ml/features` (one feature function → `features` table) → `ml/eval` (splits, metrics, harness) → `ml/models` (baselines, LightGBM, tuning, calibration).

- **`ml/data/`**: `tmdb_client.py` (rate-limited httpx client, ~20 req/s), `pull.py` (resumable discover + details pull to `data/raw/tmdb_movies.jsonl`), `clean.py` (all cleaning rules; bad values become NULL, suspect money is flagged, every released film is kept), `build_db.py` (builds `data/movies.db` with FTS, a `meta` table of build stats stored as JSON, and per-model training views `v_train_revenue` / `v_train_budget` / `v_train_score`).
- **`ml/features/build.py` is the single feature function** shared by training and the future API: `build_features(form, as_of, ctx)`. Training films are converted to creator forms with `film_to_form` and judged at their release date; a creator's film is judged at the 1st of its release month (`api_as_of`). Any new feature must go through this path so training and serving can't drift. Inputs come from `history.py` (track record with shrinkage toward the "typical film" as if 4 extra average films), `basic.py` (+ `vocab.json`), `themes.py` (+ `themes.json`), `synopsis.py` (MiniLM via `text.py`, PCA in `ml/artifacts/synopsis_pca.json`). `feature_list.json` records each feature's source and which models may use it (`NOT_ALLOWED` keeps a model's own target out).
- **`ml/eval/`**: `splits.py` joins a model's view with the features table (`load`, `fold_data`, three rolling-backtest `FOLDS`: ≤2009→2010–12, ≤2012→2013–15, ≤2015→2016–18). `evaluate.py` is the harness: any object with `fit(train_df)` and `predict(df) -> DataFrame[p10, p50, p90]` (in target units: log 2025 $ for money, points for score) gets validation metrics, breakdowns and the backtest. `metrics.py` holds MAE log / within 2× / coverage / width.
- **`ml/models/`**: `baselines.py` (B0–B2, ranges from train residuals), `train.py` (`LgbmQuantile`; revenue = monotone Huber middle in `MONOTONE` + quantile models of out-of-fold residuals without those columns, because LightGBM refuses monotone constraints on quantile objectives; budget = three unweighted quantile models (never sees `log_budget`); score = three weighted quantile models; `DEFAULT_DROP` is per target: synopsis out of every model, the budget track record also out of score; `EXCLUDED` keeps `log_budget` out of score), `tune.py` (Optuna on folds 1–2, tree count from early stopping), `calibrate.py` (our own CQR function, not MAPIE: widen ranges by q on both sides, learned on out-of-fold predictions from folds 1–2), `ablation.py`, `chain.py` (one revenue model with two corrections, "budget given" and "budget estimated" from the budget model; `predict_revenue(features, budget=None)`, `compare_budget`; `Chain.load(out_dir)`), `rough.py` (frozen rough-estimate cut-offs for revenue and budget).
- **`ml/explain/`**: `drivers.py` (`pred_contrib` on each middle model; contributions plus `expected` add up to the shown p50, crossed budget/score quantiles rescaled; strength cut-offs +50% / +20% for money, 0.3 / 0.1 points for score), `groups.py` (12 creator-friendly groups; every model feature must have one, synopsis has none), `sentences.py` (one template per group, filled from the clean form and feature row; never a raw feature name), `comparables.py` (`Index` of `score_ok` films; only films released strictly before `as_of`; weighted similarity incl. language; money films first).
- **`ml/predict.py`**: `Predictor.load()` checks `ml/artifacts/final/manifest.json` checksums, loads the chain, score model, `FeatureContext` (read-only DB, ~11 s) and comparables; `predict(form)` -> JSON-ready ranges, rough flags, budget comparison, drivers, comparables, warnings, `model_version`. A changed model file means a deliberate `ml.predict manifest` rerun and golden-snapshot update.
- **`ml/eval/final.py`** ran the one-time test (≤2018 models, corrections from all three folds) and builds the app's all-data models in `ml/artifacts/final/` with the ≤2018 corrections; `Chain.load(ml/artifacts/final)` serves them. `ml/artifacts/` itself holds the ≤2015 models from `make train`.

## Conventions

- Module docstrings list the public API and the CLI; follow that style when adding modules.
- Tests use small fake TMDB records built with the real `trim_movie` (`tests/factories.py`); keep the suite offline.
- The plan and README are written in plain, short sentences with concrete numbers; changes from the plan are recorded in `PROGRESS.md`, not silently made.
