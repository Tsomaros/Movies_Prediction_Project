# Movie Prediction App

Creators enter a planned movie's parameters and get ranges for **budget**, **revenue** and **audience score**, each with the top factors behind it. The public can browse and search movie information.

Every prediction is a range: a low end (10th percentile), an expected value (50th) and a high end (90th). The ranges are calibrated so that about 80% of real outcomes fall inside them.

**Stack:** Python, pandas, LightGBM, MAPIE, Optuna, ONNX Runtime, SQLite, FastAPI and React (Vite). All data comes from our own TMDB API pull.

## Targets

| Target  | Definition                         | Source field                      | Units                                                  |
| ------- | ---------------------------------- | --------------------------------- | ------------------------------------------------------ |
| Revenue | Worldwide box-office gross         | TMDB `revenue`                    | Nominal USD, plus `revenue_2025` in 2025 dollars       |
| Budget  | Production budget                  | TMDB `budget`                     | Nominal USD, plus `budget_2025` in 2025 dollars        |
| Score   | Average TMDB user rating (0–10)    | TMDB `vote_average`               | Films with at least 50 votes, weighted by log(1 + votes) |

A value of `0` in TMDB's `budget` or `revenue` means "unknown", not zero. See [Cleaning rules](#cleaning-rules).

## Working principles

- **Pre-release inputs only.** Every model input must be something a creator knows before the film exists. Post-release fields (`popularity`, `vote_count`, `vote_average`) are never features.
- **Time-based splits.** Every evaluation uses the same splits, and the test set stays locked until the end of Day 6.

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
make test                  # offline tests, no network needed
make data                  # pull films from TMDB (resumable), build data/movies.db, then the features table
make db                    # rebuild data/movies.db from the raw pull only (about 30 s; drops the features table)
make features              # build the features table (about 1 min; the first run also embeds every overview, about 8 min)
make evaluate              # baselines on validation, breakdowns and backtest -> reports/ (test split untouched)
```

| Folder       | Contents                                         |
| ------------ | ------------------------------------------------ |
| `ml/`        | Data pull, features, models and evaluation; `ml/artifacts/` holds the PCA (committed) and the MiniLM files (not in git) |
| `backend/`   | FastAPI app (later)                              |
| `frontend/`  | React (Vite) app (later)                         |
| `data/`      | Raw pull and database (not in git), CPI table, summaries |
| `tests/`     | Offline tests                                    |
| `notebooks/` | Exploration and check notebooks                  |
| `reports/`   | Evaluation reports from `make evaluate` (committed) |

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

The `features` table in `data/movies.db` has 169 features for every film. `ml/features/feature_list.json` lists each feature's source and which models may use it.

| Group | Features | Notes |
| --- | --- | --- |
| Track record | 24 | Director, and the first 5 billed actors as max, mean and min: earlier films, years active, median earlier log revenue and score shrunk towards the typical film as if they had 4 more average films, earlier franchise films, `is_new` |
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
- An earlier film's revenue and score count only once it is 182 days old.
- The typical film used for shrinkage is built from earlier films only.
- The top-N lists, theme keywords and PCA are fitted on train films (≤2015) only.
- A film counts as a franchise film only if its collection already had an earlier film. A first entry joins a collection only once sequels exist, which would leak its later success.

`notebooks/03_features.ipynb` shows missing values, the strongest single signals and a look at the themes and synopsis numbers.

## Evaluation

Every model goes through one harness, `ml/eval/`. Run `make evaluate` to write `reports/metrics.md`, `breakdowns.md`, `backtest.md` and `metrics.json`; it takes about 5 s.

- **Splits.** Each model is fitted on train (≤2015) and scored on validation (2016–18). The test split (2019+) is locked behind `final=True` and is opened once, at the end of Day 6. The revenue test will be reported both with and without 2020–21.
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

_Day 5._

## Limitations

- **The revenue model is mostly an English-language, post-1980 model.** Only 21% of English films have both budget and revenue (32% among the first 700 per year), and most other languages are under 10%. There are only 286 revenue training films from the 1960s and 471 from the 1970s.
- **Some revenues are incomplete.** 178 training films (2.0%) earned less than 1% of their budget. Some are real flops, but others seem to record only part of the box office, probably the US share (e.g. *Flying Swords of Dragon Gate*, $128k). No rule catches these yet.
- **Local-currency budgets are only caught when they're extreme.** The currency rule flags budgets far above their language's norm. Smaller mistakes sit near the cap: a budget entered in Brazilian reais (about 3.5 to the dollar in 2016) is only around 3.5× too high, and *The Ten Commandments: The Movie* was flagged only narrowly.
- **US certification is missing for 65% of films**, so the creator form has an "unrated/unknown" option (70.5% of films, counting NR).
- **Track-record scores use today's ratings.** An earlier film's score is its current TMDB rating, not its rating when the later film came out; the pull has no rating history.
- **COVID can't be learned from training data.** `covid_period` is always 0 in the train split, because 2020–21 films are all in the test split.
- **The revenue benchmark assumes a known budget.** B2 revenue uses each film's real budget. In the app, the budget is sometimes a prediction (Day 6), which will make revenue predictions less accurate than these numbers.
- **Coverage close to 80% overall can hide groups that are far off.** For example, B2 revenue covers 100% of $150M+ films but 72% of films under $10M. `reports/breakdowns.md` has the coverage for each group.
- **Themes depend on TMDB's keywords.** Only 48% of films have a theme, and some keywords are loose: "rape" puts *The Revenant* in "sex and erotica", and "hilarious" puts some action films in "comedy and satire".

## Next steps

- IMDb score (via OMDb) as an alternative score target.
