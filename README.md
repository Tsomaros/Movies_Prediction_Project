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

- Free for non-commercial use with attribution. The TMDB logo is less prominent than our own branding.
- Data is not cached for more than six months.
- The client stays at about 20 requests/second, well under TMDB's per-IP limit.

> This product uses the TMDB API but is not endorsed or certified by TMDB.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/) and GNU make. uv installs Python 3.11 for the project.

```bash
make setup                 # create .venv and install locked dependencies
make model                 # download the MiniLM text model (about 90 MB, once)
cp .env.example .env       # then paste your TMDB API Read Access Token into .env
make test                  # offline tests, no network needed (about 80 s; the golden and sanity tests need the database and models, about 7 s without)
make data                  # pull films from TMDB (resumable), build data/movies.db, then the features table
make db                    # rebuild data/movies.db from the raw pull only (about 30 s; drops the features table)
make features              # build the features table (about 1 min; the first run also embeds every overview, about 8 min)
make tune                  # tune the LightGBM settings on backtest folds 1-2 (15 min per target, 45 min in all)
make train                 # calibrate the ranges, then fit and save all three models to ml/artifacts/ (about 5 min)
make evaluate              # baselines and LightGBM on validation, breakdowns and backtest -> reports/ (test split untouched)
uv run python -m ml.models.rough           # the rough-estimate cut-offs (fitted once on Day 6, then frozen)
uv run python -m ml.eval.final test        # the one-time test run (done on Day 6; refuses to run again)
uv run python -m ml.eval.final all-data    # retrain the app's models on 1960-2025 -> ml/artifacts/final/ (about 1 min)
uv run python -m ml.explain.comparables    # the comparable-films index -> ml/artifacts/final/comparables.npz (3 s)
uv run python -m ml.predict manifest       # checksums of the app's model files -> ml/artifacts/final/manifest.json
```

| Folder       | Contents                                         |
| ------------ | ------------------------------------------------ |
| `ml/`        | Data pull, features, models and evaluation; `ml/artifacts/` holds the PCA and the models' settings, calibration and metadata (committed), the MiniLM files and the trained `.joblib` models (not in git; `make model`, `make train`); `ml/artifacts/final/` holds the app's all-data models, their `manifest.json` and the comparables index; `ml/explain/` and `ml/predict.py` turn them into explained predictions |
| `backend/`   | FastAPI app (later)                              |
| `frontend/`  | React (Vite) app (later)                         |
| `data/`      | Raw pull and database (not in git), CPI table, summaries |
| `tests/`     | Offline tests                                    |
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

`ml/explain/comparables.py` returns 5 earlier films like the planned one, with their real budget, revenue (2025 $) and score. The pool is the 33,077 films with a usable score; only films released before the planned date can be returned, and of the 50 most similar, those with a reported budget or revenue come first. Similarity is a weighted average of genres (0.3), themes (0.2), synopsis (0.3, cosine on the MiniLM vectors, skipped without a synopsis), era (0.1), budget level (0.2, the creator's budget or the budget model's estimate) and the same original language (0.1). The index (`ml/artifacts/final/comparables.npz`, 26 MB, not in git) is built by `uv run python -m ml.explain.comparables`; a query takes about 8 ms.

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
- **Some comparable films are obscure.** *Get Out*'s are small horror films scored about 4.5–6. A tie-break towards well-known films was tried and made the comparables' revenue less like the film's own, so it was dropped.
- **Themes depend on TMDB's keywords.** Only 48% of films have a theme, and some keywords are loose: "rape" puts *The Revenant* in "sex and erotica", and "hilarious" puts some action films in "comedy and satire".

## Next steps

- IMDb score (via OMDb) as an alternative score target.
