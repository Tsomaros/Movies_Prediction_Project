# Progress

## Day 1: Setup, data collection and first look (done 2026-10-21)

- [x] 0. Fix inconsistencies in the plan document (700 films/year, splits ≤2015 / 2016–18 / 2019+)
- [x] 1. Install tools: uv 0.13.4, GNU Make 4.4.1 (ezwinports), Python 3.11 via uv
- [x] 2. README skeleton with targets
- [x] 3. Repo setup
- [x] 4. TMDB client + offline tests (`ml/data/tmdb_client.py`, 12 tests)
- [x] 5. Pull script + offline tests (`ml/data/pull.py`, 15 tests; 27 total passing)
- [x] 6. Smoke test (2019, 20 films), then full pull
- [x] 7. Exploration notebook `notebooks/01_first_look.ipynb` → `data/day1_summary.json`
- [x] 8. Wrap-up and commit

### Pull stats (2026-10-21, at 700 per year; see "Extension" below for the current pull)

- 46,199 films, 1960–2025 (700 per year; 2005 has 699). 0 missing (404), 0 failed, 0 duplicates.
- About 39 min at 19.9 requests/second; `data/raw/tmdb_movies.jsonl` is 126 MB and not in git.
- A rerun fetches nothing (resume check passed).
- TMDB caching rule: re-pull or delete the raw data by 2027-04-21.

### Key numbers (at 700 per year; the notebook's Findings now show the 1,200-per-year numbers)

- 21% of films have both budget and revenue: 3.9% in the 1960s, 38% in the 2010s, 26% in the 2020s.
- Films with both budget and revenue: train 7,616, validation 799, test 1,305.
- Score: median 75 votes. A threshold of 50 keeps all of validation and test but cuts train from 36,971 to 19,296.
- Money coverage is 32% for English and mostly under 10% for other languages, so the revenue model is largely English-language.

### Surprises / inputs for Day 2

- The planned ratio rule (>1000×) flags real hits: The Blair Witch Project and Paranormal Activity. Rethink it on Day 2.
- The low-ratio rule (<0.0001×) catches Netflix films with token box office (Society of the Snow, Damsel). It works as intended.
- Budgets entered in local currency look rare. The one clear outlier is War and Peace (1968, ru) at $700M.
- 87 budgets and 96 revenues are between $1 and $999. The "below $1,000 → NULL" rule handles them.
- US certification is present for only 48% of films. The creator form needs an "unrated/unknown" option.
- TMDB language codes: `cn` (Cantonese) is separate from `zh`.

### Notes

- Used `ezwinports.make` instead of `GnuWin32.Make`: same GNU make, current version (4.4.1 vs 3.81), and winget adds it to PATH.
- Each saved film carries a `pulled_at` timestamp, needed for Day 2's `revenue_incomplete` flag and TMDB's 6-month caching rule.
- 404s go to `data/raw/missing_ids.txt` so reruns don't request them again.

## Day 2: Cleaning and storage (done 2026-10-21)

- [x] 0. Update the plan document: no high-ratio rule, a committed CPI table, a 3× per-language currency cap, 50 votes
- [x] 1. CPI table `data/cpi_us_annual.csv` (FRED CPIAUCNS, 1960–2025)
- [x] 2. Load and flatten (`ml/data/clean.py`)
- [x] 3. Basic cleaning
- [x] 4. Money and score rules
- [x] 5. SQLite build (`ml/data/build_db.py` → `data/movies.db`; `make db`, and `make data` = pull + build)
- [x] 6. Tests (`tests/test_clean.py`, `tests/test_build_db.py`; 65 total passing)
- [x] 7. Build and re-check notebook `notebooks/02_clean_check.ipynb`. Gate passed
- [x] 8. Wrap-up and commit

### Build stats (2026-10-21, at 700 per year; see "Extension" below)

- `make db` takes about 17 s. `data/movies.db` is 141 MB and not in git; it falls under the same TMDB 6-month rule as the raw pull.
- 46,199 films; 296,496 people; 601,306 cast rows; 330,010 crew rows; full-text search over title, original title and overview.
- Rows changed: 218 runtimes, 87 budgets and 96 revenues set to NULL. `money_suspect`: 4 films (War and Peace and The Ten Commandments: The Movie for currency; Society of the Snow and Damsel for low ratio).

| Training view | Train | Validation | Test |
| --- | --- | --- | --- |
| Revenue | 7,587 | 796 | 1,293 |
| Budget | 9,835 | 955 | 1,584 |
| Score | 19,296 | 2,100 | 4,900 |

### Changes from the plan

- **The CPI series is CPIAUCNS, not the planned CPIAUCSL.** It's the series BLS uses for official annual averages. October 2025 was never published (government shutdown), so it is the midpoint of September and November, which gives 322.153 for 2025.
- **The CPI check allows small drops.** Prices fell 0.36% in 2009, so "only goes up" was wrong. Each year must now change by between −1% and +15%.
- **The currency cap leaves each film's own budget out.** With it included, a single wrong budget in a language with fewer than about 100 budgets raised its own cap. This newly flagged The Ten Commandments: The Movie (2016, pt; $52.8M against a $49.1M cap); the flag was accepted.
- **Every `meta` value is stored as JSON.**

### Surprises / inputs for Day 3+

- Revenue training is thin before 1980: 271 films in the 1960s and 458 in the 1970s.
- 151 training films (1.8%) earned less than 1% of their budget. Some are real flops, others look like a US-only gross (*Flying Swords of Dragon Gate*). Revisit on Day 4.
- Search ranks only by text match ("godfather" puts *Hong Kong Godfather* first), so the Day 8 API should break ties by `vote_count`.
- The CPI table ends at 2025: add a row before pulling 2026 films, or their 2025-dollar values stay empty.
- `numpy` is used directly but comes in through pandas; it is not listed in `pyproject.toml`.

## Extension: 1,200 films per year (2026-10-21)

- **How:** the 700-per-year discover list was renamed to `data/raw/discover_ids_700.csv`, then the pull ran with `--pages 60`. `PAGES_PER_YEAR` in `ml/data/pull.py` is now 60, so `make data` keeps 1,200 per year.
- **Pull:** 33,000 new films in about 31 min at 20 requests/second, with 0 missing and 0 failed. That's 79,199 in total; 2005 and 2025 have 1,199. One film from the first pull fell out of its year's top 1,200 but stays in the data. `data/raw/tmdb_movies.jsonl` is 201 MB.
- **Database:** `make db` takes about 27 s and `data/movies.db` is 222 MB, with 434,571 people, 968,355 cast rows and 512,526 crew rows.
- **The extra 500 per year are thin:** median 9 votes (75 in the first 700), 21% `score_ok` (57%), 6.3% with a budget (27%), 2.3% with budget and revenue (21%).
- **Rows changed:** 1,238 runtimes, 167 budgets and 151 revenues set to NULL. `money_suspect`: 6 films, adding *Deewangee* (2002, hi, $220M budget, currency) and *Java Heat* (2013, $1,061 revenue, low ratio). There are now 23 language caps instead of 17.
- Both notebooks were rerun and their findings refreshed. The gate passed.

| Training view | Train | Validation | Test | Change from 700 per year |
| --- | --- | --- | --- | --- |
| Revenue | 8,050 | 886 | 1,485 | +6% / +11% / +15% |
| Budget | 11,334 | 1,162 | 1,964 | +15% / +22% / +24% |
| Score | 22,016 | 3,600 | 7,461 | +14% / +71% / +52% |

- Updated inputs for later days: revenue training before 1980 is still thin (286 films in the 1960s, 471 in the 1970s); 178 training films (2.0%) earned less than 1% of their budget; US certification is missing for 65% of films.
- The TMDB caching deadline is unchanged: re-pull or delete the raw data and database by 2027-04-21.

## Day 3: Feature engineering (done 2026-10-21)

- [x] 0. Update the plan document: shrinkage like 4 extra films, NR + missing → "unrated/unknown", ready-made ONNX model, `features` table in `movies.db`, leak-safety rules
- [x] 1. Form-to-feature contract (`ml/features/contract.py`): 14 inputs, `validate`, `describe`
- [x] 2. MiniLM download and embedding (`ml/features/text.py`, `make model`)
- [x] 3. Keyword themes (`ml/features/themes.py` → `themes.json`, 27 themes approved)
- [x] 4. Track-record features (`ml/features/history.py`)
- [x] 5. Other features (`ml/features/basic.py` → `vocab.json`)
- [x] 6. Synopsis embeddings and PCA (`ml/features/synopsis.py` → `ml/artifacts/synopsis_pca.json`)
- [x] 7. One shared feature function (`ml/features/build.py` → `features` table, `feature_list.json`; `make features`)
- [x] 8. Tests (`tests/test_features.py`, 30 tests; 95 total passing)
- [x] 9. Notebook `notebooks/03_features.ipynb`
- [x] 10. Wrap-up and commit

### Build stats

- `features` table: 79,199 films × 169 features (33 company, 27 theme, 24 track record, 19 genre, 17 country, 17 synopsis, 16 language, 6 certification, 5 date, 3 franchise, runtime, budget).
- `make features` takes about 60–80 s with the embedding cache in place. Embedding every overview the first time took 469 s (78,211 distinct texts); `data/overview_embeddings.npz` is 134 MB and not in git.
- `History` loads in about 7 s and covers every film in about 15 s.
- Model files: `all-MiniLM-L6-v2` at revision `1110a243`, both files checked against pinned sha256 hashes; `ml/artifacts/minilm/` (91 MB) is not in git.

### Changes from the plan

- **Actors: the form takes 5–10 (5 required), and features use the first 5 billed.** Top 10 correlated slightly better in training (+0.28 vs +0.25 with log revenue), but a creator entering only 5 would get features computed differently from training.
- **Franchise counts sequels only.** First entries of a collection earn far more (train median $108M vs $27M with no collection) because only hits get sequels, so `is_franchise`, franchise experience and the collection's earlier revenue all use earlier entries only. A new franchise name on the form counts as an original.
- **27 themes, not 15–25.** KMeans with 20 groups mixed unrelated keywords, so the 30-group run was cleaned by hand and approved. After the notebook, "amused", "absurd" and "campy" were dropped from comedy and satire: 40–51% of their films weren't comedies; now 91% of the theme's films are.
- **Synopsis code is in its own module** (`synopsis.py`), so `text.py` only handles the model.
- **A creator's film is judged at the 1st of its release month**; training films at their exact release date. On The Dark Knight this changes only small track-record values (one actor film between 1 and 16 July).
- **Major studios are a named list of 9:** Universal, Warner Bros., Paramount, Columbia, 20th Century Fox and 20th Century Studios, Walt Disney Pictures, MGM, United Artists.
- `numpy` is now declared in `pyproject.toml` (Day 2 note), along with `onnxruntime`, `tokenizers` and `scikit-learn`.

### Checks

- The Dark Knight typed by hand with names (director, 10 actors, companies, franchise, synopsis text) gives exactly the same 169 values as its training row.
- Two deliberate bugs were caught by the tests: counting same-day films (the film itself) and counting first entries as franchise experience.
- Nolan before The Dark Knight checked by hand: shrunk revenue (5 × 18.98 + 4 × 17.51) / 9 = 18.33; Batman Begins is not franchise experience.

### Surprises / inputs for Day 4+

- `covid_period` is always 0 in train, so no model can learn from it; Day 4's with-and-without-2020–21 report matters.
- The test split has more new directors (38%) than train (31%), so Day 4's new-vs-experienced breakdown is important.
- Only 48% of films have a theme, and TMDB keyword noise remains ("rape" puts *The Revenant* in sex and erotica, "hilarious" puts some action films in comedy).
- `franchise_revenue` is +0.81 with log revenue but exists only for 730 train sequels; `log_budget` (+0.68) is missing for 83% of train films, so Day 6's budget chaining matters.
- Director experience isn't linear: median revenue peaks at 6–10 earlier films ($58M) and dips at 11+ ($43M).
- 16 synopsis numbers keep 28.5% of the variance; try 32 on Day 5 if the synopsis helps.
- An earlier film's score is its current TMDB rating, not its rating at the time (README Limitations).

## Day 4: Baselines and evaluation (done 2026-10-21)

- [x] 0. Update the plan document: main genre = TMDB's first genre, PCA refit per backtest fold, B2 fitted per genre, ranges from train residuals
- [x] 1. Genre order: `movie_genres.ord` in `clean.py`/`build_db.py`, TMDB order in `film_to_form`; rebuilt; features table unchanged (exact)
- [x] 2. Split module (`ml/eval/splits.py`): views + features, test lock (`final=True`), COVID exclusion, 3 folds
- [x] 3. Metrics (`ml/eval/metrics.py`)
- [x] 4. Baselines (`ml/models/baselines.py`): B0–B2 for revenue, budget and score
- [x] 5. Harness and breakdowns (`ml/eval/evaluate.py`)
- [x] 6. Rolling backtest with per-fold synopsis PCA (`ml/eval/backtest.py`)
- [x] 7. Reports and `make evaluate` (`reports/`)
- [x] 8. Tests (`tests/test_eval.py`, 20 tests; 117 total passing)
- [x] 9. Run and review
- [x] 10. Wrap-up and commit

### Results (validation 2016–18; backtest mean over 3 folds)

| Model | Revenue MAE log / within 2× | Budget MAE log / within 2× | Score MAE |
| --- | --- | --- | --- |
| B0 | 1.890 / 24.9% | 1.272 / 35.7% | 0.692 |
| B1 | 1.796 / 26.2% | 1.207 / 36.7% | 0.627 |
| B2 | **1.316 / 39.8%** | **1.193 / 37.3%** | **0.602** |
| B2 backtest | 1.309 ± 0.012 | 1.265 ± 0.052 | 0.621 ± 0.014 |

- `make evaluate` runs all 9 baselines in about 5 s. B2 coverage is 80% (revenue), 86% (budget) and 81% (score).
- Fitted B2 values: revenue multiples from 0.82× (History) to 3.86× (Documentary), 1.69× overall; sequels cost 1.45× their genre median; director weight 1.18.

### Changes from the plan

- **`History` gained `load_films` and `typical_at`**, so B2 score can use the typical score at each film's date. The track-record features are unchanged.
- **A fold's PCA is fitted on every film from its train years with an overview**, as the saved PCA was, not only on the model's view. As a result, fold 3 reproduces the saved PCA exactly.
- **Spearman returns empty (—) for constant predictions** (B0) instead of raising a warning.
- **Peek disclosed:** while building the split module, the revenue test split was loaded once with `final=True`, to count rows (1,485; 1,163 without 2020–21). No targets or predictions were looked at.

### Checks

- Two deliberate bugs were caught by the tests: an unlocked test split and a fold PCA fitted on every year.
- Every breakdown's groups add up to the validation total, and the hand-computed metric examples match exactly.

### Surprises / inputs for Day 5+

- **B2 revenue uses the real budget**, so it's a "budget known" benchmark. The Day 6 chain must be compared fairly: with predicted budgets, revenue error will rise.
- **The budget baselines barely beat the median** (1% over B1). At $150M+, 0% of films are within 2× and B2 covers 25%; the budget model has the most room to improve.
- **One range for every film fits no group.** B2 revenue covers 100% of $150M+ films and 72% of films under $10M and of new directors' films. Day 5's quantile models should fix this; check group coverage, not just the overall figure.
- New directors and small films are the hardest groups for every target; sequels are the easiest.
- The score baseline's director term helps only experienced directors (0.61 → 0.57); new directors stay at 0.66.

## Day 5: First models (revenue and score) (done 2026-10-21)

- [x] 0. Update the plan document: calibration on folds 1–2, our own CQR function instead of MAPIE, tree count from tuning, a 32-synopsis ablation row
- [x] 1. Dependencies: `lightgbm` 4.7.0, `optuna` 5.0.0
- [x] 2. Training module (`ml/models/train.py`, `LgbmQuantile`)
- [x] 3. Tuning (`ml/models/tune.py`, `make tune`): 178 revenue and 67 score trials
- [x] 4. Conformal calibration (`ml/models/calibrate.py`)
- [x] 5. Evaluation: LightGBM in `make evaluate` next to B0–B2
- [x] 6. Ablation (`ml/models/ablation.py` → `reports/ablation.md`); synopsis then dropped from both models
- [x] 7. Saved artifacts (`make train` → `ml/artifacts/{target}_p10|p50|p90.joblib` + `{target}_meta.json`)
- [x] 8. Tests (`tests/test_models.py`, 23 tests; 140 total passing)
- [x] 9. Wrap-up and commit

### Results (validation 2016–18; backtest mean over 3 folds)

| Model | Revenue MAE log / within 2× | Revenue coverage / width | Score MAE | Score coverage / width |
| --- | --- | --- | --- | --- |
| B2 | 1.316 / 39.8% | 79.7% / 53× | 0.602 | 81.0% / 1.96 pts |
| **LightGBM** | **1.113 / 45.6%** | 83.2% / 37× | **0.496** | 81.0% / 1.68 pts |
| B2 backtest | 1.309 ± 0.012 | | 0.621 ± 0.014 | |
| LightGBM backtest | 1.130 ± 0.015 | | 0.506 ± 0.007 | |

- **Calibration** is +0.473 log for revenue and +0.165 points for score, learned from 1,848 and 6,414 fold films. On 2016–18, coverage rises from 66% to 83% for revenue and from 71% to 81% for score.
- **Ablation:**
  - Removing budget costs +0.092 on validation and +0.108 in the backtest.
  - Removing track record costs +0.017 (revenue) and +0.016 (score) in the backtest; removing themes costs +0.012 and +0.007.
  - Removing synopsis changes −0.006 and −0.000, and 32 synopsis numbers +0.008 and +0.004.
  - Removing the monotone constraints changes −0.001.
- **Sizes:** the models are 7.9 MB for revenue and 25.1 MB for score. They're gitignored and rebuilt by `make train` in about 35 s, plus about 1.5 min of calibration.

### Changes from the plan

- **Revenue model shape:** LightGBM refuses monotone constraints on quantile and L1 objectives. Revenue therefore uses a monotone Huber middle model, plus quantile models of its out-of-fold residuals that leave out the three monotone columns. Score keeps three quantile models.
- **Calibration:** our own CQR function on folds 1–2 instead of MAPIE on 2016–18, so validation coverage stays honest.
- **Tree count:** set by early stopping on folds 1–2 during tuning. Nothing is fitted or stopped on 2016–18.
- **Score never gets `log_budget`.** `feature_list.json` allows it, so `train.py` excludes it (`EXCLUDED`).
- **Synopsis dropped after the ablation**, by your decision. `DEFAULT_DROP = ("synopsis",)`, and the calibration and evaluation were rerun. The tuned settings came from the run with synopsis included and were reused without retuning.
- **Model files are not in git.** At 33 MB they are too large, and they change on every retrain; their JSON settings, calibration and metadata are committed.
- **Artifacts:** `.joblib` per quantile model, as planned.

### Checks

- Raising budget, director revenue or franchise revenue never lowers p10, p50 or p90 (on real validation rows and in the tests).
- Saved models reload with identical predictions; a fresh refit matches exactly, so training is deterministic.
- Two deliberate bugs were caught by the tests: monotone columns leaking into the range models, and an off-by-one in the conformal quantile.
- A 30-second tuning dry run wrote to `reports/experiments.csv` because the log path was bound at definition time. This was fixed and the 10 dry-run rows removed.

### Surprises / inputs for Day 6+

- **Revenue coverage on 2016–18 is 83%,** slightly cautious. For the ≤2018 model, recompute the correction from all three folds and check it on the test set.
- **Small films remain the hardest group:** under $10M, 38% are within 2× (B2: 35%).
- **The budget chain will cost revenue accuracy.** Without budget, MAE log rises by about 0.1 (validation 1.219), which is roughly the floor if the predicted budget were useless.
- **Synopsis adds nothing.** Consider removing it from the creator form's "helps the prediction" messaging, or trying other text features later.
- **Optional retune without synopsis** (`make tune`, 30 min). Tuning gained only about 1% the first time.

## Day 6: Budget model, the chain and the final test run (done 2026-10-21)

- [x] 0. Update the plan document: our own CQR on folds 1–2 instead of MAPIE on 2016–18, the chain calibrated on folds 1–2, ≤2018 corrections from all three folds, all-data models reuse them, no synopsis in the budget model, no retune
- [x] 1. Budget track-record features (`ml/features/history.py`), also tried in the revenue model: kept in revenue
- [x] 2. Budget model (`ml/models/train.py`, tuning, calibration, harness, synopsis ablation row)
- [x] 3. Chain: "budget given" and "budget estimated" calibrations, `predict_revenue(features, budget=None)`
- [x] 4. Rough-estimate label
- [x] 5. Budget comparison
- [x] 6. Freeze (`pre-test`), retrain on ≤2018, final test run, all-data models (`final-models` tag after your review)
- [x] 7. Tests
- [x] 8. Wrap-up and commit

### Task 1: budget track record

- **6 features:** `director_budget`, `actors_budget_{max,mean,min}`, `company_budget` and `franchise_budget`, in log 2025 dollars, appended after the Day 3–5 columns. The rebuilt table matches the old one exactly on all 169 earlier columns (same values, same order), so the Day 5 models reproduce exactly. `make features` now takes about 95 s.
- **Correlation with log budget (train):** franchise 0.78, company 0.59, actors max 0.53, director 0.38 (director's earlier revenue: 0.23).
- **Revenue trial** (tuned settings reused): validation MAE log 1.113 → 1.093, within 2× 45.6% → 46.8%; backtest mean 1.130 → 1.124. Kept by your decision. Score stays without it (`DEFAULT_DROP` is now per target).
- **After retraining:** revenue's correction is +0.448 log (was +0.473); validation coverage 83.6%, width 36×. Score unchanged.

### Changes from the plan

- **An earlier film's budget counts from its release,** with no 182-day wait like revenue and score: a budget is known before release.
- **Company budget is the highest shrunk median among the film's companies** that have earlier budgets (the typical budget when none do). Companies get their own track record (`Companies` in `history.py`), with typed names matched against every company in the database, not only the top 30.
- **Franchise budget is the plain median of earlier entries** (NaN when none), like `franchise_revenue`; the first entry's budget counts.
- **The budget features are their own group** ("budget track record") rather than part of "track record", so the Day 5 ablation rows keep their meaning. `reports/ablation.md` is still the Day 5 table; the full ablation is rerun with the budget model rows in task 2.

### Checks

- A deliberate bug (same-day budgets counted) was caught by 3 tests. 145 tests passing.

### Task 2: budget model

- **Model:** three LightGBM quantile models on log 2025 dollars (`LgbmQuantile("budget")`), unweighted, no constraints; 157 features (every allowed one except `log_budget` and the synopsis numbers). `train.py`, `tune.py`, `calibrate.py`, `evaluate.py` and `ablation.py` now cover all three targets.
- **Tuning:** 96 trials in 15 min on folds 1–2; fold MAE log 0.685 with 1,404 trees vs 0.699 for the defaults (−2.1%).
- **Calibration:** +0.399 log from 2,599 fold films. Coverage before → after: folds 55% / 57% → 80% / 80%, 2016–18 64% → 84%.

| Budget (validation 2016–18) | MAE log | Within 2× | Spearman | Coverage | Width | Backtest mean |
| --- | --- | --- | --- | --- | --- | --- |
| B2 | 1.193 | 37.3% | 0.389 | 86.0% | 72× | 1.265 ± 0.052 |
| **LightGBM** | **0.613** | **70.9%** | **0.859** | 84.3% | **8.1×** | **0.662 ± 0.036** |

- **Breakdowns:** better than B2 in every group. $150M+ films: 90% within 2× (B2: 0%). Under $10M: MAE log 0.85, coverage 77% (the one group below 80%). New directors 0.80, sequels 0.43.
- **Ablation:** removing the budget track record costs +0.054 (validation) / +0.061 (backtest), the people track record +0.023 / +0.026. Synopsis: +0.000 / −0.004 without it, +0.004 / +0.008 with 32 numbers, so it stays out. Themes: −0.005 / +0.001, kept.
- **Full ablation rerun:** every Day 5 revenue and score row reproduced exactly; the revenue row with the budget track record matches task 1.
- **Sizes and times:** `make train` about 1 min for the three models (plus about 4 min of calibration), `make evaluate` about 3 min, the ablation about 18 min.

### Checks (task 2)

- The budget model's top inputs by gain are `company_budget` (13%), runtime (5%) and `director_budget` (4%), with no single dominant column; `log_budget` is not among its features (tested).
- New tests: budget ranges ordered, three plain quantile models with per-film widths, never its own target, saved budget model reloads identically. 149 tests passing.

### Task 3: the chain

- **Module:** `ml/models/chain.py`. `EstimatedBudgetRevenue` fits the revenue model on real budgets and a budget model on every `v_train_budget` film up to the same last year (`splits.through`), then predicts revenue from the budget model's middle prediction. `Chain` / `predict_revenue(features, budget=None)` use the saved models: a budget means "given", none means "estimated". `LgbmQuantile.predict` takes an optional `q`.
- **Calibration** (`make train` now writes `revenue_estimated_calibration.json` too): estimated q = +0.585 log (given: +0.448), from the same 1,848 fold films. Coverage before → after: folds 62% / 61% → 79% / 81%, 2016–18 66% → 86%.

| Revenue (validation 2016–18) | MAE log | Within 2× | Spearman | Coverage | Width | Backtest mean |
| --- | --- | --- | --- | --- | --- | --- |
| B2 (real budget) | 1.316 | 39.8% | 0.709 | 79.7% | 53× | 1.309 ± 0.012 |
| No budget input (ablation) | 1.219 | 39.3% | — | — | — | 1.244 ± 0.023 |
| **LightGBM, budget estimated** | **1.135** | **44.0%** | **0.793** | 86.1% | 48× | **1.192 ± 0.044** |
| LightGBM, budget given | 1.093 | 46.8% | 0.807 | 83.6% | 36× | 1.124 ± 0.023 |

- **The estimated budget recovers about two-thirds of what the budget is worth:** no budget costs +0.126 against the given mode, an estimated one +0.042. On the 886 validation revenue films the estimate is within 2× of the real budget for 75% (MAE log 0.535), and on average 9% high.
- **Estimated mode beats B2 with the real budget** on validation and in every fold (1.199 / 1.242 / 1.135 vs 1.292 / 1.318 / 1.316).
- **Coverage by group (estimated):** 84–94%, every group above 80%; $150M+ films 94%, under $10M 88%.

### Changes from the plan

- **The estimated correction is never smaller than the given one** (`max` in `Chain.load` and the harness), which makes "estimated is never narrower" true by construction; here it didn't bind (0.585 vs 0.448).
- **The harness reports revenue in both modes**, so the estimated mode gets the same breakdowns and backtest as every other model. `make evaluate` now takes about 4.5 min.

### Checks (task 3)

- `predict_revenue` on 2016–18 with the saved models reproduces the harness exactly in both modes (1.1353 / 1.0933).
- New tests: given mode uses the creator's budget (one value or one per film), estimated mode feeds the budget model's middle and ignores any `log_budget` in the features, estimated is never narrower than given with the same budget. 152 tests passing.
- 2016–18 coverage in estimated mode (86%) is more cautious than given (84%); the ≤2018 models take their corrections from all three folds (task 6).

### Task 4: rough-estimate label

- **Module:** `ml/models/rough.py` (`is_rough`, `fit_rule`; `uv run python -m ml.models.rough` writes `ml/artifacts/rough_estimate.json`). The rule is fitted with the saved ≤2015 models on 2016–18 and then frozen.
- **Rule (your decision):** revenue and budget only; high ÷ low above the 75th percentile of 2016–18 widths, rounded to two figures: **revenue 81×** (from the budget-given ranges), **budget 12×**. Score gets no label.

| Validation 2016–18 | Labelled | MAE log labelled / rest | Within 2× labelled / rest |
| --- | --- | --- | --- |
| Revenue, budget given | 25% | 1.537 / 0.945 (1.63×) | 34% / 51% |
| Revenue, budget estimated | 32% | 1.547 / 0.945 (1.64×) | 31% / 50% |
| Budget | 27% | 0.863 / 0.520 (1.66×) | 54% / 77% |

### Changes from the plan

- **The 4× starting point was dropped:** it labelled 98% of revenue and 93% of budget predictions (typical widths 36× and 8×).
- **Score has no label:** its widths span only 1.3–2.0 points, width vs error Spearman is 0.09, and the widest quarter has only 1.14× the error of the rest. Revenue (0.30) and budget (0.26) widths do track error.
- **The rule is not part of `make train`,** so retraining (task 6) can't move the frozen cut-offs.

### Checks (task 4)

- New tests: the cut-off compares high ÷ low (80× not labelled, 82× labelled at 81×), score is never labelled, and the fitted rule labels about a quarter with a two-figure cut-off. 154 tests passing.

### Task 5: budget comparison

- **Code:** `compare_budget` and `Chain.compare_budget(features, budget=None)` in `ml/models/chain.py`, plus `format_money` (two significant figures: "$12M", "$1.2B"). Columns: low, middle, high (2025 $) and the sentence "Similar films usually cost $X–Y"; with a budget also its position (below / within / above) and its ratio to the middle. "Similar films" means the budget model's calibrated 10th–90th range for the same form.
- **On 2016–18 (1,162 films, real budgets):** 84.3% within, 10.9% below, 4.7% above; median budget ÷ middle 0.97. Examples: *Get Out* $5.9M vs $1.4M–$20M, *Avengers: Infinity War* $380M vs $180M–$580M, *La La Land* $40M vs $14M–$65M.

### Surprises / inputs for later

- **Misses are lopsided:** real budgets fall below the range twice as often as above it.
- **Rounding can blur a "below":** *The Shape of Water* ($26M) is just under a low end that also shows as $26M. Day 7's wording should handle budgets within a few percent of an edge (e.g. "at the low end").

### Checks (task 5)

- New tests: money formatting (6 cases), positions and ratios on hand values, the range still shown without a budget, and the chain using the budget model's own range. 162 tests passing.

### Task 6: freeze and final test run

- **Freeze:** tasks 1–5 committed (`6b12900`) and tagged `pre-test`.
- **Script:** `ml/eval/final.py` is the only module that passes `final=True`. `test` refuses to run again once `reports/final_test.json` exists; `all-data` needs the test run's corrections. A dry run with 2016–18 standing in for the test split (outputs in the scratchpad) reproduced every validation number exactly before the real run.
- **≤2018 corrections** (out-of-fold on folds 1–3, 2010–18): revenue +0.399 (2,734 films), revenue estimated +0.505, budget +0.363 (3,761), score +0.159 (10,014). All smaller than the folds 1–2 corrections (0.448 / 0.585 / 0.399 / 0.165).
- **Test run (2019+, once, 259 s):**

| Test 2019+ | B2 | LightGBM | Coverage | Width | Validation (for reference) |
| --- | --- | --- | --- | --- | --- |
| Revenue MAE log, budget given | 1.455 | **1.230** | 77.4% | 34× | 1.093 |
| Revenue, without 2020–21 | 1.418 | **1.189** | 78.2% | 33× | |
| Revenue, budget estimated | 1.455 | **1.266** | 78.2% | 42× | 1.135 |
| Budget MAE log | 1.247 | **0.682** | 79.9% | 7.6× | 0.613 |
| Score MAE | 0.574 | **0.493** | 81.1% | 1.67 pts | 0.496 |

- **Disappointments (in Limitations):** $150M+ revenue films are worse than B2 (MAE log 1.04 vs 0.99) with 64% coverage; with an estimated budget level with B2 (0.99). $50–150M revenue coverage 75%; $50M+ budget coverage 74–77%. Revenue is about 0.14 harder on 2019+ for both LightGBM and B2.
- **Rough label on test:** revenue 18% labelled (1.45× the error), estimated 24% (1.40×), budget 24% (1.77×).
- **All-data models** (`ml/artifacts/final/`, `.joblib` gitignored): revenue 10,421 films, budget 14,460, score 33,077 (1960–2025), with the ≤2018 corrections and frozen tree counts; the revenue meta carries `q_estimated` (+0.505), which `Chain.load(out_dir)` reads.

### Changes from the plan (task 6)

- **`save_model` takes `extra` metadata** and writes "films released 1960–2025" instead of "train split, …".
- **The ≤2018 models aren't saved;** the test run fits and scores them in one go. The app uses the all-data models.

### Task 7: tests

- **Already covered in tasks 2–5:** budget ranges ordered, estimated mode never narrower than given, budget model never gets `log_budget`, saved budget model reloads identically, the chain, the rough label and the budget comparison.
- **New `tests/test_final.py` (10 tests):**
  - only `ml/eval/final.py` passes `final=True` (checked on the code's syntax tree, so docstrings don't count);
  - the test run refuses a second run before touching any data;
  - the all-data stage refuses to run without the test run's corrections;
  - a saved chain reloads identically and reads its estimated correction from the metadata;
  - the committed all-data metadata uses the frozen settings, tree counts, features and final corrections, trained on 1960–2025 (skipped without the files);
  - the all-data models reload identically (skipped when the gitignored `.joblib` files are absent).
- **Checks:** two deliberate bugs were caught (a `final=True` call added to `evaluate.py`, and the second-run guard removed). 172 tests passing.

### Surprises / inputs for Day 7+

- **Use the all-data models:** `Chain.load(Path("ml/artifacts/final"))` and `load_model(target, Path("ml/artifacts/final"))`. `ml/artifacts/` keeps the ≤2015 models from `make train` for evaluation.
- **Big-budget revenue is the weak spot** ($150M+: worse than B2 on 2019+, 64% coverage). Day 7's explanations and Day 11's results page should not oversell blockbuster revenue predictions.
- **Rough-estimate label:** 18–24% of test predictions; pass it through `predict()` per target (revenue, budget; never score).
- **Budget comparison wording:** budgets within a few percent of an edge round to the same dollar figure (*The Shape of Water*); word these as "at the low/high end".
- **Revenue explanations must handle both modes:** in estimated mode the budget driver is the predicted budget, not the creator's.
- **`make evaluate` takes about 4.5 min** now (13 models with backtests); `make train` about 5 min.
