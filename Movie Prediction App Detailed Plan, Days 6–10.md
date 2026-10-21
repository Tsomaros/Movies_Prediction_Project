# Movie Prediction App: Detailed Plan, Days 6–10

Oct 21, 2026 · @Dimitris

## Overview

Week two (Days 6–10) takes the project from calibrated revenue and score models to a working app: a creator fills in a form in the browser and gets budget, revenue and score ranges back from a containerised API. Each day was planned the same way as week one: Claude researched and proposed options, Dimitris chose, and a day was only closed once he approved it.

**What week two adds**

- **Day 6:** the budget model, honest revenue ranges when the budget is estimated, and the one-time final test run.
- **Day 7:** plain-English explanations, comparable past films, and a single `predict()` entry point.
- **Day 8:** a versioned FastAPI backend that the frontend can be built against without further changes.
- **Day 9:** end-to-end and time-travel tests, and a Docker image with data and models baked in.
- **Day 10:** the React + TypeScript app and the creator form.

**Principles carried over from week one:** inputs are only things a creator knows before release; every evaluation is time-based; the test set is opened once; one feature function serves training and the app.

## Day 6: Budget model, the chain, and the final test run

Day 6 ends with a calibrated budget model, revenue ranges that widen honestly when the budget is estimated, and one locked-in test result for all three models.

### Decisions

| Topic               | Decision                                                                                                                                    | Why                                                                   |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Budget model        | Same recipe as Day 5: three quantile models, Optuna on backtest folds 1–2 (tree count from early stopping), our own CQR calibration on folds 1–2, same harness | Shared code and a fair comparison                                     |
| Budget inputs       | Every allowed feature except the synopsis numbers (`DEFAULT_DROP`), with one ablation row adding them back                                 | Synopsis didn't help revenue or score on Day 5; the row confirms it for budget |
| Budget track record | Leak-safe earlier budgets for director, actors, company and franchise; also tried in the revenue model and kept only if both validation and the backtest improve; not added to the monotone constraints | Earlier budgets predict budget better than earlier revenue; same bar as the Day 5 ablation |
| Budget track record in the models | Kept in the revenue model (validation MAE log −0.020, backtest −0.006, same tuned settings); the score model stays without it | Decided by Dimitris after the trial; it passed the validation + backtest rule |
| The chain           | One revenue model, two calibrations: "budget given" and "budget estimated"                                                                  | Ranges widen automatically when budget is estimated; cheap and honest |
| Chain calibration   | "Estimated" mode is calibrated on folds 1–2: each fold trains a budget model on its own train years, and the revenue model's out-of-fold predictions use those predicted budgets | 2016–18 is never used to fit, stop or calibrate, so coverage in both modes stays an honest check |
| ≤2018 models        | Retrained on ≤2018; their corrections come from out-of-fold predictions on all three folds (2010–18)                                         | More calibration films, and the Day 5 2016–18 revenue coverage (83%) was slightly cautious |
| All-data models     | Retrained on ≤2025 for the app with the ≤2018 corrections and tree counts reused; stated in Limitations                                    | No later years are left to calibrate on                               |
| Retuning            | Revenue and score are not retuned without synopsis                                                                                          | Tuning gained only about 1% on Day 5                                  |
| Rough estimate      | Per-prediction label, starting at high ÷ low > 4×, adjusted on validation                                                                   | Flags exactly the predictions that are uncertain                      |
| Rough-estimate rule | Revenue and budget only: high ÷ low above the 75th percentile of 2016–18 widths, rounded (revenue 81×, budget 12×), frozen in `ml/artifacts/rough_estimate.json`; score gets no label | 4× flagged 98% of revenue and 93% of budget ranges; score widths barely predict error (Spearman 0.09). Decided by Dimitris |
| Budget comparison   | Always shown, even when the creator gives a budget                                                                                          | A useful sanity check at almost no cost                               |
| Test set            | Opened once; no model changes after seeing it; results reviewed together                                                                    | Keeps the numbers credible                                            |

### Tasks

0. **Update the plan document (15 min).** Our own CQR on folds 1–2 instead of MAPIE on 2016–18, the chain calibrated on folds 1–2, ≤2018 corrections from all three folds, all-data models reuse them, no synopsis in the budget model, no retune.
1. **Budget track-record features (45 min).** Median earlier budget (2025 $) for the director, the actors (max/mean/min), the company and the franchise; shrunk towards the average; leakage tests extended. Tried in the revenue model as an ablation row.
2. **Budget model (1.5 h).** Three quantile models on log budget from `v_train_budget` in `ml/models/train.py`; every allowed feature except budget and synopsis; Optuna 15 min on folds 1–2; CQR correction from fold 1–2 out-of-fold predictions; evaluated against B0–B2 on validation, breakdowns and the backtest; ablation row with synopsis.
3. **Chain (1 h).** Calibrate the revenue model twice. For "estimated" mode, folds 1–2 train a budget model on the fold's train years and feed its predicted budgets into the revenue model's out-of-fold predictions; the correction comes from those. Coverage in both modes checked on 2016–18, where the budget comes from the budget model trained on ≤2015. `predict_revenue(features, budget=None)` picks the mode.
4. **Rough-estimate label (30 min).** Record the share of validation films labelled and how much larger their errors are.
5. **Budget comparison (15 min).** "Similar films usually cost $X–Y" returned whenever a budget is given.
6. **Freeze and final test run (1.5 h).**
   1. Freeze features, settings, calibrations and the rough rule; tag `pre-test`.
   2. Retrain all three models on ≤2018 with the frozen settings; take every correction (both revenue modes, budget, score) from out-of-fold predictions on all three folds.
   3. One `final=True` run on 2019+: revenue in both modes, with and without 2020–21; budget; score; all metrics, coverage and breakdowns against B0–B2.
   4. Write the numbers into the README immediately; disappointments go into Limitations.
   5. Retrain on all data (≤2025) for the app, reusing the ≤2018 corrections and tree counts; tag `final-models`.
7. **Tests (45 min).** Budget ranges ordered; estimated mode never narrower than given mode; `final=True` only in the final-run script; final artifacts reload identically.
8. **Wrap-up (30 min).** Test results and limitations in the README, `PROGRESS.md`, commit.

**After the test run:** results reviewed together. The review can change what is reported and explained, not the models.

**Done when** the test results are in the README exactly as measured and the final all-data models are saved for the API.

## Day 7: Explanations and packaging

Day 7 ends with one `predict()` call that returns budget, revenue and score ranges, the top drivers for each in plain English, and 5 comparable films, in under 400 ms.

### Decisions

| Topic                  | Decision                                                                                                               | Why                                                                     |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| How to compute drivers | LightGBM's built-in `pred_contrib` on each 50th-percentile model, rescaled to add up to the prediction                 | No `shap` package in the app; quantile models don't add up on their own |
| How to show them       | Rank and direction prominent; size as strong / moderate / slight, no exact amounts                                     | Honest about the approximation, still informative                       |
| Strength thresholds    | Budget/revenue: strong ≥ 25%, moderate 10–25%, slight < 10%. Score: strong ≥ 0.3 stars, moderate 0.1–0.3, slight < 0.1 | Starting point, tuned in the notebook                                   |
| Feature groups         | Raw features merged into creator-friendly groups                                                                       | Users never see names like `pca_emb_7`                                  |
| Top drivers            | Top 5 per target (budget, revenue, score)                                                                              | What drives budget isn't what drives score                              |
| Comparable films       | 5 similar past films with real budget, revenue, score; prefer known money, fall back to "not reported"                 | Creators think in comparables; the biggest UX win of the week           |
| Speed                  | Under 400 ms per prediction                                                                                            | The form should feel instant                                            |

### Feature groups

| Group                       | Raw features merged                               |
| --------------------------- | ------------------------------------------------- |
| Story (synopsis)            | the 16 embedding components                       |
| Genre                       | all genre columns                                 |
| Themes                      | all theme columns                                 |
| Director's track record     | earlier films, revenue, score, budget, experience |
| Cast's track record         | actor max/mean/min columns                        |
| Franchise                   | `is_franchise` and earlier collection results     |
| Budget                      | log budget (marked "estimated" in estimated mode) |
| Release timing              | month, summer/holiday flags, year                 |
| Studio / country / language | their columns                                     |
| Runtime, certification      | as-is                                             |

### Tasks

1. **Drivers (1.5 h), `ml/explain/drivers.py`.** `pred_contrib`, rescaling, grouping, strength labels.
2. **Feature groups (45 min).** The mapping above.
3. **Plain-English sentences (1 h).** One template per group, filled with the creator's values ("Releasing in **December**…"); top 5 per target, split into "pushing up" and "pushing down".
4. **Comparable films (1.5 h), `ml/explain/comparables.py`.** Nearest past films by genre, themes, synopsis embedding, era and budget level; only films released before the hypothetical date; TMDB ids for links; precomputed index loaded at startup.
5. **`predict()` package (1.5 h), `ml/predict.py`.** Validate → features → budget → revenue (given or estimated mode) → score → drivers → comparables. Output: three ranges, revenue mode, rough flag, budget comparison, drivers, comparables, warnings, model version. Artifacts in one folder with `manifest.json`.
6. **Tests (1 h).** Golden examples (franchise blockbuster, small drama, unknown cast); drivers add up and never expose raw names; comparables never from the future; under 400 ms.
7. **Sanity notebook (45 min), `07_explanations.ipynb`.** Drivers and comparables for famous films.
8. **Wrap-up (15 min).** `PROGRESS.md` and commit.

**Done when** `predict()` returns the full output for any valid input within 400 ms and the golden tests pass.

## Day 8: FastAPI backend

Day 8 ends with a complete, versioned API that the React app can be built against on Days 10–13 without further backend changes, and that's easy to extend with new endpoints later.

### Decisions

| Topic            | Decision                                                                   | Why                                                                    |
| ---------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Endpoints        | The list below, under `/api/v1`; more will be added in the future          | Covers the form and the public pages; versioning protects the frontend |
| Compare endpoint | Built now, accepting up to 3 variants in one call                          | Cheap while predict is fresh; Day 13 becomes frontend-only             |
| Browse           | FTS5 search, filters, sorting with popularity as default, page + page size | Matches a grid UI                                                      |
| Similar films    | On every movie detail page, from the Day 7 index                           | Richer public side at almost no cost                                   |
| Database access  | Plain `sqlite3`, read-only, small repository layer; no ORM                 | Fastest and simplest; a bug can't corrupt data                         |
| Rate limit       | 30 requests/minute per IP on predict endpoints                             | Protects the free-tier server during the demo                          |

### Endpoints

| Method | Path                                        | Purpose                                                     |
| ------ | ------------------------------------------- | ----------------------------------------------------------- |
| POST   | `/api/v1/predict`                           | Form in → ranges, drivers, comparables, warnings out        |
| POST   | `/api/v1/predict/compare`                   | Base input + up to 3 variants → predictions and differences |
| GET    | `/api/v1/movies`                            | Search, filters, sorting, pagination                        |
| GET    | `/api/v1/movies/{id}`                       | Facts, cast, crew, money, poster, similar films             |
| GET    | `/api/v1/people?role=…&q=…`                 | Director and actor autocomplete                             |
| GET    | `/api/v1/companies?q=…`, `/collections?q=…` | Studio and franchise autocomplete                           |
| GET    | `/api/v1/meta/options`                      | All dropdown values in one call                             |
| GET    | `/api/v1/health`                            | Status, model version, database build date                  |

### Tasks

1. **Project structure (45 min).** `main.py`; one router file per resource (new endpoint = new router file); `schemas/` from the Day 3 contract; `repo/` read-only queries; `services/`; docs at `/docs`.
2. **Startup and database (45 min).** Lifespan hook loads the model bundle and comparables index once; SQLite opened with `mode=ro`, one connection per request; settings from environment variables.
3. **Prediction endpoints (1.5 h).** Non-async `predict` runs in the thread pool; `compare` with up to 3 variants; LRU cache (about 1,000 entries); rate limit with a friendly 429; readable 422 messages.
4. **Public endpoints (2 h).** `GET /movies`: search, filters (genre, year range, language, has money data), sorting (popularity, newest, title, score), max 48 per page. `GET /movies/{id}`: facts, cast, crew, nominal and 2025-$ money, score, similar films. Full TMDB poster URLs in two sizes; HTTP cache headers.
5. **Form support endpoints (1 h).** Prefix autocomplete ranked by number of films (max 10); `meta/options`; `health`.
6. **Tests (1.5 h).** One `TestClient` test per endpoint on a fixture database; golden examples through HTTP; consistent compare differences; readable 422s; rate limit at 31 requests; `meta/options` matches the contract; writes fail in read-only mode.
7. **Wrap-up (30 min).** README API section, `PROGRESS.md`, commit.

**Done when** every endpoint passes its tests, `/docs` shows the full API, and a creator can get prediction results through the API. This completes the Week 2 backend deliverable.

## Day 9: Tests and Docker

Day 9 ends with proof that the whole pipeline works end to end and leaks nothing from the future, plus a backend container that runs the same locally and on the Day 14 host.

### Decisions

| Topic            | Decision                                                                                             | Why                                                      |
| ---------------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| End-to-end test  | Full chain on about 200 fake films                                                                   | Catches bugs that live between days                      |
| Time-travel test | Features from the full database must equal features from a database truncated before the film's year | The strongest proof of no leakage; a key interview point |
| Hardening        | Coverage report, fuzz testing with `hypothesis`, model version check                                 | The app never crashes and fails clearly on mismatches    |
| Data and models  | Baked into the Docker image                                                                          | One consistent artifact; simplest deployment             |
| Server           | `uvicorn` with one worker + thread pool                                                              | Each worker loads all models; free tiers have little RAM |
| Smoke script     | One script for local Docker and the live URL                                                         | The same checks before and after deployment              |
| Resources        | Memory and startup time measured and recorded                                                        | Problems found now, not on Day 14                        |
| Cut line         | Fuzz testing moves to Day 13 if time runs short                                                      | End-to-end and time-travel tests always stay             |

### Tasks

1. **End-to-end pipeline test (1.5 h).** `tests/fixtures/mini_raw.jsonl` with normal and messy films; raw → clean → database → features → tiny models → calibration → `predict()` → API; marked slow, under a minute; `make test` vs `make test-fast`.
2. **Time-travel leakage test (1 h).** For a sample year (e.g. 2010): features from the full database vs a truncated one must be identical across track-record, franchise, budget-history, themes and embeddings; PCA fitted on training years only.
3. **Test hardening (1.75 h).** `pytest-cov` aiming at about 80% (number in the README); `hypothesis` sends a few hundred random forms to predict and compare, always a valid result or a readable 422; `manifest.json` version check refuses to start on mismatch.
4. **Docker image (2 h).** Multi-stage build (`uv` builder → `python:3.11-slim`); database and model bundle baked in; non-root user; healthcheck on `/api/v1/health`; one `uvicorn` worker; under about 700 MB; `.dockerignore` excludes raw data, notebooks and caches.
5. **Compose, Make and smoke test (1 h).** `docker-compose.yml` (backend now, frontend on Day 10); `make docker-build`, `make docker-run`, `make smoke`; `scripts/smoke.py` checks health, golden predictions and one compare request against any base URL.
6. **Memory and startup (20 min).** Memory after startup and after 100 predictions, plus startup time, recorded in the README.
7. **Wrap-up (30 min).** README "Running with Docker" and "Testing", `PROGRESS.md`, commit.

**Done when** all tests pass (including end-to-end and time-travel), `make docker-build && make smoke` succeeds on a clean machine, and the resource numbers are recorded.

## Day 10: Frontend setup and the creator form

Day 10 ends with a working React app where a creator can fill in the form (or load an example) and submit it to the API. Results are shown raw until the Day 11 results page.

### Decisions

| Topic          | Decision                                                                                          | Why                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Language       | TypeScript, with types generated from the FastAPI schema (`openapi-typescript`)                   | API changes fail at compile time, not in the demo                      |
| UI library     | Tailwind CSS + shadcn/ui                                                                          | Modern, distinctive look with full control                             |
| Core libraries | React Router, TanStack Query, React Hook Form + Zod                                               | Routing, consistent loading/error states, validation mirroring the API |
| Form layout    | One page: required fields on top, collapsible "More details"                                      | Fast for repeated "what if" runs                                       |
| Input details  | As proposed (autocomplete, chips, month/year, runtime slider, formatted budget, synopsis counter) | No changes requested                                                   |
| Demo helpers   | Example buttons, shareable URL, draft auto-save                                                   | Smooth 5-minute demo, nothing lost on refresh                          |
| Examples       | Superhero sequel, small indie drama, horror with an unknown cast                                  | Show franchise, low budget and new people                              |
| Theme          | Light/dark toggle in the header                                                                   | Starts from system preference, remembers the choice                    |
| Cut line       | Shareable URL and draft auto-save move to Day 13 if short                                         | Example buttons always stay                                            |

### Tasks

1. **Project setup (1 h).** Vite + React + TypeScript in `/frontend`; Tailwind + shadcn/ui (button, input, select, combobox, slider, textarea, accordion, toast); React Router, TanStack Query, React Hook Form + Zod; Vite proxy to the backend; `npm run gen:api` generates types.
2. **App skeleton (1 h).** Routes `/`, `/predict`, `/predict/result` (Day 11), `/movies`, `/movies/:id` (Day 12); header, navigation, footer with TMDB attribution placeholder; light/dark toggle via theme tokens; responsive from the start.
3. **API layer (45 min).** One typed client; hooks `useMetaOptions`, `usePeopleSearch`, `useCompanySearch`, `useCollectionSearch`, `usePredict`; shared errors: 422 → field errors, 429 → "try again in a minute", network → retry toast.
4. **The form (2.5 h).**
   - Required: genres and themes (chips), release month and year (2026–2030), runtime (input + slider), language, certification, director, top 3 actors.
   - "More details": company, country, franchise, synopsis, budget.
   - Autocomplete with 250 ms debounce, film counts, and "Use '\<name>' as a new person".
   - Budget formatted as you type with "Leave empty and we'll estimate it"; synopsis counter with a 1–3 sentence hint.
   - Zod rules mirror the API contract; loading state on submit; raw response shown until Day 11.
5. **Demo helpers (1.25 h).** The three example buttons; form state in the URL; draft auto-save with a "Clear form" button.
6. **Docker (45 min).** Node build → nginx serving static files, `/api` proxied to the backend; added to `docker-compose`; smoke script checks the home page.
7. **Checks (30 min).** Vitest + Testing Library: invalid input blocked, examples fill all required fields, URL round-trips the form; manual phone-size check in both themes.
8. **Wrap-up (15 min).** `PROGRESS.md` and commit.

**Done when** a creator can load an example or fill in the form on desktop and mobile, submit it, and see the raw prediction, in both themes, through `docker compose up`.

## Carried to Days 11–15

- [ ] **Results page (Day 11).** Ranges, drivers, comparables, rough-estimate label, budget comparison, the new-person note and a limitations note.
- [ ] **Public pages (Day 12).** Browse grid and detail page with similar films; TMDB logo and notice, logo less prominent than our branding.
- [ ] **Compare UI (Day 13).** Up to 3 variants side by side, using the existing endpoint. Also receives Day 9's fuzz testing and Day 10's URL/auto-save if their cut lines were used.
- [ ] **Deployment (Day 14).** Check the host's RAM against the Day 9 measurement; run `scripts/smoke.py` against the live URL.
- [ ] **README (Day 15).** Final test results from Day 6, limitations, and next steps (IMDb score, Postgres if accounts are added).

## Sources

- [LightGBM issue #1969](https://github.com/microsoft/LightGBM/issues/1969): `pred_contrib` returns SHAP values plus the expected value
- [LightGBM issue #3998](https://github.com/microsoft/LightGBM/issues/3998): contributions don't add up for quantile/L1 objectives
- [MAPIE ConformalizedQuantileRegressor](https://mapie.readthedocs.io/en/stable/generated/mapie.regression.ConformalizedQuantileRegressor.html): the CQR method behind our own calibration function, used in both chain modes
