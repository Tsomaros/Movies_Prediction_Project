# Decisions

The key choices, what else was on the table, and why. Each day was planned the same way: Claude proposed options, Dimitris chose, and the day's plan document records it (`plan/Movie Prediction App Detailed Plan, Days 1–5.md`, `Days 6–10.md`, `Days 11–16.md`). Changes made during a day are in `PROGRESS.md`. Back to the [README](../README.md).

## Data

| Decision | Alternatives | Why |
| --- | --- | --- |
| **Our own TMDB pull**, the 1,200 most-voted films per year, 1960–2025, all languages (79,199 films) | A Kaggle dataset | Fresh data with credits and recent films, which an honest 2019+ test needs; one source keeps cleaning simple |
| **Score = TMDB `vote_average`** | IMDb's score via OMDb | It comes in the same API call; IMDb is a next step |
| **Keep every released film;** bad money becomes NULL and suspect money is flagged | Drop incomplete films | Browse pages and the score model still need them; each model gets its own training view |
| **New and upcoming films merged into `movies.db`** by a background job every 6 hours, in one transaction, films after 2025 only (V1.3) | A second small `fresh.db` read beside it through views (V1.2); a nightly redeploy; the same films in Neon; live TMDB rows with a popup (tried and dropped: second-class, with no film page, lists or notes) | One movies database is simpler to explain, and the views and the two-table search go away; they are ordinary films, so every page, list, rating, note and search works; the year rule keeps every model's data unchanged; the first write copies the 298 MB file into the container's writable layer (about 1 s in Docker, page cache only) |
| **Films listed or noted by any user are kept up to date too**, outside the windows (still only films dated after 2025) | Only the two windows | A watchlisted new film would vanish from *My movies* when it leaves the window or the container restarts |
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

## V1.5: Wikidata budgets and box office (not kept)

| Decision | Alternatives | Why |
| --- | --- | --- |
| **Tried:** fill missing TMDB budgets and box office from Wikidata (worldwide box office only, 11 currencies turned into dollars with World Bank rates), retune and retrain as v2 | Keeping TMDB money only | 1,649 budgets and 944 revenues filled, 0 replaced, 7,562 confirmed, 228 films disagreeing by 3× or more; the revenue training view grew from 10,421 to 11,036 films |
| **Kept rule:** v2 had to beat v1 on revenue on the same films, on validation (2016–18) and on the backtest mean, with coverage in 77–83%; budget and score no worse than v1's backtest std | Comparing all films | The new films are a different, harder mix; only the same films compare the models |
| **v2 rejected; the app stays on v1** | Keeping v2 for its better budget | Revenue on 875 shared validation films: MAE log 1.101 against v1's 1.090 (backtest mean 1.113 against 1.118, coverage 82.3% against 83.8%). Budget improved (0.586 against 0.604) and score stayed the same (0.497 against 0.496), but revenue is the headline number. The learning curve also flattened: v2's revenue MAE was 1.135 at 85% of the train films and 1.133 at 100%, so more films of this kind don't help. Numbers in `reports/v2_compare.md` and `reports/v2/learning_curve.md` (v1's in `reports/v1/`) |
| **The code stays, the data is parked** | Deleting it | `ml/data/wikidata.py`, `fx.py`, `wikidata_money.py` and `data/fx_rates.csv` stay. The pull is in `data/raw/v15/`, outside `make db`'s default path, so a rebuild gives v1; `uv run python -m ml.data.build_db --wikidata data/raw/v15/wikidata_money.jsonl` would try it again |

## Release-plan spikes (not kept)

Four throwaway spikes on branch `spike/release-plan` (never merged; reports in `spikes/release_plan/RESULT*.md` there). Question: does how a film is released, read from TMDB's `/movie/{id}/release_dates`, help the models? Each variant was trained from scratch with v1's frozen settings (no retuning, uncalibrated) on the same films as today's model, with paired bootstrap CIs (2,000 resamples).

| Decision | Alternatives | Why |
| --- | --- | --- |
| **Why release plan:** an error analysis of v1's revenue predictions on 2016–18 | A bigger model; more films | 54 of 886 validation films (6%) earned under 5% of their budget and caused 23% of the total error (MAE log 4.1 each); many were small or video-on-demand releases the form can't describe. Tuning, embeddings and more films had each moved revenue by only 0.01–0.03 |
| **Spike 1: country count and "release plan" rejected as leaks** | Shipping the −0.15 | Adding the number of countries with a theatrical release cut revenue MAE log from 1.093 to 0.943 (backtest 1.124 → 0.970) and became the #1 feature. But it tracks `vote_count` (Spearman 0.84) more than revenue (0.67): hits are released in more countries *because* they did well, and TMDB records popular films more completely. A creator can't give that number. Wide/limited/digital-first barely mattered (94.5% of films are "wide") |
| **Spikes 2–3: the planned US opening is a real but small signal** | Building it now | The type of the film's *first* US theatrical entry within ±7 days of release (wide / limited, missing if none) lowers revenue MAE log by 0.025 on films with a US opening (backtest −0.025, CI −0.040 to −0.012), the same when trained only on those films, so it isn't the "missing" signal. Over all films with honest form answers: 1.093 → 1.076 (about 1.5%). Later US entries were excluded on purpose: a third of "limited" films widened later, and late pickups follow success |
| **Not built: the gain isn't confirmed** | A v3 with a "US release" form field | On the 2026 holdout (70 films, models fitted on ≤2018) the change is +0.007 (CI ±0.05) and wide films lean worse. 1.5% doesn't pay for a pipeline pull, a form field, retuning and recalibration, and a model with no test-set number (the 2019+ test can't be opened again). **Revisit in mid-2027**, when the 2026 holdout has a few hundred films older than 182 days: if B2w beats v1 by about 0.02 there, build it as a minor version with the form question "planned US opening" |
| **Spike 4: no gain for the score model** | — | With the planned US opening the score MAE moves by −0.001 to +0.003 points on films with an entry (every CI includes 0), and the 2026 holdout (190 films) is slightly worse. Wide and limited films score the same on average (6.31 against 6.36). The only significant change (−0.002 in the backtest) came from films with *no* US entry, an obscurity signal a form never sends. Late US pickups score 0.4 points higher, an outcome the ±7-day window rightly removes |
| **Conclusion: the models stay on v1** | More model work | Three independent tries (more films, Wikidata money, release plan) moved revenue by 0–1.5% and score by nothing. What's left is how a film turns out after release, plus wrong labels (*The Spy Gone North* has $4,073 on TMDB but earned tens of millions in Korea). The ranges already show that uncertainty |
