# Movie Prediction App

Creators enter a planned movie's parameters and get ranges for **budget**, **revenue** and **audience score**, each with the top factors behind it. The public can browse and search movie information.

Every prediction is a range: a low end (10th percentile), an expected value (50th) and a high end (90th). The ranges are calibrated so that about 80% of real outcomes fall inside them.

**Stack:** Python, pandas, LightGBM, Optuna, ONNX Runtime, SQLite, FastAPI and React (Vite). All data comes from our own TMDB API pull.

## Targets

| Target  | Definition                         | Source field                      | Units                                                  |
| ------- | ---------------------------------- | --------------------------------- | ------------------------------------------------------ |
| Revenue | Worldwide box-office gross         | TMDB `revenue`                    | Nominal USD, plus `revenue_2025` in 2025 dollars       |
| Budget  | Production budget                  | TMDB `budget`                     | Nominal USD, plus `budget_2025` in 2025 dollars        |
| Score   | Average TMDB user rating (0–10)    | TMDB `vote_average`               | Films with at least 50 votes, weighted by log(1 + votes) |

A value of `0` in TMDB's `budget` or `revenue` means "unknown", not zero. See [Cleaning rules](#cleaning-rules).

## Working principles

- **Pre-release inputs only.** Every model input must be something a creator knows before the film exists. Post-release fields (`popularity`, `vote_count`, `vote_average`) are never features.
- **Time-based splits.** Every evaluation uses the same splits, and the test set was opened only once, at the end of Day 6.

  | Split      | Release years |
  | ---------- | ------------- |
  | Train      | ≤2015         |
  | Validation | 2016–2018     |
  | Test       | 2019+         |

- **Baselines.** Every model is compared with simple baselines, and this README reports where it does and doesn't beat them.
- **One feature function.** Training and the live app share one feature function, so the two can never drift apart.

## Data

- **Source:** our own TMDB API pull. The 1,200 most-voted films per year, 1960–2025, in all languages (79,199 films). The first 700 per year carry almost all the money data; the extra 500 mostly add score data.
- **Per film:** basic info, genres, overview, runtime, budget, revenue, collection, US certification, keywords, production companies and countries, the top 15 cast, and key crew (director, writers, producers, composer, cinematographer, editor).
- **Raw output:** `data/raw/tmdb_movies.jsonl`. It is not committed to git.
- **Database:** `data/movies.db` (SQLite), built from the raw pull by `make db`, plus the `features` table from `make features`. Neither it nor the overview embedding cache (`data/overview_embeddings.npz`) is committed to git. It holds the cleaned films, people, genres, companies, keywords and collections, full-text search on titles and overviews, and these views:
  - `v_train_revenue`, `v_train_budget` and `v_train_score` for training
  - `v_directors` and `v_actors` for autocomplete
- **Inflation:** `data/cpi_us_annual.csv` holds US CPI-U annual averages for 1960–2025 (FRED `CPIAUCNS`) and is committed. October 2025 was never published because of the government shutdown, so it is filled with the midpoint of September and November. **Add a row for each new year before pulling it**; without one, that year's 2025-dollar values stay empty.

### TMDB terms

- Free for non-commercial use with attribution. Every page carries TMDB's "Primary short" logo (in the footer, or under the start page's cards) (`frontend/public/tmdb-logo.svg`, byte for byte their file: its SHA-256 equals the checksum in TMDB's own file name), smaller than our own brand, with the notice below and a link to TMDB. Film pages also link to the film on TMDB.
- Data is not cached for more than six months. That includes the start page's two poster collages (`make collages`): rebuild them at least every six months.
- The client stays at about 20 requests/second, well under TMDB's per-IP limit.

> This product uses the TMDB API but is not endorsed or certified by TMDB.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/) and GNU make. uv installs Python 3.11 for the project.

```bash
make setup                 # create .venv and install locked dependencies
make model                 # download the MiniLM text model (about 90 MB, once) and make its 8-bit copy for the app
cp .env.example .env       # then paste your TMDB API Read Access Token into .env
make test                  # offline tests, no network needed (about 2-2.5 min; see Testing)
make test-fast             # the quick loop: no slow or real-data tests (about 15 s)
make coverage              # every test with line and branch coverage
make data                  # pull films from TMDB (resumable), build data/movies.db, then the features table
make db                    # rebuild data/movies.db from the raw pull only (about 30 s; drops the features table)
make features              # build the features table (about 1 min; the first run also embeds every overview, about 8 min)
make tune                  # tune the LightGBM settings on backtest folds 1-2 (15 min per target, 45 min in all)
make train                 # calibrate the ranges, then fit and save all three models to ml/artifacts/ (about 5 min)
make evaluate              # baselines and LightGBM on validation, breakdowns and backtest -> reports/ (test split untouched)
make api                   # the API on http://localhost:8000, docs at /docs (needs the database and the app's models)
make docker-build          # the backend and frontend images (see Running with Docker); make docker-run, make smoke
make web-setup             # the frontend's packages (needs Node 24); then make web for http://localhost:5173 (see Frontend)
make web-test              # the frontend's types, lint and tests
uv run python -m ml.models.rough           # the rough-estimate cut-offs (fitted once on Day 6, then frozen)
uv run python -m ml.eval.final test        # the one-time test run (done on Day 6; refuses to run again)
uv run python -m ml.eval.final all-data    # retrain the app's models on 1960-2025 -> ml/artifacts/final/ (about 1 min)
uv run python -m ml.explain.comparables    # the comparable-films index -> ml/artifacts/final/comparables.npz (3 s)
uv run python -m ml.predict manifest       # checksums of the app's model files -> ml/artifacts/final/manifest.json
```

| Folder       | Contents                                         |
| ------------ | ------------------------------------------------ |
| `ml/`        | Data pull, features, models and evaluation; `ml/artifacts/` holds the PCA and the models' settings, calibration and metadata (committed), the MiniLM files and the trained `.joblib` models (not in git; `make model`, `make train`); `ml/artifacts/final/` holds the app's all-data models, their `manifest.json` and the comparables index; `ml/explain/` and `ml/predict.py` turn them into explained predictions |
| `backend/`   | FastAPI app: `backend/app/` with one router per resource, schemas, read-only repo queries and services ([API](#api)) |
| `frontend/`  | React app: the creator form, the API client and types ([Frontend](#frontend)) |
| `data/`      | Raw pull and database (not in git), CPI table, summaries |
| `tests/`     | Offline tests, the end-to-end fixture and the golden forms ([Testing](#testing)) |
| `scripts/`   | `slim_db.py` (the image's database copy) and `smoke.py` (checks a running API and app) |
| `notebooks/` | Exploration and check notebooks                  |
| `reports/`   | Evaluation reports from `make evaluate`, the ablation and the final test run (committed) |

## Cleaning rules

All rules live in `ml/data/clean.py` and are tested in `tests/test_clean.py`. **Every released film is kept** for browsing; bad values become NULL, and suspect money is flagged rather than deleted. Each model trains on its own view. The counts are from the 2026-10-21 pull (79,199 films), and every build stores them in the database's `meta` table.

| Rule | What happens | Films affected |
| --- | --- | --- |
| Status | Only films with status "Released" are kept | 0 dropped |
| Duplicate ids | The latest pull (`pulled_at`) is kept | 0 dropped |
| Text | Whitespace trimmed and empty text becomes NULL; a missing title falls back to `original_title` | 0 titles |
| Release date | Parsed into `release_date`, `year` and `month`; `split` is set from the year | 0 unparseable |
| Runtime | 0 or over 600 minutes → NULL | 1,238 |
| Placeholder money | Budget or revenue below $1,000 → NULL (TMDB shorthand such as `7` meaning $7M) | 167 budgets, 151 revenues |
| Inflation | `budget_2025` / `revenue_2025` = nominal × CPI(2025) / CPI(release year) | All films with money |
| Low ratio | Revenue below 0.0001 × budget → `money_suspect` (token box office, e.g. streaming releases) | 3 |
| Currency | A non-English budget above 3× the 99th percentile of its language's *other* budgets (in 2025 dollars) → `money_suspect`. Languages with fewer than 30 budgets are compared with all other non-English budgets | 3 |
| Still earning | Released less than 182 days before the pull → `revenue_incomplete` | 0 |
| COVID | Released 2020–2021 → `covid_period` | 2,400 |
| Score | 0 votes → score NULL; `score_ok` needs at least 50 votes; `score_weight` = log(1 + votes) | 33,077 `score_ok` |

There is no rule for very *high* revenue-to-budget ratios. The only films above 1,000× were real micro-budget hits (*The Blair Witch Project*, *Paranormal Activity*).

| Training view | Films included | Train / validation / test |
| --- | --- | --- |
| `v_train_revenue` | Budget and revenue known, not `money_suspect`, not `revenue_incomplete` | 8,050 / 886 / 1,485 |
| `v_train_budget` | Budget known, not `money_suspect` | 11,334 / 1,162 / 1,964 |
| `v_train_score` | `score_ok` | 22,016 / 3,600 / 7,461 |

`notebooks/02_clean_check.ipynb` re-checks every rule and the view sizes after each build.

## Features

One function, `build_features(form, as_of, ctx)` in `ml/features/build.py`, turns a creator's form into model inputs. The training table uses the same function: each film is written as a form and judged at its release date. A creator's film is judged at the 1st of its release month. The form itself is defined in `ml/features/contract.py`.

| Creator form | Inputs |
| --- | --- |
| Required | genres (1–5), release year and month, runtime, language, US certification, director, 5–10 actors in billing order, 1–5 themes |
| Optional | production companies, countries, franchise, synopsis, budget (2025 dollars) |

People, companies and the franchise can be picked from autocomplete or typed. A name that isn't in the database counts as a new person, a new company or an original film.

The `features` table in `data/movies.db` has 175 features for every film. `ml/features/feature_list.json` lists each feature's source and which models may use it.

| Group | Features | Notes |
| --- | --- | --- |
| Track record | 24 | Director, and the first 5 billed actors as max, mean and min: earlier films, years active, median earlier log revenue and score shrunk towards the typical film as if they had 4 more average films, earlier franchise films, `is_new` |
| Budget track record | 6 | Median earlier log budget (2025 dollars) of the director, the actors (max, mean, min) and the biggest-spending company, shrunk the same way; the franchise's earlier entries (unshrunk). An earlier film's budget counts from its release |
| Companies | 33 | Top 30 in train, `company_other`, `company_unknown`, `major_studio` (9 classic Hollywood majors) |
| Themes | 27 | Story themes grouped from the 300 most common TMDB keywords (`ml/features/themes.json`) |
| Genres | 19 | One per TMDB genre |
| Countries, language | 17, 16 | Top 15 in train, plus "other" (and "unknown" for countries) |
| Synopsis | 17 | MiniLM (`all-MiniLM-L6-v2`, ONNX) reduced to 16 numbers with PCA, plus `has_synopsis` |
| Certification | 6 | G, PG, PG-13, R, NC-17, unrated/unknown (NR and missing) |
| Release date | 5 | Year, month, summer (May–Aug), holiday (Nov–Dec), `covid_period` |
| Franchise | 3 | `is_franchise` (sequels only), earlier films in the collection, their median log revenue |
| Runtime, budget | 1, 1 | `log_budget` in 2025 dollars; not allowed in the budget model |

**Leak safety.** These rules are tested in `tests/test_features.py`:
- Only films released strictly before the film's date count, so a film never counts towards itself.
- An earlier film's revenue and score count only once it is 182 days old. Its budget counts from its release, since a budget is known before release.
- The typical film used for shrinkage is built from earlier films only.
- The top-N lists, theme keywords and PCA are fitted on train films (≤2015) only.
- A film counts as a franchise film only if its collection already had an earlier film. A first entry joins a collection only once sequels exist, which would leak its later success.

`notebooks/03_features.ipynb` shows missing values, the strongest single signals and a look at the themes and synopsis numbers.

## Evaluation

Every model goes through one harness, `ml/eval/`. Run `make evaluate` to write `reports/metrics.md`, `breakdowns.md`, `backtest.md` and `metrics.json`; it takes about 4.5 minutes and needs the tuned settings and calibration (`make tune`, `make train`).

- **Splits.** Each model is fitted on train (≤2015) and scored on validation (2016–18). The test split (2019+) is locked behind `final=True`, which only `ml/eval/final.py` passes, and was opened once, at the end of Day 6. The revenue test will be reported both with and without 2020–21.
- **Metrics.**
  - Revenue and budget are measured on log 2025 dollars. **MAE on log** picks models, and **within 2×** is the headline. Median % error and Spearman are also reported.
  - Score uses MAE, plus MAE weighted by log(1 + votes).
  - Every model predicts a 10th–90th percentile range, reported as its **coverage** (target 80%) and width.
- **Baselines.** Each baseline's range is its own train errors (10th to 90th percentile) added to its middle prediction.

  |     | Revenue | Budget | Score |
  | --- | --- | --- | --- |
  | B0 | global median | global median | global median |
  | B1 | median per main genre | median per main genre | median per main genre |
  | B2 | budget × the genre's median revenue/budget multiple | genre median × a sequel factor (sequels cost 1.45×) | genre median + 1.18 × (director's shrunk earlier score − typical score) |

  The main genre is TMDB's first-listed genre. Genres with fewer than 30 train films use the global value.
- **Breakdowns.** Validation results by budget size, English vs other languages, new vs experienced director, and sequel vs original.
- **Rolling backtest.** Three folds: train ≤2009 → test 2010–12, ≤2012 → 2013–15, ≤2015 → 2016–18. Each fold refits the model, and a model that uses the synopsis numbers also refits their PCA on that fold's train years.

### Baseline results (validation, 2016–18)

| Revenue | MAE log | Within 2× | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- |
| B0 global median | 1.890 | 24.9% | — | 78.3% | 300× |
| B1 genre median | 1.796 | 26.2% | 0.314 | 78.6% | 240× |
| **B2 budget × genre multiple** | **1.316** | **39.8%** | **0.709** | 79.7% | 53× |

| Budget | MAE log | Within 2× | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- |
| B0 global median | 1.272 | 35.7% | — | 83.1% | 98× |
| B1 genre median | 1.207 | 36.7% | 0.359 | 85.1% | 74× |
| **B2 genre median × sequel factor** | **1.193** | **37.3%** | **0.389** | 86.0% | 72× |

| Score | MAE | Weighted MAE | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- |
| B0 global median | 0.692 | 0.685 | — | 82.6% | 2.30 pts |
| B1 genre median | 0.627 | 0.625 | 0.392 | 81.3% | 2.04 pts |
| **B2 genre median + director** | **0.602** | **0.599** | **0.485** | 81.0% | 1.96 pts |

Rolling backtest, mean ± spread across the three folds (MAE log for money, MAE for score):

| | B0 | B1 | B2 |
| --- | --- | --- | --- |
| Revenue | 1.950 ± 0.043 | 1.876 ± 0.057 | **1.309 ± 0.012** |
| Budget | 1.357 ± 0.064 | 1.273 ± 0.047 | **1.265 ± 0.052** |
| Score | 0.731 ± 0.028 | 0.657 ± 0.021 | **0.621 ± 0.014** |

**What the baselines show**
- **B2 is the benchmark to beat for every target**, and the ranking holds in every backtest fold. Compared with B1, B2 lowers the validation error by 27% for revenue, 4% for score and 1% for budget.
- **Budget is what makes B2 revenue strong.** B2 revenue uses the film's real budget, so it is a "budget known" benchmark.
- **The budget baselines barely learn.** They predict close to the median and do well only on $10–50M films (70% within 2×). At $150M+, not one film lands within 2×.
- **One range for every film fits no group well.** B2 revenue covers 80% overall, but 100% of $150M+ films and only 72% of films under $10M and of new directors' films. The Day 5 quantile models give each film its own range.
- **Small films, new directors and non-English films are the hardest groups; sequels are the easiest** (48% of sequels are within 2× for revenue).
- **The director's track record helps the score only where it exists.** MAE falls from 0.61 to 0.57 for experienced directors and from 0.63 to 0.54 for sequels, but stays at 0.66 for new directors.

## Results

### Models

Revenue, budget and score each have a LightGBM model (`ml/models/`) with the same `fit` / `predict` interface as the baselines.

- **Revenue:**
  - The middle prediction is a Huber model on log 2025 dollars, using the film's real budget during training.
  - It is non-decreasing in budget, the director's earlier revenue and the franchise's earlier revenue, so raising the budget never lowers any prediction. LightGBM doesn't allow these constraints on quantile models.
  - The 10th/90th come from quantile models of the middle model's out-of-fold errors. They leave out those three columns, so each film gets its own range width and the whole range moves with the middle.
- **Budget (Day 6):** three quantile models (10th, 50th, 90th) on log 2025 dollars from `v_train_budget`, with every form field except the budget as input and no constraints.
- **Score:** three quantile models (10th, 50th, 90th) on `vote_average`, weighted by log(1 + votes), with no budget input. Outputs are sorted if they cross and clipped to 0–10.
- **Features:** every allowed feature except the 16 synopsis numbers, which the ablation below found don't help. Revenue and budget also use the 6 budget track-record features (Day 6); for revenue they lowered validation MAE log by 0.020 and the backtest mean by 0.006. Score doesn't use them. That leaves 158 features for revenue, 157 for budget (no `log_budget`) and 151 for score.
- **Tuning:** Optuna, 15 minutes per target, on backtest folds 1–2 only (≤2015).
  - Early stopping on each fold's test years sets the tree count: 1,032 for revenue, 1,404 for budget and 925 for score.
  - The final model trains on all of train with that count.
  - Every trial is logged in `reports/experiments.csv`.
  - Tuning improved fold MAE by only 1.4% for revenue, 2.1% for budget (96 trials) and 0.8% for score.
- **Calibration:** conformalized quantile regression, written as our own short function.
  - Out-of-fold predictions on folds 1–2 (2010–15) give the amount each range is widened on both sides: 0.448 log (about 1.6×) for revenue, 0.399 log (about 1.5×) for budget and 0.165 points for score.
  - 2016–18 is never used to fit, stop or calibrate anything, so its coverage is an honest check.
- **The chain (Day 6):** one revenue model, two range corrections (`ml/models/chain.py`).
  - **Budget given:** the creator's budget goes into the revenue model, with the 0.448 correction above.
  - **Budget estimated:** the budget model's middle prediction goes in instead. Its correction, 0.585 log (about 1.8×), is learned the same way on folds 1–2, with each fold's revenue predictions fed budgets from a budget model trained on that fold's train years.
  - The revenue range models never see the budget, so the estimated range is wider only by its larger correction, and it is never allowed to be narrower than the given one.
  - `predict_revenue(features, budget=None)` picks the mode: a budget means "given", none means "estimated".

### Results (validation, 2016–18)

| Revenue | MAE log | Median % error | Within 2× | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| B2 budget × genre multiple | 1.316 | 71% | 39.8% | 0.709 | 79.7% | 53× |
| **LightGBM, budget given** | **1.093** | **66%** | **46.8%** | **0.807** | 83.6% | **36×** |
| LightGBM, budget estimated | 1.135 | 70% | 44.0% | 0.793 | 86.1% | 48× |

| Budget | MAE log | Median % error | Within 2× | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| B2 genre median × sequel factor | 1.193 | 78% | 37.3% | 0.389 | 86.0% | 72× |
| **LightGBM** | **0.613** | **39%** | **70.9%** | **0.859** | 84.3% | **8.1×** |

| Score | MAE | Weighted MAE | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- |
| B2 genre median + director | 0.602 | 0.599 | 0.485 | 81.0% | 1.96 pts |
| **LightGBM** | **0.496** | **0.501** | **0.687** | 81.0% | **1.68 pts** |

Rolling backtest, mean ± spread across the three folds:

| | B2 | LightGBM | LightGBM per fold (2010–12 / 2013–15 / 2016–18) |
| --- | --- | --- | --- |
| Revenue MAE log | 1.309 ± 0.012 | **1.124 ± 0.023** | 1.129 / 1.149 / 1.093 |
| Revenue MAE log, budget estimated | 1.309 ± 0.012 | 1.192 ± 0.044 | 1.199 / 1.242 / 1.135 |
| Budget MAE log | 1.265 ± 0.052 | **0.662 ± 0.036** | 0.701 / 0.671 / 0.613 |
| Score MAE | 0.621 ± 0.014 | **0.506 ± 0.007** | 0.513 / 0.509 / 0.496 |

**What the results show**
- **All three models beat B2 on validation and in every backtest fold.** Error is 17% lower for revenue, 49% lower for budget and 18% lower for score, with narrower ranges at about 80% coverage.
- **They also beat B2 in every breakdown group:**

  | Group | LightGBM | B2 |
  | --- | --- | --- |
  | $150M+ films, MAE log | 0.48 | 0.65 |
  | Sequels, revenue within 2× | 62% | 48% |
  | New directors, score MAE | 0.53 | 0.66 |
  | $150M+ films, budget within 2× | 90% | 0% |

- **Ranges now fit the groups better.** Revenue coverage is 82–91% in every group (B2: 72–100%), and score coverage is 80–82%.
- **An estimated budget costs revenue some accuracy, but less than having no budget at all.** Validation MAE log is 1.135 with an estimated budget, against 1.093 with the real one and 1.219 for a model with no budget input (ablation). Even estimated, it beats B2, which uses the real budget (1.316). The estimate is within 2× of the real budget for 75% of revenue films.
- **Estimated-budget ranges are wider and slightly cautious.** They are typically 48× wide (36× with the budget given) and cover 86% of 2016–18 films, above the 80% target; every group is covered 84–94%.
- **Revenue coverage on 2016–18 is 84%, a little above the target.** Calibrated on 2010–15, the ranges are slightly cautious for 2016–18. On the test years they are slightly narrow instead (77%; see below).
- **The budget model learns what the baselines couldn't.** B2 budget barely beat the median; LightGBM puts 71% of films within 2× (B2: 37%). Earlier budgets of the companies, director and actors carry most of it: without them, validation MAE log rises from 0.613 to 0.667.
- **Budget coverage on 2016–18 is 84%,** slightly cautious like revenue, but only 77% for films under $10M. Budget ranges are typically 8× wide (5× for $150M+ films, 12× under $10M and for new directors).
- **Small films are still hard.** Under $10M, revenue MAE log is 1.34 and only 36% are within 2× (B2: 35%); budget MAE log is 0.85 (0.33 at $150M+).
- **Revenue ranges are wide.** The high end is typically 36× the low end, meaning a film's revenue is honestly very uncertain before release. Score ranges average 1.7 points.

### Rough-estimate label

A revenue or budget prediction is labelled a **rough estimate** when its high end is more than 81× (revenue) or 12× (budget) its low end. These cut-offs are the widest quarter of 2016–18 ranges, rounded, and are frozen in `ml/artifacts/rough_estimate.json` (`uv run python -m ml.models.rough`). Score gets no label: its ranges barely vary (1.3–2.0 points) and their width hardly predicts the error (Spearman 0.09). The plan's starting point of 4× would have labelled 98% of revenue and 93% of budget predictions.

| Validation, 2016–18 | Labelled | MAE log, labelled / rest | Within 2×, labelled / rest |
| --- | --- | --- | --- |
| Revenue, budget given | 25% | 1.54 / 0.95 (1.6×) | 34% / 51% |
| Revenue, budget estimated | 32% | 1.55 / 0.95 (1.6×) | 31% / 50% |
| Budget | 27% | 0.86 / 0.52 (1.7×) | 54% / 77% |

The cut-offs were chosen on these films, so the test set gives the honest check.

### Budget comparison

Every prediction includes "Similar films usually cost $X–Y": the budget model's calibrated 10th–90th range for the same form. It is shown even when the creator gives a budget, and the budget is then placed below, within or above that range (`Chain.compare_budget` in `ml/models/chain.py`; `predict()` also says "at the low / high end" within 5% of an edge). On 2016–18, 84% of real budgets fall within, 11% below and 5% above, so the model overestimates more often than it underestimates. For example, *Get Out* ($5.9M) gets "$1.4M–$20M" and *Avengers: Infinity War* ($380M) gets "$180M–$580M".

### Ablation

Each row removes one part and reuses the tuned settings. The full model here means every allowed feature, synopsis included. Lower error is better, and the change is the row minus the full model (`reports/ablation.md`).

| Run | Revenue MAE log | Change | Backtest change | Score MAE | Change | Backtest change |
| --- | --- | --- | --- | --- | --- | --- |
| Full model | 1.126 | — | — | 0.498 | — | — |
| No synopsis embeddings | 1.113 | −0.013 | −0.006 | 0.496 | −0.001 | −0.000 |
| 32 synopsis numbers | 1.124 | −0.002 | +0.008 | 0.498 | +0.001 | +0.004 |
| No track-record features | 1.136 | +0.010 | +0.017 | 0.501 | +0.003 | +0.016 |
| No themes | 1.135 | +0.008 | +0.012 | 0.503 | +0.005 | +0.007 |
| No budget | 1.219 | +0.092 | +0.108 | — | — | — |
| No monotone constraints | 1.122 | −0.004 | −0.001 | — | — | — |

- **Budget is by far the strongest revenue input.** Without it, revenue within 2× falls from 44.7% to 39.3%.
- **Track record and themes earn their place** in the revenue and score models, by about 0.01–0.02 in the backtest.
- **The synopsis embeddings don't help either model, and 32 numbers don't help either**, so the saved models leave them out. The features table still stores 16, for the app and for later tries.
- **Monotone constraints cost no accuracy**, so "what if" changes in the app behave sensibly for free.
- **Budget (Day 6):**

  | Run | Budget MAE log | Change | Backtest change |
  | --- | --- | --- | --- |
  | Full model (every allowed feature) | 0.613 | — | — |
  | No synopsis embeddings (saved) | 0.613 | +0.000 | −0.004 |
  | 32 synopsis numbers | 0.617 | +0.004 | +0.008 |
  | No budget track record | 0.667 | +0.054 | +0.061 |
  | No track-record features | 0.636 | +0.023 | +0.026 |
  | No themes | 0.608 | −0.005 | +0.001 |

  Removing the budget track record costs the most, more than the whole people track record. The synopsis doesn't help the budget model either, so it is left out. Themes are a wash (−0.005 on validation, +0.001 in the backtest) and stay in, as in the other models.
- **The budget track record (Day 6) helps revenue, mostly on 2016–18.** Added to the saved model's features, it lowers validation MAE log from 1.113 to 1.093 and the backtest mean from 1.130 to 1.124. The backtest gain comes from fold 3 (2016–18, −0.020); folds 1–2 change by +0.004 and −0.002. The revenue and score rows in the first table leave it out.

## Final test results (2019+)

The test split was opened once, on 2026-10-21, after everything was frozen at the `pre-test` tag (`uv run python -m ml.eval.final test`; full tables in `reports/final_test.md`). Every model, B0–B2 included, was refitted on films released up to 2018 with the frozen settings. Each range correction came from out-of-fold predictions on all three backtest folds (2010–18): revenue +0.399 log (budget estimated +0.505), budget +0.363 log, score +0.159 points. No model was changed after the run.

| Revenue, budget given | Films | MAE log | Median % error | Within 2× | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B2 budget × genre multiple | 1,485 | 1.455 | 82% | 36.2% | 0.664 | 77.6% | 54× |
| **LightGBM** | 1,485 | **1.230** | **76%** | **41.1%** | **0.761** | 77.4% | **34×** |
| LightGBM, without 2020–21 | 1,163 | 1.189 | 74% | 42.4% | 0.764 | 78.2% | 33× |

| Revenue, budget estimated | Films | MAE log | Median % error | Within 2× | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **LightGBM** | 1,485 | **1.266** | **78%** | **38.7%** | **0.744** | 78.2% | 42× |
| LightGBM, without 2020–21 | 1,163 | 1.225 | 75% | 39.8% | 0.751 | 79.4% | 41× |

| Budget | Films | MAE log | Median % error | Within 2× | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B2 genre median × sequel factor | 1,964 | 1.247 | 80% | 34.3% | 0.360 | 83.7% | 67× |
| **LightGBM** | 1,964 | **0.682** | **45%** | **66.7%** | **0.827** | 79.9% | **7.6×** |

| Score | Films | MAE | Weighted MAE | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| B2 genre median + director | 7,461 | 0.574 | 0.578 | 0.503 | 80.8% | 1.94 pts |
| **LightGBM** | 7,461 | **0.493** | **0.491** | **0.641** | 81.1% | **1.67 pts** |

**What the test shows**
- **All three models beat B2 on the test set.** Error is 15% lower for revenue (budget given), 45% lower for budget and 14% lower for score. Revenue with an estimated budget (1.266) also beats B2, which uses the real budget (1.455).
- **Revenue is harder on 2019+ than on 2016–18 for every model.** LightGBM's MAE log rose from 1.093 to 1.230, and B2's from 1.316 to 1.455, by about the same amount. Leaving out 2020–21 brings LightGBM down to 1.189. Budget rose from 0.613 to 0.682; score stayed level (0.496 → 0.493).
- **Coverage is close to 80%:** budget 79.9%, score 81.1% and revenue 77.4% (78.2% without 2020–21). Revenue ranges are slightly too narrow on the test years; 2016–18 had been slightly too wide (84%).
- **Big-budget revenue is the one group where LightGBM doesn't beat B2.** For $150M+ films (108), MAE log is 1.04 against B2's 0.99, and only 64% are covered (B2: 90%). With an estimated budget it's 0.99, level with B2. $50–150M films are covered 75%.
- **Every other group is better than B2:** for example films under $10M (revenue 1.36 vs 1.68), new directors (revenue 1.40 vs 1.71; budget 0.92 vs 1.67) and sequels (revenue within 2× 61% vs 45%).
- **The rough-estimate label still picks out the worst predictions,** with smaller gaps than on 2016–18:

  | Test, 2019+ | Labelled | MAE log, labelled / rest | Within 2×, labelled / rest |
  | --- | --- | --- | --- |
  | Revenue, budget given | 18% | 1.65 / 1.14 (1.4×) | 27% / 44% |
  | Revenue, budget estimated | 24% | 1.62 / 1.16 (1.4×) | 25% / 43% |
  | Budget | 24% | 1.02 / 0.58 (1.8×) | 49% / 72% |

The app's models are then retrained on every film from 1960–2025 with the same settings, tree counts and ≤2018 corrections (`uv run python -m ml.eval.final all-data` → `ml/artifacts/final/`). Their own accuracy can't be measured, since no later films are left to test on.

## Explanations and `predict()`

Day 7 turns the app's models into one call: `ml.predict.predict(form)` returns budget, revenue and score ranges, the top 5 drivers of each in plain English, 5 comparable past films and warnings. `notebooks/07_explanations.ipynb` checks the cut-offs and weights below and runs six famous films through it.

### Drivers

- **What is explained:** each target's middle (p50) model. LightGBM's `pred_contrib` splits a prediction into one amount per feature plus the typical film's value, and these add up exactly to the middle that is shown (`ml/explain/drivers.py`). When the budget or score quantile models cross, the sorted middle is not the p50 model's own (about 3% of 2016–18 budget films), and those amounts are scaled to match.
- **Groups:** the 158 features are merged into 12 groups a creator recognises: budget, director, cast, franchise, studio, genre, themes, release timing, runtime, certification, language and country (`ml/explain/groups.py`). The budget track record joins the group it describes, and the synopsis numbers have no group because no model uses them.
- **Strength:** money effects are "strong" from +50% (or −33%), "moderate" from +20% (or −17%), otherwise "slight"; score effects from 0.3 and 0.1 points. The plan started at +25% / +10%, which made 99% of top revenue drivers on 2016–18 "strong"; with +50% / +20%, 30% of the top 5 drivers are strong, 53% moderate and 17% slight.
- **Sentences:** one template per group, filled with the creator's values (`ml/explain/sentences.py`), for example "Being part of The Avengers Collection (2 earlier films) strongly raises the expected revenue." or "Jordan Peele, with no earlier films as director in our data, lowers the expected revenue." Release timing names whichever part pushes most: "Releasing in 2026 (recent films earn less in our data)" or "Releasing in December (holiday season)". In "budget estimated" mode the budget driver says so: "The estimated budget of about $29M …".

| 2016–18, ≤2015 models | Most often the top driver |
| --- | --- |
| Revenue | budget 70%, studio 9% |
| Budget | studio 73% (90% of it the companies' earlier budgets), cast 14% |
| Score | cast 44%, genre 26%, runtime 19% |

### Comparable films

`ml/explain/comparables.py` returns 5 earlier films like the planned one, with their real budget, revenue (2025 $) and score, and up to 3 short reasons why each is similar, strongest first: the shared genres or themes by name ("Same genres", "Also superhero, science fiction"), "Similar story" (synopsis cosine 0.5+), "Similar budget" (within 2×), "Same era" (about 5 years) or, for films not in English, "Same language". The pool is the 33,077 films with a usable score; only films released before the planned date can be returned, and of the 50 most similar, those with a reported budget or revenue come first. Similarity is a weighted average of genres (0.3), themes (0.2), synopsis (0.3, cosine on the MiniLM vectors, skipped without a synopsis), era (0.1), budget level (0.2, the creator's budget or the budget model's estimate) and the same original language (0.1). The index (`ml/artifacts/final/comparables.npz`, 26 MB, not in git) is built by `uv run python -m ml.explain.comparables`; a query takes about 8 ms.

The language weight and the doubled budget weight were chosen on 600 films from 2016–18, each judged at its release:

| Weights | Comparables' revenue vs the film's (MAE log) | Score MAE | Same language |
| --- | --- | --- | --- |
| Planned (no language, budget 0.1) | 1.883 | 0.602 | 60% |
| Chosen (language 0.1, budget 0.2) | 1.802 | 0.584 | 84% |
| Chosen + a tie-break towards well-known films | 1.931 | 0.572 | 83% |

For example, *Avengers: Infinity War* gets *Green Lantern*, *Avengers: Age of Ultron*, *Captain America: Civil War*, *Justice League* and *X-Men: Days of Future Past*, and *Paddington 2* gets *Paddington* first.

### `predict()`

`Predictor.load()` loads the all-data models from `ml/artifacts/final/`, the feature context from `data/movies.db` (read-only) and the comparables index, about 11 s once; `predictor.predict(form)` then takes about 150 ms (median of 30 calls for each of three forms, under the 400 ms target). The steps are: validate the form (`ml/features/contract.py`; an invalid form raises `InvalidForm` with one message per field), build the features, predict the budget, revenue (with the creator's budget, or the estimated one) and score, then the drivers and comparables. The output is a JSON-ready dict:

- `budget`, `revenue`, `score`: low, middle and high (2025 $ or points), a text range such as "$5.2M–$62M", and the rough-estimate flag (revenue and budget only); revenue also has its `mode` and the budget it used;
- `budget.comparison`: "Similar films usually cost $X–Y" and, with a budget, "Your budget of $X is below / at the low end of / within / at the high end of / above what similar films usually cost" (within 5% of an edge counts as "at the end", since both can round to the same figure);
- `drivers`, `comparables`, `warnings`, `model_version` and `as_of` (the 1st of the release month, the date the film is judged at).

Warnings appear for a budget of $150M or more (revenue for these films was the weak spot on 2019+, and above $300M a bigger budget no longer raises the estimate), a director or actors we can't match, an empty production country or studio (past films with none recorded are mostly small, so an empty field lowers the ranges), and a release after 2025, where the data ends. The score always carries a note that new films' TMDB scores start higher and settle during their first year, so the range is for the settled score (audit, Finding 1).

`ml/artifacts/final/manifest.json` (`uv run python -m ml.predict manifest`) lists every model file with its checksum, the training years, the corrections, the LightGBM version and the `final-models` tag; the predictor refuses to load models that don't match it. The rough-estimate rule is copied into the same folder, so it holds everything the app reads except the database.

| Example form | Budget | Revenue | Score |
| --- | --- | --- | --- |
| Franchise blockbuster (Russo brothers, Avengers cast, Marvel, $300M, May 2027) | $180M–$600M | $500M–$3.6B | 6.4–8.2 |
| Small drama (Greta Gerwig, A24, no budget given, October 2026) | $5.2M–$62M, rough | $2M–$170M (budget estimated), rough | 6.2–7.6 |
| Unknown cast (horror, new director and actors, $2M, no studio or country) | $18K–$7M, rough | $38K–$14M, rough | 4.8–6.9 |

These three forms are the golden examples in `tests/test_golden.py`: the tests check rules (ordered ranges, mode, warnings, earlier comparables, speed) and a snapshot of the output in `tests/golden/predictions.json`, which is rewritten only on purpose (`UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py`).

## API

A FastAPI backend in `backend/app/`. Every endpoint lives under `/api/v1`, and the interactive docs are at `/docs`. Run it with `make api` (http://localhost:8000; about 10 s to load the models and lookups once). The React app ([Frontend](#frontend)) is built against this API.

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/v1/predict` | A creator form in; ranges, drivers, comparable films and warnings out |
| POST | `/api/v1/predict/compare` | A base form and 1–3 variants; every prediction plus the differences |
| POST | `/api/v1/predict/sweep` | One form with one field (`release_month`, `runtime` or `budget`) tried at 2–12 values; the three ranges at each |
| GET | `/api/v1/movies` | Search (`q`), filters (`genre`, `year_from`, `year_to`, `language`, `score_min`: films with any number of votes), `sort` (popularity, newest, title, score: 50+ votes only, revenue: 2025 $, trusted figures only), `page`, `page_size` (at most 48); each film with its score, votes and revenue in 2025 $ |
| GET | `/api/v1/movies/{id}` | Facts, themes, cast and crew, money (as reported and in 2025 $), score, posters and 6 similar films |
| GET | `/api/v1/people?role=director\|actor&q=` | Director and actor autocomplete |
| GET | `/api/v1/companies?q=`, `/api/v1/collections?q=` | Studio and franchise autocomplete |
| GET | `/api/v1/meta/options` | Every form field and limit from the contract, the 27 themes, common languages and countries, suggested years |
| GET | `/api/v1/model-card` | The served models' accuracy: the 2019+ test and the 2026 holdout next to the best baseline, training films, the database's size and years, and the "within the uncertainty" thresholds |
| GET | `/api/v1/health` | Status, model version, database build, uptime and the prediction cache |

**Predictions.**
- **The form:** `/predict` takes the creator form from `ml/features/contract.py`. People, companies and the franchise can be an id from autocomplete, a typed name or `{id, name}`. Leave `budget` out and it is estimated.
- **The output:** exactly what `predict()` returns, plus `cached` and full TMDB poster URLs for the comparables. The OpenAPI schema documents every field, for the Day 10 TypeScript types.
- **The model card:** `uv run python -m ml.eval.model_card` copies the numbers from `reports/final_test.json` and `reports/audit_metrics.json` into `ml/artifacts/final/model_card.json` (committed, because the image has no `reports/`). Per target it has the films, the share inside the range, the typical miss of the middle (money as a factor, exp(MAE log); score in points), within 2× and the median range width, for LightGBM and for B2. `/model-card` adds the database's films and years, and answers 503 if the card was written for other models than those being served. `tests/test_model_card.py` fails when the committed card no longer matches the reports.
- **"Within the uncertainty" (Day 13):** the card also holds the thresholds the compare page uses. A change between two versions of a film counts only if it moves the middle by at least a tenth of the median 80% range on validation (2016–18, `reports/metrics.json`). For money that is a factor of width^0.1, because the width is high ÷ low: **×1.43** for revenue (×1.47 with the budget estimated) and **×1.23** for budget. For the score it is **0.17 points**.
- **Compare:** each variant lists only the fields it changes, and `null` clears an optional one. For each variant, `differences` gives the changed fields, the money middles as a ratio of the base's (×1.8), the score as a point difference (+0.3), and whether the revenue mode changed.
- **Sweep (Day 13):** `{form, field, values}` tries one field at each value, e.g. the 12 months of the planned year, and returns the budget, revenue and score ranges at each, plus the revenue mode. It counts as one request against the rate limit, and every point goes through the prediction cache.

```bash
curl -s localhost:8000/api/v1/predict -H 'Content-Type: application/json' -d '{
  "genres": ["Drama"], "release_year": 2026, "release_month": 10, "runtime": 105, "language": "en",
  "certification": "R", "director": 45400, "actors": [36592, 1373737, 1190668, "Ann Newcomer", "Bo Unknown"],
  "themes": ["family", "coming of age and school"], "companies": [41077], "countries": ["US"]}'
```

**Errors.** Every 422 has one shape, `{"detail": "Some fields need fixing", "errors": {field: message}}`, and one response lists every problem:
- **Messages:** they come from the contract, so a wrong type reads like a wrong value: `{"runtime": "must be a number", "themes": "required", "genres": "unknown value(s): 'Cartoon'"}`.
- **Compare:** errors name the variant, e.g. `variants.1.budget`.
- **Sweep:** errors name the form's field (`form.runtime`) or the value (`values.3`).
- **Other errors:** an unknown film is a 404, and a wrong method a 405.
- **In the schema:** every 422 is documented as this shape (`FieldErrors`), and 404 and 429 as `{"detail"}`, so the frontend's generated types match what the API sends.

**Limits and caching.**
- **Rate limit:** 30 prediction requests a minute per IP, shared by `/predict`, `/compare` and `/sweep` (our own sliding window, in memory). The 31st gets a 429, "Please try again in a minute", with `Retry-After`.
- **Prediction cache:** the 1,000 most recently used predictions are kept (LRU), keyed by the validated form, so the same film written two ways is one entry.
- **HTTP caching:** movie, autocomplete, options and model-card responses are cacheable for an hour (`Cache-Control: public, max-age=3600`); health is `no-store`.
- **Settings:** `MOVIES_DB`, `MODELS_DIR`, `CORS_ORIGINS` (default the Vite dev server), `RATE_LIMIT` and `CACHE_SIZE` come from environment variables.

**Search and lookups.**
- **Search:** every word of `q` is a quoted prefix in SQLite FTS5, over titles, original titles and overviews, with accents ignored. Typed text can never be FTS syntax.
- **Similar films:** they come from the Day 7 index with no date rule, any year but never the film itself.
- **Autocomplete:** in memory. Any word of a name can start the match ("hanks", "tom ha"), and the names with the most films come first. The 398k names and their word keys are packed into byte blobs, about 33 MB; plain Python lists took about 207 MB.
- **The database:** opened read-only (`mode=ro`), with one connection per request, so the API cannot write to it.

**Measured** on this Windows laptop with the real models:

| | |
| --- | --- |
| Startup (models, feature context, comparables, lookups) | about 10 s |
| `/predict` over HTTP, uncached | median 167 ms (under the 400 ms target); about 3 ms from the cache |
| `/predict/compare` with 3 variants, uncached | about 0.5 s |
| `/predict/sweep` over 12 months, uncached | 1.6 s in Docker (12 predictions); cached, a few ms |
| Autocomplete / movie search / movie page | 2–10 ms / 5–90 ms / about 20 ms |
| Memory after startup / after predictions with a synopsis (MiniLM loaded) | 639 MB / 746 MB on Windows, before the Day 9 cuts; in Docker now 323 MB / 407 MB ([Running with Docker](#running-with-docker)) |

Memory was 1,236 MB at first. The track record (`ml/features/history.py`) kept 350k small objects (about 870 MB); it now packs them into flat arrays (about 108 MB), and the rebuilt features table is bit-for-bit identical to the stored one. Day 9 brought the app under the 450 MB gate for the free host.

`tests/test_api.py` (63 tests, offline, on a small fake database and small models) checks:
- every endpoint, pinned to a list so a new one must get a test;
- both revenue modes, the cache, compare's differences, a 12-month sweep equal to single predictions, every kind of 422, and the 31st request;
- FTS input that would be syntax, pages, filters and sorting;
- similar films that never include the film itself, read-only connections, and parallel requests.

`tests/test_api_golden.py` (10 tests, skipped without the real data and models) checks:
- the golden forms over HTTP equal `predict()` and the snapshot, in under 400 ms;
- real autocomplete, movie pages, options and health.

## Frontend

A React app in `frontend/` (Vite 8, React 19, TypeScript 6, Tailwind 4 with shadcn/ui, React Router 8, TanStack Query 5, React Hook Form + Zod 4). It needs Node 24.

```bash
make web-setup   # npm ci, once
make api         # the API on :8000 (the dev server proxies /api to it)
make web         # the app on http://localhost:5173
make web-test    # types, lint (oxlint) and the Vitest tests
make gen-api     # regenerate src/api/schema.d.ts from the running API's /openapi.json
make collages    # the start page's poster collages (needs data/movies.db and TMDB_READ_TOKEN; commit the two images)
cd frontend && npm run coverage
```

| Path | What it holds |
| --- | --- |
| `src/app/` | routes, layout (header, navigation, footer with the TMDB notice), theme, providers |
| `src/api/` | the typed client (`client.ts`), the hooks (`hooks.ts`), shared error handling (`errors.ts`), and `schema.d.ts` generated from the API |
| `src/form/` | the creator form: values and Zod rules (`model.ts`), the examples, the URL and draft (`persist.ts`), and its inputs (`inputs/`) |
| `src/pages/` | the start page `/`, `/series` (coming soon), `/movies` (curated rows), `/browse` (search), `/predict`, the results page `/predict/result`, the compare page `/predict/compare`, `/movies`, `/movies/:id` and `/about` |
| `src/movies/` | the public side's parts: the browse state in the URL (`browse.ts`), filters, poster, cards, pager, the curated rows of `/movies` (`rows.ts`, one config entry per row) and "Predict a film like this" (`predictLike.ts`) |
| `src/result/` | the results page's parts: summary cards, the range chart, drivers, comparable films, notes and accuracy, and number formatting (`format.ts`) |
| `src/compare/` | the compare page's parts: the variants in the URL, the presets and "within the uncertainty" (`variants.ts`), the picker, the side-by-side view, and the month sweep (`sweep.ts`, `MonthSweep.tsx`) |

**The start page** (`/`) has no header or footer: the title, then two bordered cards in the middle of the screen, each over a poster collage. **Movies** opens `/movies`, **Series** opens `/series` ("coming soon", over the same collage blurred). Under the cards: "Predict a film", "About", the theme switch and TMDB's logo and notice. Every other page has the header (Movies · Browse · Predict · About) and the footer.

![The start page: Movies and Series cards](docs/images/start-page.png)

- **Cards:** 320 × 400 px side by side on wide screens; on a phone they stack and turn landscape (16:10), so both fit on one screen. Hovering or focusing a card lifts it, lightens its overlay and lifts its title. Each card is one link with a visible focus ring.
- **The collages** pan slowly with a CSS transform; the pan is off when the system asks for reduced motion.
- **The images** are two static WebP files (about 155 kB each, 1200 × 1000) in `frontend/public/collages/`, made by `scripts/build_collages.py` (`make collages`): 24 w185 posters each, tiled in turned rows with Pillow. Movies are the 24 most popular films with a poster in our database; series come from TMDB's popular TV list (two pages of 20). They are committed, so building the app never calls TMDB.

**The form** (`/predict`) starts with what a prediction gives back (ranges, why, films like yours) and is one card, with the optional fields folded under "More details":
- **The film:** genre and theme chips (1–5 each, counted in the label), release month and year, runtime as a box plus a slider, the original language (named by the browser, with film counts) and the US rating.
- **People:** the director and the top-billed cast, typed straight into the box. Suggestions come 250 ms after the last keystroke, with film counts. A pick becomes a chip, numbered for the cast (5 to 10). The last option is always "Use '…' as a new person", for someone with no earlier films in our data.
- **More details:** up to 5 studios and 5 countries, the franchise, the budget in millions of dollars ("Leave it empty and we'll estimate it") and the synopsis with a counter.
- **Prefilled:** 110 minutes, June of next year and English, so a quick "what if" needs fewer clicks.
- **Predict** opens the results page; the answer is already in the query cache, so it isn't asked for twice.

**The results page** (`/predict/result?f=…`) reads the form from the URL, so a result can be shared, refreshed or printed.

![The results page for the Superhero sequel example](docs/images/results-page.png)

In order:
- **Summary:** three cards (box office, budget, audience score) with the expected value and the likely range, money to 2 significant figures and the score to one decimal. Badges show "Rough estimate" (an unusually wide range), "Budget estimated" (no budget in the form: revenue uses the estimate) and where a given budget sits against similar films.
- **The ranges side by side:** budget and revenue on one log money axis, with the break-even zone (2–2.5× the budget) shaded behind revenue, labelled as a rule of thumb, and a sentence saying whether the expected revenue is below, inside or above it; the score on its own 0–10 axis. Screen readers get the same numbers as a list.
- **What drives these estimates:** tabs per target (Revenue first), "Pushes it up" and "Pulls it down" columns with arrows, and 1–3 strength bars plus the word, so nothing depends on colour (blue and orange).
- **Films like yours:** the 5 comparables with posters (lazy), real figures or "not reported", the "why similar" tags and links to their film pages.
- **Notes:** the warnings for this form (new director or actors, a big budget, empty studio or country, a release after 2025), the score note, an always-visible limitations note, and **How accurate is this?**, built from `GET /model-card`: the share of real figures inside the range and the typical miss next to the best simple rule, on the 2019+ test and on 2026 films, for the revenue mode in use.
- **Actions:** edit the inputs, compare variations, best release month, copy the link, print or save as PDF (a print stylesheet: light colours, all three driver tabs, no buttons).

**Compare variations** (`/predict/compare?f=…&v=…`, Day 13) puts your film next to up to 3 variants, each changing exactly one thing, so every difference has one clear cause:

![Compare: a holiday release, an unknown cast and a franchise next to the small indie drama](docs/images/compare-page.png)

- **Presets:** "Holiday release" (December), "Make it a franchise" (opens a search for an existing franchise: a new name would count as a first entry and change nothing), "Double the budget", "Unknown cast" (the same number of new names) and "PG-13 instead of R". A preset that doesn't fit the film is disabled and says why ("Add a budget to the form first", "Already added"), and "PG-13 instead of R" shows only for R films.
- **By hand:** release month or year, runtime, budget (or leaving it out), rating, language, director or franchise. Numbers are checked against the API's limits from `/meta/options` before anything is sent.
- **Each version** shows its three expected values and ranges, the change against your film (×1.3, ×0.3, +0.1 points) and the revenue drivers that moved ("Release timing: now no clear effect (was a moderate drag)"). A change below the model card's threshold is greyed out: "within the uncertainty". Then the revenue ranges sit side by side on one log axis, each with its own break-even zone.
- **In the URL:** the variants live in `?v=`, so a comparison can be shared, and Back undoes the last change. A broken `?v=` keeps the readable variants and says how many it left out. One `POST /predict/compare` answers for all of them; a variant the API refuses is named on its own column.

**Best release month** (on the same page, and linked from the results page) tries your film in every month of its year with one `POST /predict/sweep`. It shows the expected box office and likely range per month on a log axis, highlights your month, marks the best one, and marks the months within the revenue threshold of the best as "about as good". For the small indie drama every month is about as good: December leads October by ×1.3, under the ×1.47 threshold, and the page says the month makes little difference. Screen readers get the same numbers as a table.

![Best release month for the small indie drama](docs/images/month-sweep.png)

While a prediction loads, skeletons keep the layout still. A link without a complete form, a 429, a network failure (with Try again) and a model card that can't load each get their own message; the rest of the page keeps working.

**Rules and errors.** The Zod rules mirror the API's contract and read every limit from `GET /meta/options`, so no number is copied by hand. A bad form is stopped before it is sent: each field says what to fix, and the first one gets the focus. The API's 422 messages land on the same fields; a 429 shows "You're going a bit fast. Try again in a minute", and a network or server error offers a Retry button.

**When things go wrong** (Day 13):

| Situation | What the visitor sees |
| --- | --- |
| A slow answer (a free server waking up) | after 3 s: "Waking up the server, this can take up to a minute on free hosting", on the form, results, compare, browse and film pages |
| The API down or no network | "Can't reach the server…" with Retry; the form keeps everything typed |
| Too many requests (429) | "You're going a bit fast. Try again in a minute" (or "in 3 minutes", from `Retry-After`) |
| An unknown director or actor | the "new person" option in the form and a note on the results |
| A link cut or edited by hand | the readable fields load and a notice names the rest ("runtime, synopsis start from the usual value"), on the form, results, compare and browse pages; an unknown genre in a browse link too |
| An unknown film | "We don't have this film" with search and start page links |
| A page that crashes | "Something went wrong" with Reload, inside the page frame: the header, navigation and footer keep working |
| A slow connection | skeletons with the final layout's size: no layout shift above 0.06 in Lighthouse |

A full reload also returns to the top of the page now: scroll positions are kept per address, so another page's position is never restored.

**Demo helpers:**
- **Three examples** ("Superhero sequel", "Small indie drama", "Horror, unknown cast"). They are the golden forms of `tests/golden/forms.json` with the names added, and a test checks they send exactly those forms.
- **A shareable URL:** the form lives in `?f=` (JSON in base64url), 400 ms after the last change. "Copy link" copies it, and a link opens that form.
- **Draft auto-save** in this browser. On load, a link wins over the draft, and the draft over a fresh form. "Clear form" empties all three.

**Theme:** light and dark with a teal accent. It starts from the system preference and remembers the choice; a script in `index.html` sets it before the page draws, so it doesn't flash.

**Types from the API.** `npm run gen:api` turns the API's OpenAPI schema into `src/api/schema.d.ts` (committed), so an API change fails the type check. For this, the schema now documents every 422 as our `{detail, errors}` shape (`backend/app/schemas/errors.py`) and types the form fields of `/meta/options` (`FieldSpec`). A Python test keeps `frontend/src/test/options.json`, the options the form tests run on, equal to the contract.

**The public side** (Day 12):

| Browse | Film page |
| --- | --- |
| ![Browse: science fiction, 1980–1999, score 7+](docs/images/browse-page.png) | ![The film page of Avengers: Infinity War](docs/images/film-page.png) |

- **Movies** (`/movies`): four curated rows from `src/movies/rows.ts`: Most popular, Top rated (50+ votes), From the 1990s and Biggest box office (2025 $). Each is a browse query, so "See all" opens the same films on `/browse`. On a phone a row scrolls sideways.
- **Browse** (`/browse`, its own page and header link): search as you type (300 ms after the last keystroke, over titles, original titles and plots), genre, years, original language and lowest score, five sorts, and numbered pages. Everything is in the URL, so a link or the back button shows the same films. Filters sit in a sidebar on wide screens and in a drawer on phones, with the same menus as the form (genre, language, score and the sort), active ones show as removable chips, and "no results" offers a button per filter. Small, medium or large posters, or a list, remembered in this browser. A link from before the split (`/movies?q=alien&genre=Horror`) opens `/browse` with the same search.
- **Scores always come with their votes,** e.g. "9.4 (12 votes)". The score filter includes films with few votes; the score sort and the "Top rated" row need 50+, our usable-score rule, so a 10.0 from two votes never tops them.
- **Posters** keep a fixed 2:3 shape while they load (lazily, w342 in grids, w780 on the film page); a film without one gets a placeholder with its title.
- **Film page** (`/movies/:id`): facts, overview, genres and our themes, the score with its votes (and a note under 50), money as reported or in 2025 dollars, key crew, studios, countries and franchise, the cast with initials avatars in a colour derived from the name (our data has no photos), similar films with their "why" tag, and a link to the film on TMDB. The browser tab shows the film's title. An unknown id gets a "We don't have this film" page with search and start page links.
- **"Predict a film like this"** opens the form with the film's genres, themes, runtime, language, US rating, first director and top 5 cast (`filmToForm`, the one place that decides this). The date stays next year's, and the form says which film it started from. Values the form would refuse are dropped; TMDB's "NR" becomes "unrated", and a missing rating is left for the creator to pick.
- **About** (`/about`): the data, how a prediction is made, the accuracy panel from `/model-card`, what the app can't do, and links to the code.

**Bundle:** every page but the start page loads on demand. The start page downloads 159 kB of JavaScript (gzipped, as Lighthouse measures the transfer), `/movies` 173 kB and `/browse` 194 kB in all, and a film page adds 30 kB; the form page adds about 90 kB (Zod, Radix, cmdk), and the compare page about 40 kB (8 kB of its own, the rest shared with the form and results pages).

**Quality pass** (Day 13), on the Docker app (the production build):

| Lighthouse 12 (mobile / desktop) | Performance | Accessibility | Best practices | SEO |
| --- | --- | --- | --- | --- |
| Start page | 88 / 100 | 100 / 100 | 100 / 100 | 100 / 100 |
| Series | 93 / 100 | 100 / 100 | 100 / 100 | 100 / 100 |
| Movies (rows) | 88 / 97 | 100 / 100 | 100 / 100 | 100 / 100 |
| Browse | 86 / 97 | 100 / 100 | 100 / 100 | 100 / 100 |
| Form | 91 / 100 | 100 / 100 | 100 / 100 | 100 / 100 |
| Results | 94 / 100 | 100 / 100 | 100 / 100 | 100 / 100 |
| Compare | 93 / 100 | 100 / 100 | 100 / 100 | 100 / 100 |

- **Fixed after the first run:**
  - SEO went from 83 to 100: a meta description, and a `robots.txt` (nginx answered it with the app's page).
  - Layout shift on the form went from 0.13 to 0 and on compare from 0.29 to 0.06: the loading states now take the final layout's room.
  - Accessibility on the form and results went from 95–97 to 100: the runtime slider's handle gets its name, "More details" became an `h2`, and the inactive tabs and the drivers' blue heading got enough contrast.
  - Also fixed: a pager label that didn't match its text ("Page 3300" vs "3,300"), the first row of posters now loads at once (it is the page's largest paint), and a preconnect to TMDB's image host.
- **The start page, Series, Movies and Browse rows and the form** were measured again after the start page was added; results and compare are from Day 13. On a phone the start page's largest paint is a card's 1200 px collage (about 155 kB) on Lighthouse's slow-4G profile; a smaller phone copy would save about 150 kB.
- **Left as is:** mobile browse scores 86–92 between runs. Its largest paint is a TMDB poster on Lighthouse's slow-4G profile, and the API serves w342 posters where a phone grid would need w185.
- **Keyboard only:** a Playwright script in Edge runs the whole creator flow with Tab, Enter, Space and the arrow keys: an example, Predict, the drivers' tabs, Compare, a preset, a variant made by hand, removing one, then the sweep. Every element it lands on shows a focus mark; the drivers' tab panel had none, and now does.
- **Browsers:**
  - WebKit (Playwright 1.64, Safari's engine) on desktop and as an iPhone 13: all 6 main pages and the whole creator flow pass, with no console errors.
  - On the phone it found a real bug: the sweep's screen-reader table ignored `sr-only`'s 1 px width and made the compare page 471 px wide on a 390 px screen. The table now sits inside an `sr-only` wrapper.
  - Chromium is covered by Edge (Lighthouse and the keyboard run).
  - Playwright's own Firefox build would not start on this Windows machine ("side-by-side configuration is incorrect", usually a missing Visual C++ runtime), so Firefox was not checked automatically.

## Running with Docker

Two containers (`docker-compose.yml`): the backend, with the database, the app's models and the 8-bit text model baked in (`backend/Dockerfile`), and the frontend (`frontend/Dockerfile`), which serves the app on http://localhost:8080 and proxies `/api` to the backend. It needs Docker and the local data and models (`data/movies.db`, `ml/artifacts/final/`, `make model`).

```bash
make docker-build   # build/movies.db (slim copy) + build/context.joblib (prebuilt track records), then both images
make docker-run     # docker compose up -d --wait: returns once both healthchecks pass; the app is on :8080
make smoke          # scripts/smoke.py: the API on :8000 and the app on :8080; make smoke URL=https://... WEB=https://... for the live site
docker compose down
```

**The frontend image** (82.5 MB): Node 24 installs the locked packages, type-checks the app and builds it; then an unprivileged nginx serves it on 8080, as a non-root user with a healthcheck. nginx sends every other path (`/predict`, `/movies/603`) to the app, caches the hashed bundles for a year and the page not at all, gzips, and proxies `/api/` to `backend:8000`. It starts once the backend is healthy.

**What goes into the backend image:**
- the runtime dependencies only, 10 packages: `uv sync --no-default-groups`; `optuna`, `matplotlib`, `scikit-learn` and `onnx` are in the `ml` group, and `pytest` and `jupyter` in `dev`;
- `ml/` and `backend/`;
- `build/movies.db`: `data/movies.db` without the training-only `features` table, VACUUMed, 309 → 220 MB (`scripts/slim_db.py`);
- `build/context.joblib`: History, Companies and Franchises built once (`python -m ml.features.build prebuilt`), stamped with the database's build time and film count, so a file from another build is refused;
- the app's models and comparables index, and the 8-bit MiniLM only (23 MB).

**How it runs:**
- as a non-root user, with one uvicorn worker (the prediction cache and the rate limiter live in its memory);
- a healthcheck on `/api/v1/health`;
- `CORS_ORIGINS` from the environment;
- `MALLOC_ARENA_MAX=2`, and after loading the app hands freed memory back to the system (`malloc_trim`).

**The smoke script** (`scripts/smoke.py`) waits for `/health`, then checks:
- the model version;
- the three golden forms, each middle equal to `tests/golden/predictions.json` to 6 significant figures;
- compare, the 12-month sweep, a bad form's 422, search, the box-office sort and the score filter, a movie page, autocomplete, options and the model card;
- with `--web-url` (`make smoke` passes `WEB`, default :8080): the start page and its two collages (WebP, under 300 kB), the script bundle (gzipped, cached for a year), a client-side route served as the app, and the API through the frontend's proxy.

That is 19 checks. It exits with status 1 on any failure, the same against local Docker and the live URL.

**Measured in Docker Desktop (Linux) on this laptop:**

| | |
| --- | --- |
| Backend image | 984 MB unpacked, 370 MB compressed (Docker Desktop's `docker images` shows their sum, 1.36 GB) |
| Frontend image | 82.5 MB (nginx; the app itself is about 1 MB) |
| Startup until healthy | 8.3 s (models, prebuilt track records, comparables, lookups) |
| Memory after startup | 323 MB (it peaks at 489 MB while loading) |
| Memory after 100 different predictions with synopses | **407 MB** (`docker stats` 385 MiB), under the 450 MB gate |
| Under a 512 MB limit, like Render Free | no out-of-memory kill; startup, 100 predictions and the smoke test pass |
| `/predict`, uncached | median 175 ms, 90th percentile 192 ms |

**How memory came down from 663 MB:**
- **Prebuilt track records:** building History with pandas left about 320 MB freed but kept.
- **Returning freed memory** to the system.
- **Packed name lookups:** History's dict of 344k names took 83 MB.
- **Flat arrays** for Companies and Franchises: dicts of 47k small arrays took 52 MB.
- **Comparables titles as plain strings** instead of 127-character fixed-width text, which took 17 MB.

Every prediction is unchanged: the full features table rebuilt both ways matches the stored one bit for bit, and all 344,445 person and 42,519 company names resolve as before.

**How the image came down from 1.03 GB:**
- **The app stopped loading `optuna` and `scikit-learn`.** `Chain.load` imported `optuna` through `calibrate` and `tune`, and three sklearn imports moved into the training functions that use them.
- **An 8-bit MiniLM for the creator's synopsis** (23 MB instead of 90 MB). Its weights are quantised per output channel. On 1,000 overviews its vectors have a mean cosine of 0.993 with the full model's, and 89% find the same nearest overview; plain int8 gave 0.956 and 71%. Training and the comparables index keep the full model's vectors, and the golden comparables are unchanged.

## Testing

```bash
make test        # everything: 404 tests, about 2 min with the database and models
make test-fast   # skips the slow and real-data tests: 320 tests, about 15 s
make coverage    # everything, with line and branch coverage of ml/ and backend/
```

Two markers (`pyproject.toml`) sort the tests:
- `slow`: the end-to-end, fuzz and real-database time-travel tests;
- `real_data`: the tests that need `data/movies.db` and the app's models. They are also skipped automatically when those files are missing.

| What | Where | What it proves |
| --- | --- | --- |
| End to end | `tests/test_e2e.py`, `tests/fixtures/mini_raw.jsonl` | 213 fake TMDB records (200 films 2005–2020 plus 13 messy ones) go through every real step to answers over HTTP, in about 4 s: each messy record trips its cleaning rule exactly once, the views keep bad money out, the feature columns match `feature_list.json`, tiny models learn and stay monotone in budget |
| Time travel | `tests/test_time_travel.py` | cutting the database at a date leaves every feature of the deleted films unchanged when judged at that date: on the fixture (cut 2017, with a film released on the cut day) and on the real database (cut 2010, 300 films); the vocab, theme keywords and synopsis PCA refitted on train films equal the committed files |
| Fuzzing | `tests/test_fuzz.py` (hypothesis) | 300 random forms to `/predict`, 100 to `/predict/compare` and 60 to `/predict/sweep`, from valid edges to NaN, Infinity, huge or unicode text and non-objects: always a 200 with ordered, finite ranges or a 422 naming a field, never a 500 |
| Logic | `tests/test_sanity.py` | bounds, a monotone budget, invariance, the revenue modes, form edges and matched-pair directions on the real models |
| Golden examples | `tests/test_golden.py`, `tests/test_api_golden.py` | the three golden forms through `predict()` and over HTTP equal the snapshot, in under 400 ms |
| The API | `tests/test_api.py` | every endpoint, the cache, the rate limit, errors, read-only connections, parallel requests, and that the app refuses to start on a model file that doesn't match its manifest; the OpenAPI schema's error shapes and field specs |
| The model card | `tests/test_model_card.py` | the committed `model_card.json` equals one built from the reports now, belongs to the served models, and copies the reports' numbers exactly, the uncertainty thresholds included |
| The frontend | `frontend/src/**/*.test.ts(x)` (Vitest, Testing Library) | the rules against the API's real limits, invalid input blocked, the autocomplete (Enter waits for the suggestions), the examples sending exactly the golden forms, the URL and draft round trips, every API error kind, routes and the theme; the results page on the three golden answers saved from the real API (cards, badges, break-even, notes, comparables, drivers, the accuracy numbers equal to the model card), form → results with one request, the actions, and each failure state; compare and the sweep on real answers saved from the API (every preset changes one field or says why not, the `?v=` round trip and broken variants, "within the uncertainty" on both sides of each threshold, the drivers that moved, a variant the API refuses, 12 months with the best and "about as good"); the edge cases (the waking-up notice after 3 s, the API down, 429, links edited by hand on four pages, a crashing page keeping the navigation); the browse state in the URL, search writing `?q=` once after typing, filters, chips, the no-results buttons, the remembered view, the film page (money toggle, few votes, no poster, 404), "Predict a film like this", the curated rows from their config, and TMDB's logo and notice on every route; the start page's panels and their reduced-motion switch, `/series`, the header's links, `/movies` against `/browse` and old `/movies?…` links reaching `/browse`; 190 tests, 97% of lines and 86% of branches (`npm run coverage`) |

**Fuzzing found one real bug.** A whole-number field (year, month or runtime) sent as NaN or Infinity crashed the contract check with an `OverflowError`, and the API answered 500. JSON parsers, the server's included, accept those values. They now get the usual 422 "must be a number" (`ml/features/contract.py`, with 12 new tests).

**Coverage** (`make coverage`, lines and branches):

| Part | Coverage |
| --- | --- |
| Everything | 78.0% |
| The code the app runs (`backend/`, `ml/predict.py`, `ml/explain/`, `ml/features/`, the models) | 92.2% |
| Data, evaluation, baselines and calibration | 82.3% |
| The one-off scripts (audit, ablation, tuning, the final test run) | 13.3% |

The one-off scripts were each run by hand, and their results are in `reports/`.

## Audit after Day 7

The whole pipeline was reviewed stage by stage against the methods it uses, the app's logic was tested on the real models, and performance was measured again without opening the locked test split. The full write-up with sources is in [`reports/audit.md`](reports/audit.md); the numbers come from `uv run python -m ml.eval.audit` (`reports/audit_metrics.md`).

- **Method:** no leak found. The 182-day lag, strictly-earlier history, time-ordered splits, CQR exactly as Romano et al. (2019) publish it, and TreeSHAP drivers are all standard. Judging a film at the 1st of its month instead of its release day moves the middle by a median of under 0.01.
- **Logic:** 42 rule tests in `tests/test_sanity.py` all pass on the real models:
  - ordered, finite ranges, with the score within 0–10;
  - a higher budget never lowers any part of the revenue range;
  - the synopsis and the order of list fields change nothing;
  - estimated mode equals given mode at the estimated budget, only wider;
  - edge and out-of-form inputs are handled;
  - matched pairs move the way film-economics studies report.
- **Reproduction:** all 13 models refitted from scratch match `reports/metrics.md` to the last digit.
- **Proper scores (2016–18):** the interval score (width plus 10× every miss) drops from B2 to LightGBM:
  - revenue 6.69 → 5.24;
  - budget 5.49 → 3.25;
  - score 2.67 → 2.28.

  LightGBM wins in every backtest fold, and every 95% bootstrap interval of its MAE gain over B2 excludes zero.
- **A fresh holdout, films released in 2026:** this is the first test of the app's own all-data models.

| 2026 films (judged at the 1st of their month) | Films | B2 MAE | App MAE (95% CI) | App R² | App coverage (target 80%) |
| --- | --- | --- | --- | --- | --- |
| Revenue, budget given (182+ days old) | 70 | 1.295 log | 1.052 (0.86–1.25) | 0.56 | 81.4% |
| Budget | 223 | 1.366 log | 0.781 (0.67–0.92) | 0.62 | 81.2% |
| Score (182+ days old) | 190 | 0.731 pts | 0.590 (0.52–0.66) | 0.32 | 73.7% |

The money models hold up on new films; the score ranges under-cover, because young films' TMDB scores are still settling (below).

## Limitations

- **The revenue model is mostly an English-language, post-1980 model.** Only 21% of English films have both budget and revenue (32% among the first 700 per year), and most other languages are under 10%. There are only 286 revenue training films from the 1960s and 471 from the 1970s.
- **Some revenues are incomplete.** 178 training films (2.0%) earned less than 1% of their budget. Some are real flops, but others seem to record only part of the box office, probably the US share (e.g. *Flying Swords of Dragon Gate*, $128k). No rule catches these yet.
- **Local-currency budgets are only caught when they're extreme.** The currency rule flags budgets far above their language's norm. Smaller mistakes sit near the cap: a budget entered in Brazilian reais (about 3.5 to the dollar in 2016) is only around 3.5× too high, and *The Ten Commandments: The Movie* was flagged only narrowly.
- **US certification is missing for 65% of films**, so the creator form has an "unrated/unknown" option (70.5% of films, counting NR).
- **Track-record scores use today's ratings.** An earlier film's score is its current TMDB rating, not its rating when the later film came out; the pull has no rating history.
- **COVID can't be learned from training data.** `covid_period` is always 0 in the train split, because 2020–21 films are all in the test split.
- **Revenue with an estimated budget is less accurate.** When a creator leaves the budget out, the app predicts it first; validation MAE log rises from 1.093 to 1.135 (test: 1.230 to 1.266), and the ranges widen from about 34× to 42× on the test years.
- **Coverage close to 80% overall can hide groups that are far off.** For example, B2 revenue covers 100% of $150M+ films but 72% of films under $10M. LightGBM narrows this to 82–91% on 2016–18, but on the test years it covers only 64% of $150M+ revenue films and 74–77% of $50M+ budgets. `reports/breakdowns.md` and `reports/final_test.md` have the coverage for each group.
- **Big-budget revenue is no better than the simple baseline on the test years.** For $150M+ films from 2019 on, LightGBM's revenue error (MAE log 1.04) is slightly worse than B2's (0.99), and its ranges are too narrow (64% coverage). Why isn't known yet; the test split stays closed, so it can only be studied on newer films.
- **The app's models have only a small test of their own.** They are retrained on 1960–2025 and reuse the ≤2018 corrections and tree counts. The 2019+ results above estimate their accuracy, and the 2026 holdout (70 revenue, 223 budget and 190 score films) confirms the money models; a bigger check needs a pull in 2027.
- **Young films' scores are still settling.** TMDB scores start high, when fans vote first, and drift down. 2026 films under six months old score +0.41 above the app's middle, and those 6–12 months old +0.17, so score ranges cover 60% and 74% of them instead of 80%. The ranges describe a film's settled score, and `predict()` says so in `score.note`.
- **Releases after 2025 look slightly worse the further away they are.** The track record's "years active" keeps growing after the data ends, although no new films can be counted: the same small drama's revenue middle falls from $23M in 2026 to $17M in 2030.
- **Revenue stops rising with the budget above about $300M.** Trees can't extrapolate past the 130 training films with a budget over $250M, so $300M, $400M and $1B give the same revenue. The big-budget warning says so.
- **Coverage is uneven in some groups on 2016–18:** budgets of films under $10M (77%, with 22% cheaper than the low end), and the scores of animated (72%) and romance (74%) films, which are mostly higher than the high end.
- **The revenue and score settings were tuned with the synopsis numbers included and without the budget track record.** The ablation dropped the synopsis afterwards and Day 6 added the budget track record to revenue; the settings were reused without retuning. The budget model was tuned on Day 6 with its saved features, and `make tune` now tunes every model with its saved features.
- **Synopsis meaning doesn't help yet.** MiniLM embeddings reduced to 16 or 32 numbers add nothing beyond genres and themes. Other text features remain an open question.
- **Drivers describe the model, not causes.** "A budget of $40M strongly raises the expected revenue" says what the model leans on for films like this one; spending more would not by itself earn more. The drivers explain the middle prediction only, not the width of the range.
- **Breakouts stay outside the range.** *Get Out* earned $340M against a range of $160K–$59M, even with the all-data models that saw it in training; its drivers (small budget, new director, small studios) describe the typical film like it.
- **Empty optional fields count against a film.** No production country or studio looks like the obscure films in the data that have none (no country: about −38% revenue for a small horror film). `predict()` warns about it.
- **"Predict a film like this" carries only part of a film.** It leaves out the studio, country, franchise, budget and synopsis, and takes the first credited director when there are two (the form has one).
- **Cast and crew have no photos.** The pull didn't fetch people's images, so the film page shows initials avatars.
- **The default browse order is TMDB's popularity on the day of the pull.** It is a trending number, so the first page starts with *Clue* (1985) rather than the best-known films.
- **The rate limit sees the proxy, not the visitor, behind a proxy.** It counts per client IP from the connection. Behind the frontend's nginx in `docker compose`, every visitor shares one count of 30 a minute; on Render (Day 14) it must read `X-Forwarded-For` instead.
- **The examples are dated October 2026 and May 2027,** like the golden forms they send. Once a date has passed, the year list (this year to four years ahead) no longer offers it, though the form still sends it.
- **The Docker image is 984 MB unpacked, above the ~700 MB aim** (370 MB compressed). The Python packages take 441 MB, scipy alone 143 MB: LightGBM imports `scipy.sparse` when it loads, so scipy can't be left out. The 100 MB of precompiled bytecode stays, so startup doesn't recompile everything.
- **Startup peaks at 489 MB.** That is under Render Free's 512 MB, but not by much: a bigger database or model would need another look.
- **The app embeds a synopsis with an 8-bit model, the comparables index holds full-model vectors.** They agree closely (mean cosine 0.993), but for about 1 synopsis in 10 the nearest overview differs, so a comparable can differ from what the full model would pick.
- **Memory measurements depend on the system.** On Windows the same app keeps more freed memory (639 MB after startup before the cuts); `malloc_trim` works on Linux only. The gate is measured in Docker, like the host.
- **Some comparable films are obscure.** *Get Out*'s are small horror films scored about 4.5–6. A tie-break towards well-known films was tried and made the comparables' revenue less like the film's own, so it was dropped.
- **The break-even zone is a rule of thumb.** 2–2.5× the budget assumes cinemas keep about half the box office and marketing costs a large share of the budget on top. It ignores streaming, TV and home sales and each film's own deals, so the results page shows it as a shaded band, not a probability of making money.
- **"Within the uncertainty" is a rule of thumb, not a significance test.** A tenth of the median validation range is a set share, chosen on Day 13, not a measured noise level. Two versions of one film share most of their error, so a smaller change may still be real. A larger one can still be the model's quirk: the unknown-cast variant also moves the themes driver.
- **The month sweep only moves the release month.** Everything else stays as planned. The models know a month's typical effect, not the competition a film would meet that month.
- **Firefox wasn't checked automatically.** Playwright's Firefox build wouldn't start on this machine; Chromium (Edge) and WebKit were. A real phone check is still to do.
- **"Why similar" tags use hand-set cut-offs** (synopsis cosine 0.5, within 2× the budget, about 5 years); they name the parts of the similarity that matched, not a measured reason.
- **Themes depend on TMDB's keywords.** Only 48% of films have a theme, and some keywords are loose: "rape" puts *The Revenant* in "sex and erotica", and "hilarious" puts some action films in "comedy and satire".

## Next steps

- IMDb score (via OMDb) as an alternative score target.
