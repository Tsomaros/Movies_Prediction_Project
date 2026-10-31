# Evaluation and testing

The time-split evaluation, the baselines, the one-time test on 2019+ films, the audit and the test suite. Back to the [README](../README.md).

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

## Audit after Day 7

The whole pipeline was reviewed stage by stage against the methods it uses, the app's logic was tested on the real models, and performance was measured again without opening the locked test split. The full write-up with sources is in [`reports/audit.md`](../reports/audit.md); the numbers come from `uv run python -m ml.eval.audit` (`reports/audit_metrics.md`).

- **Method:** no leak found. The 182-day lag, strictly-earlier history, time-ordered splits, CQR exactly as Romano et al. (2019) publish it, and TreeSHAP drivers are all standard. Judging a film at the 1st of its month instead of its release day moves the middle by a median of under 0.01.
- **Logic:** 42 rule tests in `tests/ml/test_sanity.py` all pass on the real models:
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

The money models hold up on new films; the score ranges under-cover, because young films' TMDB scores are still settling ([Limitations](../README.md#limitations)).

## Testing

```bash
make test        # everything: 595 tests, about 2.7 min with the database, the models and the compose Postgres
make test-fast   # skips the slow, real-data and Postgres tests: 465 tests, about 35 s
make test-pg     # starts the compose Postgres, then the 46 accounts tests
make coverage    # everything, with line and branch coverage of ml/ and backend/
```

Three markers (`pyproject.toml`) sort the tests:
- `slow`: the end-to-end, fuzz and real-database time-travel tests;
- `real_data`: the tests that need `data/movies.db` and the app's models. They are also skipped automatically when those files are missing;
- `pg`: the accounts tests, against a throwaway database on the Postgres at `TEST_DATABASE_URL` (default the compose `db` on :5432). They are skipped when it can't be reached.

| What | Where | What it proves |
| --- | --- | --- |
| End to end | `tests/api/test_e2e.py`, `tests/fixtures/mini_raw.jsonl` | 213 fake TMDB records (200 films 2005–2020 plus 13 messy ones) go through every real step to answers over HTTP, in about 4 s: each messy record trips its cleaning rule exactly once, the views keep bad money out, the feature columns match `feature_list.json`, tiny models learn and stay monotone in budget |
| Time travel | `tests/features/test_time_travel.py` | cutting the database at a date leaves every feature of the deleted films unchanged when judged at that date: on the fixture (cut 2017, with a film released on the cut day) and on the real database (cut 2010, 300 films); the vocab, theme keywords and synopsis PCA refitted on train films equal the committed files |
| Fuzzing | `tests/api/test_fuzz.py` (hypothesis) | 300 random forms to `/predict`, 100 to `/predict/compare` and 60 to `/predict/sweep`, from valid edges to NaN, Infinity, huge or unicode text and non-objects: always a 200 with ordered, finite ranges or a 422 naming a field, never a 500 |
| Logic | `tests/ml/test_sanity.py` | bounds, a monotone budget, invariance, the revenue modes, form edges and matched-pair directions on the real models |
| Golden examples | `tests/ml/test_golden.py`, `tests/api/test_api_golden.py` | the three golden forms through `predict()` and over HTTP equal the snapshot, in under 400 ms |
| The API | `tests/api/test_api.py` | every endpoint, the cache, the rate limit, errors, read-only connections, parallel requests, and that the app refuses to start on a model file that doesn't match its manifest; the OpenAPI schema's error shapes and field specs |
| Accounts | `tests/accounts/test_accounts.py` (`pg`) | 401 on every `/me` route when logged out, a wrong password, the 6th login and 11th demo login in a minute, the cookie's flags (Secure on https only), only the token's hash stored, an old cookie after logout, an expired session, writes from another site or without JSON; lists created, switched and removed, a field left out keeping its value, the database refusing a rating on a watchlist film, unknown films, the 48-film status limit, tabs, sorts and pages; notes newest first, edit and delete, someone else's note as a 404, the 2,000-character limit, the Notes tab's pages; the 501st entry, 201st note and 31st write; the reset at 23:59:59 and 00:00:01 Athens time restoring the seed exactly, and four simultaneous demo logins resetting once |
| Surprise me | `tests/api/test_random.py`; the logged-in cases in `tests/accounts/test_accounts.py` (`pg`) | the pick never returns a watched or already shown film; spinning again until nothing is left gives exactly the films above the floor, each once; hidden gems remove the floor but keep the poster rule; each filter, and a film with no runtime left out under a runtime limit; `no_match`, `all_seen` and `watchlist_empty`; watchlist mode only from the watchlist, with no floor, 401 logged out and 503 without accounts; 422s for a bad decade or more than 200 excluded ids; the 429 |
| Person pages | `tests/data/test_people_data.py`, `tests/data/test_people_db.py`, `tests/api/test_people_api.py` | slimming and cleaning a TMDB person (blanks, future and reversed dates, only http(s) homepages and `nm…` IMDb ids), the biography cut at a sentence end, which ids are pulled (cast with 2+ films and every crew member, each once), the pull asking `/person/{id}` in English, resuming and recording 404s, the six-month refresh leaving one line per id; `person_details` in every build, the load skipping unknown ids and keeping the newest record and the build stamp; a person page's details and roles (acting first for an actor, films newest first with characters; crew films once per role with their jobs; the main role from TMDB's department or, without one, the most films), stats per role (the 50-vote rule, unknown and doubted money left out, the actor and director with 2+ shared films, never the person: a director's top actor, a writer's top director), cast photos on film pages, bad ids as 404 or 422, search hits with a photo and known-for film, accents folded both ways, search text with SQL or FTS syntax |
| The demo flow | `frontend/e2e/demo.spec.ts` (Playwright, Edge; `npm run e2e`, default against :8080) | in a real browser: a logged-out click, the demo login in the dialog, 8/10 by keyboard, a note with Ctrl+Enter, both in My movies after a reload, then it cleans up; then a "Surprise me" spin, a second spin with a different film, and its page |
| The served app and Sentry (Day 15) | `tests/api/test_web.py`, `tests/api/test_monitoring.py`, `frontend/src/lib/monitoring.test.ts` | client routes get the app uncached, bundles a year and gzipped, `.webp` typed, an old bundle and an unknown `/api` path are 404s, paths outside `dist/` never leak a file, the safety headers; an unhandled error reaches Sentry without the session cookie or the forwarded IP, 4xx answers don't; the frontend loads Sentry only with a DSN, once, and reports a crash |
| The model card | `tests/ml/test_model_card.py` | the committed `model_card.json` equals one built from the reports now, belongs to the served models, and copies the reports' numbers exactly, the uncertainty thresholds included |
| The frontend | `frontend/src/**/*.test.ts(x)` (Vitest, Testing Library) | the rules against the API's real limits, invalid input blocked, the autocomplete (Enter waits for the suggestions), the examples sending exactly the golden forms, the URL and draft round trips, every API error kind, routes and the theme; the results page on the three golden answers saved from the real API (cards, badges, break-even, notes, comparables, drivers, the accuracy numbers equal to the model card), form → results with one request, the actions, and each failure state; compare and the sweep on real answers saved from the API (every preset changes one field or says why not, the `?v=` round trip and broken variants, "within the uncertainty" on both sides of each threshold, the drivers that moved, a variant the API refuses, 12 months with the best and "about as good"); the edge cases (the waking-up notice after 3 s, the API down, 429, links edited by hand on four pages, a crashing page keeping the navigation); the browse state in the URL, search writing `?q=` once after typing, filters, chips, the no-results buttons, the remembered view, the film page (money toggle, few votes, no poster, 404), "Predict a film like this", the curated rows from their config, and TMDB's logo and notice on every route; the start page's panels and their reduced-motion switch, `/series`, the header's links, `/movies` against `/browse` and old `/movies?…` links reaching `/browse`; the accounts (a logged-out click completing after the login in the dialog, the password form: success back to `?next=`, a wrong password, empty and blank fields, a failing demo login; `?next=` only to a path on this site, an optimistic change rolling back with a toast, "Rating removed · Undo", the watched date, the stars by keyboard saving once, notes added with Ctrl+Enter, edited in place, deleted with Undo or rolled back, `/my-movies`' URL state, tabs, empty tab and retry, the browse badges from one request and the quick buttons, logout leaving nothing private); "Surprise me" (the shuffle then the film, at once with reduce motion, Spin again excluding every earlier pick, the login dialog before a watchlist spin, the three empty states and their buttons, the filters sent and remembered, a broken saved choice, the dialog on wide screens, the list buttons, a 429, reopening without a replay); the actor pages (photo, life dates, stats with links, the biography as plain text with Read more, IMDb and TMDB links, films with characters and every sort in the URL, crew credits, an initials avatar without TMDB details, a director-only page, the predict button's form, not found, a bad id never asked, Try again; the people row: 6 actors, nothing under 2 characters, "No films or people match", initials without a photo; cast and crew names linking from film pages; `formatLife` around a birthday); the person page by role (opening on the main role, the switch in `?role=` with the sort, an odd role falling back, the writing credit, the director's predict button, no button for writing); directors in the people row, merged and labelled; cast photos with initials as the fallback); 254 tests, 97.5% of lines and 87.3% of branches (`npm run coverage`) |

**Fuzzing found one real bug.** A whole-number field (year, month or runtime) sent as NaN or Infinity crashed the contract check with an `OverflowError`, and the API answered 500. JSON parsers, the server's included, accept those values. They now get the usual 422 "must be a number" (`ml/features/contract.py`, with 12 new tests).

**Coverage** (`make coverage`, lines and branches):

| Part | Coverage |
| --- | --- |
| Everything | 78.0% |
| The code the app runs (`backend/`, `ml/predict.py`, `ml/explain/`, `ml/features/`, the models) | 92.2% |
| Data, evaluation, baselines and calibration | 82.3% |
| The one-off scripts (audit, ablation, tuning, the final test run) | 13.3% |

The one-off scripts were each run by hand, and their results are in `reports/`.
