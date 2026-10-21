# Movie Prediction App: Detailed Plan, Days 1–5

Oct 20, 2026 · @Dimitris

## Overview

Week one (Days 1–5) takes the project from an empty repo to tuned, calibrated revenue and score models that are measured honestly against baselines. Each day was planned separately: Claude researched and proposed options, Dimitris chose, and a day was only closed once he approved it.

**Product.** Creators enter a planned movie's parameters and get ranges for budget, revenue and audience score, each with the top factors behind it. The public can browse and search movie information.

**Outputs.** Every prediction is a range: a low end (10th percentile), an expected value (50th) and a high end (90th). Ranges are calibrated so that about 80% of real outcomes fall inside them.

**Stack.** Python, pandas, LightGBM, MAPIE, Optuna, ONNX Runtime, SQLite, FastAPI and React (Vite). All data comes from our own TMDB API pull.

**Working principles**

- Every model input must be something a creator knows before the film exists. Post-release fields (`popularity`, `vote_count`, `vote_average`) are never features.
- Every evaluation uses time-based splits: train ≤2015, validation 2016–18, test 2019+. The test set stays locked until the end of Day 6.
- Every model is compared with simple baselines, and the README reports where it does and doesn't beat them.
- One feature function serves both training and the live app, so the two can never drift apart.
- Speed matters, but the app must work properly and feel good to use.

## Day 1: Setup, data collection and first look

Day 1 ends with a working repo, a full TMDB pull of about 79,000 films (1960–2025), and numbers showing whether the data is good enough for Day 2.

### Decisions

| Topic           | Decision                                                                              | Why                                                                                                          |
| --------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Score target    | TMDB `vote_average`                                                                   | Comes in the same API call; IMDb (via OMDb) noted as a next step                                             |
| Data source     | Our own TMDB API pull only, no Kaggle                                                 | Fresh data with credits and recent films, which an honest 2019+ test needs; one source keeps cleaning simple |
| Films           | 1960–2025, the 1,200 most-voted films per year, all languages (first pulled at 700, extended on Day 2) | About 79k films; global, with `original_language` as a feature; the extra 500 per year mostly add score data |
| Extra fields    | Collection, US certification, keywords, production countries, overview, `poster_path` | All known before release; the poster comes free and avoids a second pull for the browse pages                |
| Fields left out | Cast photos, IMDb id                                                                  | UI-only; not needed                                                                                          |
| Tooling         | `uv`, Makefile, `.env`; no CI or lint                                                 | Speed over ceremony                                                                                          |
| Data check      | Exploration notebook on Day 1                                                         | Finds data problems now instead of on Day 5                                                                  |

TMDB terms to respect: free for non-commercial use with attribution; logo less prominent than our own branding; data not cached for more than six months. The client stays at about 20 requests/second, well under TMDB's limit of roughly 40/second per IP.

### Tasks

1. **Define the targets (15 min).** Write into the README: revenue = worldwide gross, budget = production budget (both nominal USD from TMDB), score = TMDB `vote_average` above a vote threshold set on Day 2.
2. **Repo setup (45 min).** Monorepo `/ml`, `/backend`, `/frontend`, `/data`, `/tests`, `/notebooks`; `uv` with Python 3.11 and a lockfile; `.env` + `.env.example`; `.gitignore`; Makefile with `make setup`, `make data`, `make test`; README skeleton, `PROGRESS.md`, first commit.
3. **TMDB client (1 h).** Read Access Token auth; throttled to about 20 requests/second; retries on 429 and 5xx; 404s skipped; offline tests with a fake TMDB.
4. **Pull script (2 h).**
   - Discover: the 1,200 most-voted films per year, 1960–2025 (60 pages of 20).
   - Details: one request per film, `/movie/{id}?append_to_response=credits,keywords,release_dates`.
   - Keeps basic info, the new fields, production companies, top 15 cast and key crew (director, writers, producers, composer, cinematographer, editor).
   - Resumable, writes each line as soon as it's fetched; output `data/raw/tmdb_movies.jsonl`; about 70 min for the full pull from scratch.
5. **Run it (40 min; the extension to 1,200 per year added about 30 min).** Smoke test with 20 films, then the full pull; write step 6 while it runs.
6. **Exploration notebook (1 h), `notebooks/01_first_look.ipynb`.**
   - Coverage by decade: % with budget, revenue, director, certification.
   - Split sizes (train ≤2015, validation 2016–18, test 2019+).
   - Plots: log-budget vs log-revenue, score distribution, films per language.
   - Suspicious values: tiny budgets (`7` meaning $7M), budgets in local currency.
   - Key numbers saved to `data/day1_summary.json`.
7. **Wrap-up (15 min).** Update `PROGRESS.md` and commit.

**Known risk:** the 1960s–70s will be thin on budget and revenue; those films still serve the score model and the browse pages.

**Done when** the full pull is saved, the tests pass, and the notebook shows which decades and languages have usable money data.

## Day 2: Cleaning and storage

Day 2 ends with one SQLite database that keeps every released film, holds trustworthy money and score values, and has ready-made views for training, search and autocomplete.

### Decisions

| Topic               | Decision                                                                           | Why                                                                                     |
| ------------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Incomplete films    | Keep every released film; bad money becomes NULL                                   | Browse pages and the score model still need them; each model gets its own training view |
| Placeholder money   | Budget or revenue below $1,000 → NULL                                              | TMDB placeholders such as `7` meaning $7M; real micro-budgets survive                   |
| Suspicious money    | Flag `money_suspect`, keep for display, exclude from financial training            | Token box office (revenue below 0.0001× budget) and budgets entered in local currency; no high-ratio rule, since it only caught real hits (Blair Witch, Paranormal Activity) |
| Inflation           | Store nominal and 2025-dollar values from a committed US CPI-U table (FRED, 1960–2025) | Films span 1960–2025; models and UI use 2025 dollars; offline and fixed, unlike the `cpi` library |
| Score reliability   | Minimum vote threshold + `log(1 + vote_count)` training weights                    | Low-vote scores are noisy; well-voted films count more                                  |
| Still-earning films | `revenue_incomplete` for films under 6 months old at pull time; no stricter cutoff | Safety net for future re-pulls; barely applies to this pull                             |
| COVID               | `covid_period` flag for 2020–2021                                                  | The 2019+ test set contains the collapse years                                          |
| Storage             | One SQLite database for app and ML                                                 | Simplest to deploy on Day 14                                                            |
| Tests               | Tests and re-check notebook on Day 2                                               | Rules are easiest to test while fresh                                                   |

### Tasks

1. **Load the raw pull (30 min).** Read the JSONL into pandas; flatten genres, companies, cast, crew, keywords, countries, collection and US certification.
2. **Basic cleaning (1 h).** Keep status "Released"; drop duplicate ids; trim text and fall back to the original title; parse release date into date, year and month; runtime 0 or over 600 min → NULL; 0-vote score → NULL.
3. **Money rules (1.5 h).**
   - Below $1,000 → NULL.
   - Ratio check: revenue ÷ budget below 0.0001× → `money_suspect`.
   - Currency check: non-English films whose 2025-dollar budget is more than 3× their language's 99th percentile (languages with fewer than 30 budgets share one non-English cap) → `money_suspect`.
   - Inflation: `budget_2025` and `revenue_2025` beside the nominal columns.
   - `revenue_incomplete` and `covid_period` flags.
4. **Score rules (30 min).** Vote threshold of 50, confirmed from the Day 1 notebook; store the `log(1 + vote_count)` weight per film.
5. **SQLite database (1.5 h).**
   - Tables: `movies`, `genres`, `people`, `movie_cast` (top 15), `movie_crew` (key jobs), `companies`, `keywords`, `collections`, `countries`, plus link tables.
   - Indexes for browse, filters and autocomplete; FTS5 full-text search on title and overview.
   - Training views: `v_train_revenue` (money known, not suspect, not incomplete), `v_train_budget` (budget known, not suspect), `v_train_score` (votes ≥ threshold, with weight).
   - Autocomplete views: `v_directors`, `v_actors`, ranked by number of films.
   - Built in a temp file and swapped in at the end; a `meta` table holds build time and the cleaning report.
6. **Tests (1 h).** Fake records for a placeholder budget, a rupee-sized budget, an absurd ratio, a 0-vote film, a still-earning film, the inflation calculation and a duplicate id; one end-to-end test of the views and full-text search.
7. **Re-check notebook (45 min), `notebooks/02_clean_check.ipynb`.** Rows changed per rule; training set sizes per model and split; inflation-adjusted budget vs revenue plot. **Gate:** fix any training view too small for a split now.
8. **Wrap-up (15 min).** `PROGRESS.md`, cleaning rules table in the README, commit.

**Done when** `make data` builds the database from the raw pull, all tests pass, and the re-check notebook shows usable training sizes for all three models.

## Day 3: Feature engineering

Day 3 ends with one leak-safe feature function used by both training and the live app, a feature table for every film, and tests proving nothing from the future leaks in.

### Decisions

| Topic                   | Decision                                                                                                                                                                    | Why                                                                      |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Creator form            | Required: genres, release year/month, runtime, language, certification, director, 5–10 actors in billing order (at least 5), at least one theme. Optional: company, country, franchise, synopsis, budget | The form defines what the model may use                                  |
| New people              | Any typed name is accepted; names not in the database count as "new person"                                                                                                 | First-time casts must still get a prediction                             |
| Budget in revenue model | Chained: the creator's budget if given, otherwise the predicted budget, with wider ranges                                                                                   | Budget is the strongest revenue signal; one model, natural "what if" use |
| Track record            | Earlier films only, shrunk towards the average as if the person had 4 extra average films: `(n × own + 4 × average) / (n + 4)`                                              | Leak-safe; one hit doesn't make a "star"                                 |
| Certification           | G, PG, PG-13, R, NC-17 and "unrated/unknown" (NR and missing merged)                                                                                                         | 65% of films have no US certification and 6% are NR                      |
| Keywords                | Grouped into themes (about 15–25); names proposed by Claude, approved by Dimitris                                                                                           | Easier for creators to pick                                              |
| Synopsis                | MiniLM sentence embeddings via ONNX, using the ready-made ONNX export of `all-MiniLM-L6-v2` from Hugging Face                                                               | Strongest text option with no PyTorch anywhere, not even for export      |
| Storage                 | A `features` table in `data/movies.db`, built by `make features`                                                                                                            | One database; no new file format or dependency                           |
| Cut line                | Embeddings move to Day 5 if Day 3 runs short                                                                                                                                | Day 3 is about 9 hours                                                   |

### Leak-safety rules

- **History** means films released strictly before the target film's release date, so a film never counts towards itself.
- An earlier film's revenue and score only count once it is at least 182 days old at that date. Before then it adds to the film count but not to the medians, matching `revenue_incomplete`.
- The average used for shrinkage comes from history only, so it changes over time instead of including future films.
- Top-N lists, the theme keyword list and PCA are fitted on the train split (≤2015) only.
- **Known limitation:** an earlier film's score is its current TMDB rating, not its rating at the time. The pull can't avoid this, so the README states it.

**New dependencies:** `onnxruntime` and `tokenizers` (embeddings), `scikit-learn` (clustering and PCA), and `numpy`, which was already used but is now declared.

### Tasks

0. **Update this plan (5 min).** The decisions and leak-safety rules above.
1. **Form-to-feature contract (30 min).** `ml/features/contract.py` lists every input, its type, whether it's required and its allowed values; `validate(form)` returns the cleaned form and errors. People fields take an autocomplete id or free text (unknown names mean "new person"). It drives Day 8 API validation and the Day 10 form.
2. **Model download and text embedding (45 min).** `make model` downloads `onnx/model.onnx` (about 90 MB) and `tokenizer.json` from `sentence-transformers/all-MiniLM-L6-v2` into `ml/artifacts/minilm/` (gitignored). `ml/features/text.py` runs it with `onnxruntime` + `tokenizers`: mean pooling over the attention mask, then L2 normalisation.
3. **Keyword themes (1.5 h).** Embed the 300 most frequent keywords in train films, cluster them with KMeans (about 20 groups), name the groups ("superhero", "true story", "based on a book", "heist") and get the names approved (done: 27 themes from the 30-group run, cleaned by hand; "amused", "absurd" and "campy" dropped after the notebook); save to `ml/features/themes.json`; one yes/no column per theme.
4. **Track-record features (2 h), `ml/features/history.py`.** For the director and the first 5 billed actors (the form's required 5; actors 6–10 are accepted but not used), from history only: number of earlier films, years since first film, shrunk median earlier log revenue (2025 $) and shrunk median earlier score, earlier franchise films, `is_new`. With several directors, the one with the most earlier films is used. Actors combined as max, mean and min.
5. **Other features (1 h), `ml/features/basic.py`.**
   - Genres: one column each. Language and country: top 15 + "other". Company: top 30, `major_studio`, or "unknown". Lists fitted on train and saved to `ml/features/vocab.json`.
   - Certification: the six categories above. Runtime.
   - Franchise: `is_franchise`, earlier films in the collection, the collection's earlier median log revenue. **Sequels only:** `is_franchise` is 1 only when the collection already had an earlier film, because first entries join a collection only after later sequels (train median revenue: first entries $108M, later entries $103M, no collection $27M). A new franchise name on the form counts as an original film. Franchise experience in Task 4 uses the same rule. Major studios: Universal, Warner Bros., Paramount, Columbia, 20th Century Fox / 20th Century Studios, Walt Disney Pictures, MGM, United Artists.
   - Dates: year, month, summer (May–Aug) and holiday (Nov–Dec) flags, `covid_period`.
   - Budget: log budget in 2025 dollars; predicted budget fills in when missing (Day 6).
6. **Synopsis embeddings (1.5 h).** Embed every overview once into `data/overview_embeddings.npy` (gitignored); PCA from 384 to 16 numbers, fitted on train only, saved to `ml/artifacts/synopsis_pca.json`; neutral vector (zeros after PCA) + `has_synopsis = 0` when empty.
7. **One shared feature function (1 h), `ml/features/build.py`.** `build_features(form, as_of_date, ctx)` for the training table and the Day 8 API. The training table turns each film into a form (`film_to_form`) and passes it through the same function at its release date. Outputs the `features` table in `movies.db` and `feature_list.json` (name, source, allowed per model). `make features` builds it; `make data` = pull, db, features; `make db` drops the table, so `make features` runs after it.
8. **Tests (45 min), `tests/test_features.py`.** No future films in track-record or franchise values; films under 182 days old count but don't move the medians; shrinkage matches a hand-computed value; forbidden inputs never appear and budget isn't a budget-model input; unknown people get neutral values; training and API paths give identical features; contract validation; embedding tests skip when the model file is missing.
9. **Notebook `03_features.ipynb` (45 min).** Missing-value rates, top correlations with log revenue and score (train only), theme sizes and examples, a 2-D view of the embeddings by genre.
10. **Wrap-up (15 min).** `PROGRESS.md`, README features section and limitation, commit.

**Done when** the feature table exists for every film, the leakage tests pass, and the API can call the same function on a form input, including one with a new director.

## Day 4: Baselines and evaluation

Day 4 ends with one evaluation harness that every model goes through, honest baselines to beat, and a rolling backtest showing whether results hold over time. No real model yet; Day 5 plugs into this harness.

### Decisions

| Topic            | Decision                                                                               | Why                                                                     |
| ---------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Test set         | Locked until the end of Day 6; opened once with `final=True`                           | Repeated peeking makes test numbers dishonest                           |
| Final model      | Retrained on train + validation (≤2018) for the test run, then on all data for the app | Uses the most data at each stage                                        |
| COVID in test    | Revenue test reported with and without 2020–21                                         | Most honest view; a good interview point                                |
| Selection metric | MAE on log revenue                                                                     | Stable and fair across budget sizes                                     |
| Headline metric  | "Within 2×" rate                                                                       | Easy to explain in the UI and demo                                      |
| Baselines        | B0 global median, B1 genre median, B2 simple rules                                     | B2 is the tough, credible benchmark                                     |
| Breakdowns       | Included on Day 4                                                                      | Feed the Limitations section and the results-page note                  |
| Rolling backtest | Included on Day 4                                                                      | Shows stability over time; cut line: run on baselines only if over time |

### Metrics

| Target                        | Metrics                                                                                   |
| ----------------------------- | ----------------------------------------------------------------------------------------- |
| Revenue and budget (2025 $)   | MAE on log (selection), median % error, "within 2×" rate (headline), Spearman correlation |
| Score                         | MAE, weighted MAE with `log(1 + vote_count)`                                              |
| Ranges (10th–90th percentile) | Coverage (target about 80%), average width                                                |

### Baselines

|     | Revenue                                 | Budget                          | Score                                                   |
| --- | --------------------------------------- | ------------------------------- | ------------------------------------------------------- |
| B0  | Global median                           | Global median                   | Global median                                           |
| B1  | Median per main genre                   | Median per main genre           | Median per main genre                                   |
| B2  | Typical multiple × budget, fit on train | Genre median × franchise factor | Genre median adjusted by the director's earlier average |

### Tasks

1. **Split module (45 min), `ml/eval/splits.py`.** Train ≤2015, validation 2016–18, test 2019+ behind a `final=True` guard; revenue test with and without 2020–21; each model uses its own Day 2 training view.
2. **Metrics (1 h), `ml/eval/metrics.py`.** The metrics above.
3. **Baselines (1.5 h), `ml/models/baselines.py`.** B0–B2 for all three targets; ranges from training percentiles so coverage applies too.
4. **Breakdowns (45 min).** Budget size (<$10M, $10–50M, $50–150M, $150M+), English vs non-English, new vs experienced director, franchise vs original.
5. **Rolling backtest (1.5 h), `ml/eval/backtest.py`.**

   | Fold | Train | Test    |
   | ---- | ----- | ------- |
   | 1    | ≤2009 | 2010–12 |
   | 2    | ≤2012 | 2013–15 |
   | 3    | ≤2015 | 2016–18 |

   All folds stay before 2019; PCA and baseline multiples refit per fold; metrics per fold plus mean and spread.

6. **Reports (30 min).** `reports/metrics.json`, `metrics.md` (README table), `breakdowns.md`, `backtest.md`.
7. **Tests (45 min).** Metrics on hand-computed examples; the split guard; no training row on or after its fold's test start.
8. **Wrap-up (15 min).** README Evaluation section with baseline results, `PROGRESS.md`, commit.

**Done when** one command produces the baseline metrics, breakdowns and backtest reports, and Day 5's model only has to provide predictions to be compared fairly.

## Day 5: First models (revenue and score)

Day 5 ends with tuned, calibrated LightGBM models for revenue and score, compared fairly against the baselines, plus an ablation table showing which features earn their place. The budget model comes on Day 6.

### Decisions

| Topic                | Decision                                                                           | Why                                                                    |
| -------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Model shape          | Three LightGBM quantile models per target: 10th, 50th, 90th percentile             | One method everywhere; the 50th is the "expected" value                |
| Range calibration    | Conformalized quantile regression (MAPIE) on 2016–18                               | Plain quantile ranges are often too narrow; this corrects them         |
| Tuning               | Optuna with a 15-minute limit per target, on backtest folds                        | Quick and shows method                                                 |
| Monotone constraints | Non-decreasing in budget, director's earlier revenue and franchise earlier revenue | Raising the budget never lowers revenue, so "what if" behaves sensibly |
| Score inputs         | No budget                                                                          | Keeps the score model independent of the chain                         |
| Ablation             | Full table on Day 5, no cut line                                                   | Answers "is the fancy part worth it?"                                  |
| Experiment log       | `reports/experiments.csv`                                                          | Simpler than MLflow, enough for three weeks                            |

### Tasks

0. **Carry-over (0–1.5 h).** Add the synopsis embeddings first if Day 3's cut line was used.
1. **Training module (1.5 h), `ml/models/train.py`.**
   - Revenue: log revenue in 2025 dollars, with real log budget as an input during training.
   - Score: `vote_average`, weighted by `log(1 + vote_count)`, no budget input.
   - Monotone constraints on revenue as decided; outputs sorted if they cross; score clipped to 0–10; early stopping everywhere.
2. **Tuning (1 h).** Optuna, 15 minutes per target, on the backtest folds (≤2015); the middle model is tuned and the 10th/90th reuse its settings; every trial logged.
3. **Conformal calibration (1 h).** MAPIE on 2016–18 targeting 80% coverage. Report coverage before calibration on the backtest folds; true calibrated coverage comes from the test set at the end of Day 6.
4. **Evaluation (45 min).** LightGBM rows next to B0–B2 in the Day 4 harness: validation, backtest folds and breakdowns.
5. **Ablation table (1 h).**

   | Run                      | Revenue | Score |
   | ------------------------ | ------- | ----- |
   | Full model               | ✓       | ✓     |
   | No synopsis embeddings   | ✓       | ✓     |
   | No track-record features | ✓       | ✓     |
   | No themes                | ✓       | ✓     |
   | No budget                | ✓       | —     |
   | No monotone constraints  | ✓       | —     |

6. **Save artifacts (30 min).** `ml/artifacts/revenue_*.joblib`, `score_*.joblib`, plus metadata JSON: features, training years, settings, calibration correction, validation metrics.
7. **Tests (45 min).** Low ≤ middle ≤ high; higher budget never lowers revenue; score within 0–10; saved models reload with identical predictions.
8. **Wrap-up (30 min).** Results and ablation tables in `reports/metrics.md` and the README; `PROGRESS.md`; commit.

**Time:** about 8 hours, more if the embeddings carry over. Spilling into the next session is acceptable and gets noted in `PROGRESS.md`.

**Done when** both models beat the B2 baseline on validation (or the README says honestly where they don't), calibrated ranges exist, and the ablation table is filled in.

## Carried to Day 6 and later

- [ ] **Budget model and the chain (Day 6).** The revenue model trains on real budgets but will sometimes receive a predicted budget in the app; decide how to handle that mismatch.
- [ ] **Open the test set (end of Day 6).** One run with `final=True`: calibrated coverage and final metrics, revenue with and without 2020–21.
- [ ] **Attribution (Day 12).** TMDB logo and notice, logo less prominent than our branding.
- [ ] **New-person note (Day 11).** Results page explains when a director or actor wasn't recognised.
- [ ] **README next steps (Day 15).** IMDb score via OMDb as an alternative target.

## Sources

- [How to Get a TMDB API Key (Apidog)](https://apidog.com/blog/tmdb-api-key/): rate limits, attribution, 6-month caching rule
- [5 Best Movie APIs in 2026 (api.market)](https://api.market/blog/sleeyax/entertainment/best-movie-apis): TMDB rate limit per IP
- [cpi Python library docs](https://palewi.re/docs/cpi/): inflation adjustment
- [How IMDb determines the Top 250](https://neurobiology.substack.com/p/how-imdb-determines-top-250_27): Bayesian weighting of low-vote scores
- [Presenting a Larger Up-to-date Movie Dataset (arXiv 2110.07039)](https://export.arxiv.org/abs/2110.07039): star power and revenue
- [Does Story Really Matter In The Movie Industry? (EconPapers)](https://econpapers.repec.org/paper/iikwpaper/284.htm): counter-evidence on track record
- [MAPIE ConformalizedQuantileRegressor](https://mapie.readthedocs.io/en/stable/generated/mapie.regression.ConformalizedQuantileRegressor.html): calibrated ranges
- [Optuna LightGBMTuner](https://optuna.readthedocs.io/en/v3.0.0/reference/generated/optuna.integration.lightgbm.LightGBMTuner.html): time-limited tuning
