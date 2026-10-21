# Movie Prediction App

Creators enter a planned movie's parameters and get ranges for **budget**, **revenue** and **audience score**, each with the top factors behind it. The public can browse and search movie information.

Every prediction is a range: a low end (10th percentile), an expected value (50th) and a high end (90th). The ranges are calibrated so that about 80% of real outcomes fall inside them.

**Stack:** Python, pandas, LightGBM, MAPIE, Optuna, ONNX Runtime, SQLite, FastAPI and React (Vite). All data comes from our own TMDB API pull.

## Targets

| Target  | Definition                         | Source field                      | Units                                                  |
| ------- | ---------------------------------- | --------------------------------- | ------------------------------------------------------ |
| Revenue | Worldwide box-office gross         | TMDB `revenue`                    | Nominal USD as pulled; 2025 dollars added on Day 2     |
| Budget  | Production budget                  | TMDB `budget`                     | Nominal USD as pulled; 2025 dollars added on Day 2     |
| Score   | Average TMDB user rating (0–10)    | TMDB `vote_average`               | Only films above a minimum vote count (set on Day 2)   |

A value of `0` in TMDB's `budget` or `revenue` means "unknown", not zero. The cleaning rules are set on Day 2.

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
make data                  # pull films from TMDB into data/raw/ (resumable)
```

| Folder       | Contents                                         |
| ------------ | ------------------------------------------------ |
| `ml/`        | Data pull, features, models and evaluation       |
| `backend/`   | FastAPI app (later)                              |
| `frontend/`  | React (Vite) app (later)                         |
| `data/`      | Raw pull (`data/raw/`, not in git) and summaries |
| `tests/`     | Offline tests                                    |
| `notebooks/` | Exploration and check notebooks                  |

## Cleaning rules

_Day 2._

## Evaluation

_Day 4._

## Results

_Day 5._

## Limitations

_To be filled in as we go._

## Next steps

- IMDb score (via OMDb) as an alternative score target.
