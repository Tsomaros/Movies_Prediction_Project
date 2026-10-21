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

- **Source:** our own TMDB API pull. The 700 most-voted films per year, 1960–2025, in all languages (about 46,000 films).
- **Per film:** basic info, genres, overview, runtime, budget, revenue, collection, US certification, keywords, production companies and countries, the top 15 cast, and key crew (director, writers, producers, composer, cinematographer, editor).
- **Raw output:** `data/raw/tmdb_movies.jsonl`. It is not committed to git.
- **Database:** `data/movies.db` (SQLite), built from the raw pull by `make db`. It is not committed to git either. It holds the cleaned films, people, genres, companies, keywords and collections, full-text search on titles and overviews, and these views:
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
cp .env.example .env       # then paste your TMDB API Read Access Token into .env
make test                  # offline tests, no network needed
make data                  # pull films from TMDB into data/raw/ (resumable), then build data/movies.db
make db                    # rebuild data/movies.db from the raw pull only (about 20 s)
```

| Folder       | Contents                                         |
| ------------ | ------------------------------------------------ |
| `ml/`        | Data pull, features, models and evaluation       |
| `backend/`   | FastAPI app (later)                              |
| `frontend/`  | React (Vite) app (later)                         |
| `data/`      | Raw pull and database (not in git), CPI table, summaries |
| `tests/`     | Offline tests                                    |
| `notebooks/` | Exploration and check notebooks                  |

## Cleaning rules

All rules live in `ml/data/clean.py` and are tested in `tests/test_clean.py`. **Every released film is kept** for browsing; bad values become NULL, and suspect money is flagged rather than deleted. Each model trains on its own view. The counts are from the 2026-10-21 pull (46,199 films), and every build stores them in the database's `meta` table.

| Rule | What happens | Films affected |
| --- | --- | --- |
| Status | Only films with status "Released" are kept | 0 dropped |
| Duplicate ids | The latest pull (`pulled_at`) is kept | 0 dropped |
| Text | Whitespace trimmed and empty text becomes NULL; a missing title falls back to `original_title` | 0 titles |
| Release date | Parsed into `release_date`, `year` and `month`; `split` is set from the year | 0 unparseable |
| Runtime | 0 or over 600 minutes → NULL | 218 |
| Placeholder money | Budget or revenue below $1,000 → NULL (TMDB shorthand such as `7` meaning $7M) | 87 budgets, 96 revenues |
| Inflation | `budget_2025` / `revenue_2025` = nominal × CPI(2025) / CPI(release year) | All films with money |
| Low ratio | Revenue below 0.0001 × budget → `money_suspect` (token box office, e.g. streaming releases) | 2 |
| Currency | A non-English budget above 3× the 99th percentile of its language's *other* budgets (in 2025 dollars) → `money_suspect`. Languages with fewer than 30 budgets are compared with all other non-English budgets | 2 |
| Still earning | Released less than 182 days before the pull → `revenue_incomplete` | 0 |
| COVID | Released 2020–2021 → `covid_period` | 1,400 |
| Score | 0 votes → score NULL; `score_ok` needs at least 50 votes; `score_weight` = log(1 + votes) | 26,296 `score_ok` |

There is no rule for very *high* revenue-to-budget ratios. The only films above 1,000× were real micro-budget hits (*The Blair Witch Project*, *Paranormal Activity*).

| Training view | Films included | Train / validation / test |
| --- | --- | --- |
| `v_train_revenue` | Budget and revenue known, not `money_suspect`, not `revenue_incomplete` | 7,587 / 796 / 1,293 |
| `v_train_budget` | Budget known, not `money_suspect` | 9,835 / 955 / 1,584 |
| `v_train_score` | `score_ok` | 19,296 / 2,100 / 4,900 |

`notebooks/02_clean_check.ipynb` re-checks every rule and the view sizes after each build.

## Evaluation

_Day 4._

## Results

_Day 5._

## Limitations

- **The revenue model is mostly an English-language, post-1980 model.** Only 32% of English films have both budget and revenue, and most other languages are under 10%. There are only 271 revenue training films from the 1960s and 458 from the 1970s.
- **Some revenues are incomplete.** 151 training films (1.8%) earned less than 1% of their budget. Some are real flops, but others seem to record only part of the box office, probably the US share (e.g. *Flying Swords of Dragon Gate*, $128k). No rule catches these yet.
- **Local-currency budgets are only caught when they're extreme.** The currency rule flags budgets far above their language's norm. Smaller mistakes sit near the cap: a budget entered in Brazilian reais (about 3.5 to the dollar in 2016) is only around 3.5× too high, and *The Ten Commandments: The Movie* was flagged only narrowly.
- **US certification is missing for 52% of films**, so the creator form needs an "unrated/unknown" option.

## Next steps

- IMDb score (via OMDb) as an alternative score target.
