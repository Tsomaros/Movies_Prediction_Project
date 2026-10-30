# Decisions

The key choices, what else was on the table, and why. Each day was planned the same way: Claude proposed options, Dimitris chose, and the day's plan document records it (`plan/Movie Prediction App Detailed Plan, Days 1–5.md`, `Days 6–10.md`, `Days 11–16.md`). Changes made during a day are in `PROGRESS.md`. Back to the [README](../README.md).

## Data

| Decision | Alternatives | Why |
| --- | --- | --- |
| **Our own TMDB pull**, the 1,200 most-voted films per year, 1960–2025, all languages (79,199 films) | A Kaggle dataset | Fresh data with credits and recent films, which an honest 2019+ test needs; one source keeps cleaning simple |
| **Score = TMDB `vote_average`** | IMDb's score via OMDb | It comes in the same API call; IMDb is a next step |
| **Keep every released film;** bad money becomes NULL and suspect money is flagged | Drop incomplete films | Browse pages and the score model still need them; each model gets its own training view |
| **2026 films in the database but never in a model** (`MODEL_DATA_MAX_YEAR = 2025`) | Retraining on them, or leaving them out of the app | The app shows what came out this year; the models, their track records and the model card stay exactly as tested, which a snapshot of the training data proves |
| **2025 dollars from a committed CPI table** (FRED CPI-U, 1960–2025) | The `cpi` Python library | Offline and fixed, so a rebuild gives the same numbers |
| **One SQLite database** for the app and the pipeline | A server database | Read-only at serve time, baked into the image, nothing to run |

## Features

| Decision | Alternatives | Why |
| --- | --- | --- |
| **Pre-release inputs only;** the creator form (`ml/features/contract.py`) defines every allowed input | Using popularity or vote counts | A creator doesn't have them; they would leak the answer |
| **One feature function** for training and the app; a training film is judged at its release date, a creator's at the 1st of its month | Separate training and serving code | Training and serving can't drift apart |
| **Track records from earlier films only,** shrunk toward the average as if each person had 4 extra average films | Raw averages | Leak-safe, and one hit doesn't make a "star" |
| **Keywords grouped into 27 named themes** | Raw keywords | Creators can pick them from a list |
| **Synopsis embedded with MiniLM through ONNX** (an 8-bit copy in the app) | A PyTorch model | No PyTorch anywhere; 23 MB in the image |
| **The synopsis was then dropped from every model** | Keeping 16 or 32 embedding numbers | The ablation showed no gain beyond genres and themes |

## Evaluation

| Decision | Alternatives | Why |
| --- | --- | --- |
| **Time splits:** train ≤2015, validation 2016–18, test 2019+, plus a three-fold rolling backtest | Random splits | Future films are what the app predicts; random splits leak the future |
| **The test split locked in code and opened once** (Day 6), no model changes after | Checking the test set while building | Repeated peeking makes test numbers dishonest |
| **Baselines B0–B2 through the same harness;** B2 is a tough rule (budget × genre multiple, director's record) | Comparing only with a global average | A credible benchmark shows whether the model is worth it |
| **MAE on log money for selection, "within 2×" as the headline** | RMSE, R² | Stable across budget sizes; easy to explain |
| **Revenue reported with and without 2020–21** | One number | The test years include the COVID collapse |
| **A time-travel test:** features from a database cut at a date must equal the full database's for the deleted films | Trusting the code | The strongest proof of no leakage |

## Models

| Decision | Alternatives | Why |
| --- | --- | --- |
| **LightGBM quantile models** (10th, 50th, 90th) per target | One point model plus a fixed error band | A range per film, one method everywhere |
| **Our own conformalized quantile regression** to calibrate the ranges, learned on out-of-fold predictions from backtest folds 1–2 | MAPIE | Plain quantile ranges are too narrow; a short function, no dependency, easy to test; 2016–18 stays an honest check |
| **Revenue: a monotone Huber middle model plus quantile models of its residuals** | Monotone quantile models | LightGBM refuses monotone constraints on quantile objectives; raising the budget must never lower revenue |
| **One revenue model with two corrections,** "budget given" and "budget estimated" from the budget model | Two revenue models | Ranges widen automatically when the budget is a guess |
| **The score model never sees the budget** | Using it | Keeps the score independent of the money chain |
| **Optuna, 15 minutes per target, on folds 1–2; tree count by early stopping there** | Tuning on validation | Validation never helps fit the model |
| **The app's models retrained on 1960–2025** with the same settings and corrections | Serving the ≤2018 test models | The most data for real predictions; the 2026 holdout checks them |
| **`reports/experiments.csv` as the experiment log** | MLflow | Enough for three weeks |

## Explanations

| Decision | Alternatives | Why |
| --- | --- | --- |
| **Drivers from LightGBM's `pred_contrib`,** grouped into 12 creator-friendly groups and written as sentences | The `shap` package | Built in, nothing extra in the image; users never see a raw feature name |
| **Strength as strong / moderate / slight,** no exact amounts | Exact contributions | Honest about the approximation |
| **Five comparable earlier films,** money films first | No comparables | Creators think in comparables |
| **A "rough estimate" label** when a range is too wide to be useful | Hiding wide ranges | Flags exactly the uncertain predictions |

## Backend and app

| Decision | Alternatives | Why |
| --- | --- | --- |
| **FastAPI, plain `sqlite3`, read-only connections** | An ORM | Fastest and simplest; a bug can't corrupt the data |
| **One uvicorn worker,** a prediction cache and a per-IP rate limit (30 a minute) | Several workers | Each worker loads every model; the host has 512 MB |
| **A memory gate: under 450 MB after 100 predictions** | Measuring at the end | Problems found on Day 9, not on deployment day; met by packing the data (1,236 → 407 MB) |
| **TypeScript types generated from the API's schema** | Hand-written types | API changes fail at compile time |
| **Tailwind + shadcn/ui, TanStack Query, React Hook Form + Zod** | A component framework | Full control of the look; one pattern for loading, errors and validation |
| **A break-even band at 2–2.5× the budget,** labelled a rule of thumb | A probability of profit | Answers "will it make money?" without a made-up number |
| **"Within the uncertainty":** a change smaller than a tenth of the typical range is greyed out | Showing every difference | The app says when a change doesn't matter |

## Accounts (Day 14)

| Decision | Alternatives | Why |
| --- | --- | --- |
| **Two databases:** movies in read-only SQLite, user data in Postgres | User data in the SQLite file | Render Free wipes the container's disk on every sleep and redeploy |
| **Neon's free Postgres in Frankfurt** | Supabase (pauses after 7 idle days), Render Postgres (expires after 30 days) | A permanent free tier with no card |
| **One shared demo account** with one-click login, write limits, caps and a nightly reset | Sign-ups | Interviewers get in with one click; the shared data stays tidy |
| **Sessions as a hashed random token,** argon2id at OWASP's minimum | Signed cookies | Logout really ends a session; argon2's default 64 MB is too much for 512 MB |
| **The rules in the database** (one list per film, a rating only when watched) | Checks in the API only | The API can't create bad states |

## Deployment (Day 15)

| Decision | Alternatives | Why |
| --- | --- | --- |
| **Render Free, Frankfurt** | Render Starter ($7/month), Google Cloud Run (needs a card), Hugging Face Spaces (Docker needs a paid plan), Fly.io and Railway (no free tier) | The only free option that runs our container without a card |
| **One image: the API serves the React app** | A separate nginx container | One URL, no CORS, one thing to deploy |
| **A prebuilt private image** on GitHub's registry, deployed with `make deploy` | Render building from GitHub | 470 MB of data and models aren't in git; private keeps the TMDB-derived database from being downloadable |
| **A daily smoke check from GitHub Actions** | Uptime pings every 5 minutes | Any ping wakes the free service, so frequent ones are a keep-alive |
| **The per-IP limits read `CF-Connecting-IP`** | `X-Forwarded-For` | Render appends to a visitor's own `X-Forwarded-For`, so forged values got past the limits; Cloudflare sets `CF-Connecting-IP` and refuses it from clients |
| **Sentry for errors only,** no personal data | No error reporting, or tracing too | Know about failures; the session cookie never leaves the server |
