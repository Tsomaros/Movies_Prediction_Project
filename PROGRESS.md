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

## Day 7: Explanations and packaging (done 2026-10-22)

- [x] 0. Update the plan document: no rescaling (contributions add up to the middle exactly), no synopsis driver, log-based strength thresholds, the budget track record inside the groups, comparables from `score_ok` films with money first and full MiniLM vectors, one "estimated budget" driver, a $150M+ warning, "at the low/high end" wording
- [x] 1. Drivers (`ml/explain/drivers.py`)
- [x] 2. Feature groups (`ml/explain/groups.py`)
- [x] 3. Plain-English sentences (`ml/explain/sentences.py`)
- [x] 4. Comparable films (`ml/explain/comparables.py`)
- [x] 5. `predict()` package (`ml/predict.py`, `manifest.json`)
- [x] 6. Tests
- [x] 7. Sanity notebook (`notebooks/07_explanations.ipynb`)
- [x] 8. Wrap-up and commit

### Task 1: drivers

- **Module:** `ml/explain/drivers.py`.
  - `contributions(model, df)` returns LightGBM's `pred_contrib` on the middle model: one column per feature plus `expected` (the typical film).
  - `group_contributions(contribs, groups)` refuses any feature without a group.
  - `effect`, `strength` and `top_drivers(target, row, n=5, estimated=())` complete the module. Zero contributions are dropped, and `estimated` flags revenue's budget in estimated mode.
- **They add up:** on 2016–18 with both the ≤2015 and the all-data models, contributions plus `expected` equal the middle that is shown, to within 1e-13, in both revenue modes. The starting points (all-data models) are revenue 17.12 log ($27M), budget 16.33 log ($12M) and score 6.41.
- **Strength on 2016–18 (all-data models, grouped by feature source for now):**

| Target | Top-5 drivers strong / moderate / slight | Top driver strong | Most often the top driver |
| --- | --- | --- | --- |
| Revenue | 68% / 30% / 2% | 99% | budget (64%) |
| Budget | 47% / 45% / 8% | 98% | budget track record (77%) |
| Score | 13% / 41% / 45% | 57% | track record (50%) |

- **Speed for one film:** about 9 ms for revenue, 25–40 ms for budget and 40–50 ms for score. The score model's trees are deep, and `pred_contrib` costs more than a plain prediction (about 5 ms per model). All three come to about 100 ms of the 400 ms budget.

### Changes from the plan (task 1)

- **A small rescale after all:** when the budget or score quantile models cross, `predict()` sorts them, and the middle shown isn't the p50 model's own value. On 2016–18 with the all-data models this affects 40 of 1,162 budget films (up to 0.21 log) and 2 of 3,600 score films. Those rows are scaled so the features add up to the middle that is shown; revenue never needs it.

### Checks (task 1)

- **New `tests/test_explain.py` (18 tests):**
  - contributions add up to the middle for all three models;
  - the correction q never moves the middle;
  - crossed quantiles are followed;
  - estimated-mode contributions add up to the chain's middle;
  - groups keep the total;
  - a feature without a group is refused;
  - the strength cut-offs hold (−20% counts as strong, like +25%);
  - the top drivers come out in the right order with the right flags.
- **Mutation check:** with the rescale removed, 2 tests fail; even the small test budget model has crossings. 190 tests passing.

### Inputs for later tasks

- **Money cut-offs may be too low:** 68% of revenue's top-5 drivers are "strong". Check this in the notebook (task 7) before the wording is settled.

### Task 2: feature groups

- **Module:** `ml/explain/groups.py`. `GROUPS` (12 ids → labels), `group_of(name, source)` and `feature_groups()`.
- **How features are grouped:**
  - groups follow the feature sources in `feature_list.json`;
  - the track record is split into director and cast by prefix;
  - each budget track-record column joins the group it describes.
- **158 features in 12 groups:** studio 34, themes 27, cast 21, genre 19, country 17, language 16, director 7, certification 6, release timing 5, franchise 4, runtime 1, budget 1.
  - Every feature of the three app models has a group.
  - Revenue uses all 12 groups. Budget and score use 11, without the budget group.
- **Drivers on 2016–18 (all-data models, real groups):**

| Target | Strong / moderate / slight (top 5) | Most often the top driver | Most often in the top 5 |
| --- | --- | --- | --- |
| Revenue | 72% / 27% / 1% | budget 62%, studio 11%, cast 8% | studio 84%, budget 83%, certification 59%, runtime 59% |
| Budget | 59% / 37% / 4% | studio 71%, cast 15% | studio 96%, cast 81%, genre 74%, director 72% |
| Score | 12% / 47% / 41% | cast 42%, genre 29%, runtime 20% | genre 90%, runtime 89%, cast 89%, themes 62% |

### Changes from the plan (task 2)

- **Studio is its own group,** separate from country and language. It holds the 33 company columns and `company_budget`, and it is a top driver for budget 71% of the time.
- **The synopsis numbers have no group,** as decided in task 0. A model that used them would be refused by `group_contributions` rather than explained with a raw name.

### Checks (task 2)

- **6 new tests (24 in `tests/test_explain.py`):**
  - every feature the app models use has a group;
  - every group is used, and labels are plain words;
  - the budget track record lands in the right groups;
  - the synopsis numbers have no group, and an unmapped source raises an error.
- **Mutation checks:** removing the country source mapping fails 6 tests, and so does removing the cast prefix. 196 tests passing.
- **Studio driving budget needs a look in the notebook (task 7):** `company_budget` probably carries most of it.

### Task 3: plain-English sentences

- **Module:** `ml/explain/sentences.py`. `sentence(target, driver, form, features, names=None)` returns `{group, label, direction, strength, estimated, value, text}`; `explain(...)` splits drivers into `up` and `down`, largest first.
- **How a sentence is built:**
  - one template per group, filled from the clean form and the feature row;
  - the budget is the one the model used, so in estimated mode it reads "The estimated budget of about $5.2M";
  - `names` supplies display names when the form holds only ids (the API will look them up);
  - `value` is the creator's value on its own, so the frontend can highlight it.
- **Examples** (all-data models, each film judged at its release date):
  - *Get Out*, revenue: "Jordan Peele, with no earlier films as director in our data, strongly lowers the expected revenue."
  - *La La Land*, score: "Damien Chazelle's 3 earlier films strongly raise the expected audience score."
  - *Avengers: Infinity War*, revenue: "Being part of The Avengers Collection (2 earlier films) strongly raises the expected revenue."
  - *The Shape of Water*, revenue: "Releasing in December 2017 (holiday season) raises the expected revenue."

### Changes from the plan (task 3)

- **No bold in the text.** The sentences are plain, and the highlighted value is a separate field.
- **Wording fixes after reading real output:**
  - the verb agrees with the subject ("The genres … raise");
  - lists of studios and themes stop at three ("… and 2 more");
  - theme names are quoted, because they contain "and" ("murder and revenge");
  - a first-time director has "no earlier films as director".

### Checks (task 3)

- **16 new tests (40 in `tests/test_explain.py`):**
  - every group has a sentence, with no raw feature name in it;
  - 12 exact sentences built from one form;
  - the estimated-budget and per-target wording;
  - new people, franchises (existing or new) and missing values;
  - typed names used without a lookup;
  - the up/down split.
- **Mutation checks:** ignoring verb agreement fails 3 tests, and so does removing a group's template. 212 tests passing.

### Inputs for later tasks

- **A single feature row with missing values comes out as `object` dtype,** which LightGBM refuses. `predict()` (task 5) must turn the `build_features` dict into a float frame.

### Task 4: comparable films

- **Module:** `ml/explain/comparables.py`.
  - `Index.build(con, cache)` builds the index from the database and the embedding cache, and `Index.save` / `Index.load` store it.
  - `index.query(genres, themes, vector, year, log_budget, as_of, n=5)` returns JSON-ready dicts: id, title, year, poster path, budget, revenue (2025 $ or None), score and similarity.
  - `uv run python -m ml.explain.comparables` writes `ml/artifacts/final/comparables.npz` (26 MB, 3 s, gitignored).
- **Pool:** 33,077 films with a usable score. 16,750 of them have a real budget or revenue, and 33,024 have a synopsis vector.
- **Similarity:** a weighted average of
  - genre Jaccard 0.3;
  - theme Jaccard 0.2;
  - synopsis cosine 0.3, left out of the average without a synopsis;
  - era 0.1: exp(−years apart / 10);
  - budget level 0.1: exp(−|log difference|), and 0.5 for a film with no reported budget.
- **Selection:** only films released strictly before the planned date. Of the 50 most similar, the ones with money come first.
- **Speed:** loading takes 0.15 s; a query takes about 8 ms with a synopsis and 6 ms without.
- **Examples** (each film judged at its release date, with its real budget):
  - *Avengers: Infinity War*: Green Lantern, Avengers: Age of Ultron, Captain America: Civil War, Fantastic Four, X-Men: Days of Future Past;
  - *Paddington 2*: Paddington first, then Diary of a Wimpy Kid: The Long Haul;
  - *La La Land*: Letters to Juliet, Love & Other Drugs, Prime;
  - *Get Out*: small horror films (Sinister, Goodnight Mommy), but also obscure ones scored 4.5.

### Changes from the plan (task 4)

- **The vectors are float16 on disk and float32 in memory.** Converting them on every query took about 40 ms.
- **`Index.build` takes the theme names,** so the test database (one theme) can build an index.

### Checks (task 4)

- **6 new tests (46 in `tests/test_explain.py`):**
  - an identical film scores 1, with or without a synopsis;
  - a film released on the planned date or later is never returned;
  - films with money come first, and the others only fill in;
  - an unknown budget counts as half close (hand-computed);
  - results are JSON-ready, and the index round-trips through the file;
  - the index builds from the small test database.
- **Mutation checks:**
  - allowing same-day films (`>` instead of `>=`) fails a test;
  - dropping "money first" fails a test.
- **On the real index,** all 12 example queries returned only films released before their date. 218 tests passing.

### Inputs for the notebook (task 7)

- **Obscure films come up:** *Get Out* gets *Scorned* and *Treehouse*, both scored 4.5. A small tie-break towards well-known films (vote count) could help. Vote count is post-release, but only for past films, so it would never be a model input.
- **There is no language term:** *Parasite* gets English-language films (*Wild Tales* is Spanish). Adding the original language as a sixth part is worth a look.
- **Revenue equal to budget:** *Treehouse* shows $4.4M for both, which is probably one figure copied into the other on TMDB. 35 of the 10,421 films with both figures (and not suspect) have them exactly equal. The Day 2 cleaning rules don't flag this, so the films are shown as reported. This is not a model change (Day 6 froze the models); it could become a display note.

### Task 5: the `predict()` package

- **Module:** `ml/predict.py`.
  - `Predictor.load(out_dir, db_path)` loads the all-data models, the feature context (from a read-only database connection), the rough rule and the comparables index, after checking every model file against `manifest.json`. It takes 11 s here, once.
  - `predictor.predict(form)` returns a JSON-ready dict. `predict(form)` does the same with a predictor loaded once.
  - An invalid form raises `InvalidForm`; its `.errors` field-by-field are the contract's messages.
- **Steps:** validate, then features, budget, revenue (budget given or estimated), score, drivers (with sentences), comparables and warnings. A synopsis is embedded once and used for both the features and the comparables.
- **Output:**
  - `budget`, `revenue` and `score`: low / middle / high, a text range and a rough flag (score is never rough);
  - revenue also carries `mode` and `budget_used`;
  - budget also carries `given` and `comparison`, the sentence "Your budget of $X is below / at the low end of / within / at the high end of / above what similar films usually cost", with a 5% margin at each end;
  - `drivers` per target (`up` / `down`), `comparables`, `warnings`, `model_version` and `as_of`.
- **Warnings:**
  - `big_budget`: $150M or more, given or estimated;
  - `new_director` and `new_actors`: a name we can't match;
  - `no_country` and `no_studio`;
  - `future_release`: a year after the data ends.
- **Manifest:** `uv run python -m ml.predict manifest` writes `ml/artifacts/final/manifest.json`, model version `2026-10-21.849304a7`.
  - It records sha256 checksums of the 9 models, the 3 metadata files and the rough rule, which it copies into `ml/artifacts/final/`.
  - It also records the training years, the corrections, the LightGBM version and the `final-models` tag.
  - The comparables index is listed but not checksummed, because it is rebuilt from the database.
- **Three example forms** (all-data models, 30 runs each after loading):

| Form | Budget | Revenue | Score | Median / p95 time |
| --- | --- | --- | --- | --- |
| Franchise blockbuster (Russo brothers, Avengers cast, Marvel, $300M, May 2027) | $180M–$600M | $500M–$3.6B (given) | 6.4–8.2 | 151 / 162 ms |
| Small drama (Gerwig, Ronan, Pugh, Chalamet + 2 unknown, A24, no budget, Oct 2026) | $5.2M–$62M, rough | $2M–$170M (estimated), rough | 6.2–7.6 | 158 / 165 ms |
| Unknown cast (horror, new director and actors, $2M, no studio or country) | $18K–$7M, rough | $38K–$14M, rough | 4.8–6.9 | 148 / 163 ms |

- **Comparables for the blockbuster:** The Flash, Guardians of the Galaxy Vol. 3, Transformers: Rise of the Beasts, Avengers: Infinity War, Captain Marvel.
- **Comparables for the small drama:** Janet Planet, How to Make Millions Before Grandma Dies, Summer Hours, Sentimental Value, And Their Children After Them.

### Changes from the plan (task 5)

- **Two of your decisions after seeing the output:**
  - **Warnings for an empty country or studio.** For the horror form, "no production country" pulled revenue down by about 38% (`country_unknown`), because past films missing it are mostly obscure.
  - **The timing sentence names its main part.** For 2026 films the year contributes about −16% to revenue and the month far less. The sentence now reads "Releasing in 2026 (recent films earn less in our data)" or "Releasing in December (holiday season)". `drivers.main_feature` picks the part; the name never reaches the text.
- **The rough rule is copied into `ml/artifacts/final/`,** so the folder holds everything the app reads except the database.
- **The manifest checks the models when the predictor loads:** a changed `.joblib` or metadata file stops the app from loading.

### Checks (task 5)

- **New `tests/test_predict.py` (14 tests),** on the small test database with small models:
  - the full output is JSON-ready, with ordered ranges, at most 5 drivers per target and no raw names;
  - estimated mode uses the budget model's middle and flags the budget driver;
  - the same budget given gives the same middle and a range that is never wider;
  - comparables are earlier films only, for three planned dates;
  - invalid forms are refused field by field;
  - each warning appears exactly when it should;
  - names come from the database;
  - a budget near an edge is "at the low / high end" (7 cases);
  - the manifest records and checks every file, and a swapped model file is caught.
- **2 new tests in `tests/test_explain.py`** for the timing wording and `main_feature`.
- **Mutation checks:**
  - dropping the "estimated" flag fails 1 test;
  - removing the low-end margin fails 2.
- 234 tests passing.

### Inputs for later tasks

- **Golden examples on the real models (task 6):** the three forms above. Their speed is already about 150 ms against the 400 ms target.
- **Loading takes 11 s,** most of it the feature context. The Day 8 API loads it once at startup.
- **Day 9 (Docker):** the manifest checksums the `.joblib` files. An image built with retrained models needs a new manifest, written on purpose.

### Task 6: tests

- **Already covered in tasks 1–5, offline** (62 tests in `tests/test_explain.py` and `tests/test_predict.py`):
  - drivers add up to the middle;
  - no raw feature names appear;
  - comparables never come from the future, including on the planned date itself;
  - both revenue modes;
  - invalid forms are refused;
  - warnings, and the manifest.
- **New `tests/test_golden.py` (15 tests)** runs `predict()` on the real all-data models for three fixed forms: franchise blockbuster, small drama and unknown cast. It is skipped when `data/movies.db`, the `.joblib` models or the comparables index are missing.
  - **Rules that hold whatever the numbers:**
    - the models match `manifest.json`;
    - outputs are complete, JSON-ready and ordered;
    - comparables come before the planned date;
    - each form's mode, warnings and main drivers (for example, the blockbuster's revenue is pushed up by budget, franchise and studio, and *Avengers: Infinity War* is among its comparables);
    - the same form gives the same output;
    - the median of 10 calls is under 400 ms, and the slowest under 800 ms.
  - **Snapshot:** `tests/golden/predictions.json` holds each form's ranges to 6 figures, mode, rough flags, budget position, driver sentences, comparable ids and warning codes. Rewrite it only on purpose, with `UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py`.
- **Suite time:** `make test` now takes about 26 s instead of 7 s, of which 11 s is loading the real predictor once. 249 tests passing.

### Changes from the plan (task 6)

- **A golden snapshot on top of the rules,** so any change to models, features, wording or comparables shows up in the tests.
- **`budget_used` is the creator's exact budget in given mode.** The golden test found $299,999,999.9999998, from taking the log and back.

### Checks (task 6)

- **Mutation checks against the golden tests:**
  - "slightly" reworded to "a little" fails the snapshot;
  - dropping the score correction (`q=0`) fails it;
  - swapping the genre and theme weights in comparables fails 2 tests.
- **A blind spot, covered offline:** the golden forms are all set in 2026–27, after the data ends, so their comparables can't catch a future film. The offline tests (`test_comparables_never_come_from_the_future`, `test_comparables_are_earlier_films_only`) cover that.

### Task 7: sanity notebook

- **Notebook:** `notebooks/07_explanations.ipynb`, which runs top to bottom (executed with `jupyter nbconvert --execute`).
  - Sections 1–4 use the ≤2015 models on 2016–18.
  - Section 5 runs six famous films through `predict()` with the all-data models. Each film is judged at the 1st of its release month. These models saw the films in training, so the section shows the explanations, not accuracy.
  - The test years are only shown (*Parasite*).
- **Strength cut-offs (your decision): +50% / +20% for money,** replacing +25% / +10%. Score keeps 0.3 / 0.1 points.

| 2016–18, top 5 drivers | +25% / +10% (plan) | +50% / +20% (chosen) | 2× / +25% |
| --- | --- | --- | --- |
| Revenue strong / moderate / slight | 72% / 27% / 2% | 30% / 53% / 17% | 11% / 60% / 28% |
| Revenue top driver strong | 99% | 87% | 52% |
| Budget strong / moderate / slight | 60% / 37% / 3% | 35% / 38% / 27% | 11% / 49% / 40% |

- **Median driver sizes (revenue, drivers 1–5):** +104%, +48%, +35%, +26%, +20%. For score: 0.32, 0.18, 0.12, 0.08 and 0.06 points (13% strong, 44% moderate, 43% slight).
- **What drives what:**
  - revenue's top driver is budget for 70% of films, the studio for 9%;
  - budget's is the studio for 73%, the cast for 14%;
  - score's is the cast for 44%, genre for 26%, runtime for 19%.
- **Inside studio for budget:** 90% of the group is `company_budget`, the companies' earlier budgets; `major_studio` is 6%.
- **Comparables weights (your decision): add language 0.1 and raise budget to 0.2.** Measured on 600 films from 2016–18 with a real revenue:

| Weights | Comparables' revenue MAE log | Score MAE | Same language | 200+ votes |
| --- | --- | --- | --- | --- |
| Plan | 1.883 | 0.602 | 60% | 73% |
| + language 0.1 | 1.875 | 0.586 | 85% | 74% |
| Budget 0.2 | 1.833 | 0.599 | 60% | 73% |
| **+ language 0.1, budget 0.2 (chosen)** | **1.802** | **0.584** | **84%** | **74%** |
| Chosen + well-known tie-break 0.1 | 1.931 | 0.572 | 83% | 83% |
| Synopsis 0.15 | 1.903 | 0.622 | 57% | 73% |

- **Famous films:**
  - *Avengers: Infinity War*: revenue is driven up by its budget, the franchise and Marvel.
  - *Get Out*: revenue is driven down by its small budget, small studios and a first-time director. Its real $340M is far above its range of $160K–$59M.
  - *La La Land*: score is driven up by Damien Chazelle's earlier films.
  - *Paddington 2*: Paddington is its first comparable.
  - *Parasite*: gets a Korean comparable, *The Yellow Sea*.

### Changes from the plan (task 7)

- **Strength cut-offs and comparables weights** changed as above. Both decisions are recorded in the plan document.
- **`Index.query` and `similarity` take the original language,** and the index stores it. The index was rebuilt.
- **The golden snapshot was rewritten on purpose:**
  - only strength words and comparables changed;
  - every range and warning stayed the same, and the snapshot test failed first as it should.

### Checks (task 7)

- **Tests:**
  - the strength tests use the new cut-offs (+50% counts as strong, and so does −33%);
  - a new test checks the language weight (0.1 out of 1.2);
  - the unknown-budget test was recomputed by hand with budget 0.2.
- 250 tests passing.

### Surprises / inputs for wrap-up and Day 8

- **Breakouts stay outside the range** even for films the models saw (*Get Out*). The README should say that drivers explain the typical film like yours, not a breakout.
- **Some comparables are still obscure** (*Get Out*: small horror films scored 4.5–6). A fix would need a measure that doesn't pull revenue away from the film's own, so it is left as a limitation.

### Task 8: wrap-up

- **README:** a new section, "Explanations and `predict()`", covering drivers, groups, strength cut-offs, sentences, comparable films with the weights table, the `predict()` output, warnings, the manifest and the golden examples. Also:
  - the setup lists the comparables and manifest commands;
  - the folder table and the budget-comparison wording are updated;
  - four new Limitations: drivers describe the model, not causes; breakouts stay outside the range; empty optional fields count against a film; some comparables are obscure.
- **CLAUDE.md:** the new commands, the golden snapshot rule, the gitignored files, and the architecture of `ml/explain/` and `ml/predict.py`.
- **Plan document:** the Day 7 outcome line.

### Surprises / inputs for Day 8+

- **One entry point:** `ml.predict.Predictor.load()` (about 11 s) once in the FastAPI lifespan hook, then `predictor.predict(form)` per request (about 150 ms).
  - `InvalidForm.errors` maps fields to readable messages, ready for the 422 responses.
  - The output is already JSON-ready.
- **Thread safety:** `predict()` opens its own read-only SQLite connection for names, so the thread pool can share one `Predictor`. MiniLM loads on the first form with a synopsis, which makes that first call slower.
- **Comparables for movie pages (Day 8 "similar films"):** `Index.query` needs genres, themes, language, vector, year and budget. The index holds all of these for every pool film, so a movie page can query with the film's own row and its release day as `as_of`.
- **Day 9 (Docker):** the image needs `data/movies.db`, the 9 `.joblib` files, `comparables.npz` and the MiniLM files. `manifest.json` checks the models, so new models need a new manifest and golden snapshot.
- **Day 10 (form):** nudge creators to fill in the production country and studio, since empty fields lower the ranges (warnings `no_country` and `no_studio`). The 27 theme names come from `themes.json` (`load_themes()`); `contract.describe()` leaves the theme choices empty, so `meta/options` must add them.
- **`make test` takes about 25 s** because the golden examples load the real predictor. Without the database or models they are skipped, and the suite takes about 7 s.

## Audit after Day 7 (2026-10-22)

Asked by Dimitris: review everything from Day 1 for logic and science, test that the app stays within the bounds of logic, and measure performance. Decisions (asked today):
- the 2019+ test split stays locked, and its Day 6 numbers are quoted;
- films of 2026 are pulled from TMDB as a fresh holdout;
- clear code bugs are fixed, and anything touching the models becomes a proposal.

Write-up: `reports/audit.md`.

- [x] **Method review**, stage by stage (data, targets, leakage, track record, splits, models, calibration, metrics, drivers, domain sense), with sources checked by web search. No leak and no method error. Three data caveats became Findings 1–3.
- [x] **`tests/test_sanity.py`: 42 rule tests** on the real app models, about 55 s, all passing. They cover:
  - bounds, on the 3 golden forms and 60 real 2016–18 films;
  - no range narrower than 2q;
  - a monotone budget, over 12 budgets × 3 forms;
  - invariance to the synopsis and to list order;
  - estimated vs given mode;
  - 10 edge and 7 out-of-form inputs;
  - 5 matched-pair directions;
  - future-free comparables;
  - train/serve date drift.
- [x] **`ml/eval/audit.py`** (CLI `uv run python -m ml.eval.audit [validation|holdout|all]` → `reports/audit_metrics.md` / `.json`):
  - all 13 models are refitted, and their validation and backtest MAE match the reports exactly;
  - new measures: pinball loss, interval score, R², bias, bootstrap 95% CIs, and coverage by year, genre, language and budget.
- [x] **2026 holdout:** `ml.data.pull --years 2026 --out-dir data/holdout_2026` gave 1,199 films in about 1 min (gitignored). `data/movies.db` has the same checksum before and after. 609 films were 182+ days old.

### Stats

| | Revenue (given) | Budget | Score |
| --- | --- | --- | --- |
| Interval score 2016–18, B2 → LightGBM | 6.69 → 5.24 | 5.49 → 3.25 | 2.67 → 2.28 |
| R² 2016–18, B2 → LightGBM | 0.41 → 0.58 | 0.12 → 0.70 | 0.22 → 0.46 |
| LightGBM − B2 MAE, 95% CI | −0.27 to −0.18 | −0.64 to −0.53 | −0.12 to −0.09 |
| 2026 holdout films | 70 | 223 | 190 (182+ days) |
| 2026 MAE, B2 → app | 1.295 → 1.052 | 1.366 → 0.781 | 0.731 → 0.590 |
| 2026 coverage, app | 81.4% | 81.2% | 73.7% (60.0% under 182 days) |

### Changes from the plan

- **Score on the holdout uses films 182+ days old,** like revenue, because young films' scores were found to be still rising. Younger films are reported in a separate row.
- **Baselines on the holdout are fitted on ≤2018,** not 1960–2025, so that nothing reads the locked test split; the app models themselves saw 1960–2025.
- **Mutation "unsorted crossed quantiles" survives.** The app models' crossings never put p10 above p90, and `apply_q` clamps the ends to the middle, so both versions are valid. Kept as a design note, not a gap. A new rule (no range narrower than 2q) was added anyway.
- **The estimated-mode test was made strict** (the estimated range must be wider) after a mutation that gave estimated mode the "given" correction failed only the golden snapshot.
- **The planned "all 19 genres" and "runtime 1 / 400" edge cases** are out-of-form inputs (at most 5 genres, runtimes 40–300), so they are tested as rejections.

### Checks

- `make test`: 292 passed (250 + 42).
- Mutation checks:
  - same-day comparables → the sanity test fails;
  - estimated mode with the given correction → 3 sanity tests and 2 golden tests fail;
  - unsorted quantiles → survives (see above).
- `ml.eval.audit validation` reproduces `reports/metrics.md` with difference 0 for all 13 models, in 257 s.

### Findings for Dimitris (nothing changed; each would change frozen models or app numbers)

1. Young films' TMDB scores are still settling. Options:
   - a note on the score in the app (Day 8–10);
   - a maturity rule for the score target (needs a retrain).
2. Revenue is learned from the 13% of films that report money. Keep it as a Limitation.
3. Releases after 2025 stretch "years active". `predict()` could judge the track record at 2025-12-31 for later releases (about 5 lines; changes the golden snapshot).
4. Revenue plateaus above about $300M. Add a sentence to the big-budget warning.
5. The holdout is small. Rerun `ml.eval.audit holdout` after a 2027 pull.
6. Coverage is uneven in some groups: budgets under $10M, animation and romance scores. A per-group conformal correction (Mondrian CQR) needs a retrain.

### Inputs for Day 8

- `make test` now includes `tests/test_sanity.py` (the whole suite takes about 80 s with the database and models; the sanity tests are skipped without them).
- If Dimitris picks Finding 1's note or Finding 4's sentence, it is a text change in `ml/predict.py` warnings, plus a golden snapshot update.

### Follow-up: Findings 1A and 4 applied as text (2026-10-22, asked by Dimitris)

- `predict()` output: `score.note` = "TMDB scores of new films usually start higher and settle during their first year; this range is for the settled score." (`SCORE_NOTE` in `ml/predict.py`).
- The `big_budget` warning ends with "…and budgets above $300M don't raise the revenue estimate any further." (`PLATEAU_BUDGET`).
- `tests/test_golden.py`: the snapshot now also keeps the warning texts and the score note, so wording changes show up; two new asserts check both texts. The snapshot was rewritten with `UPDATE_GOLDEN=1`, and its diff contains only the new texts (no number, driver or comparable changed).
- `make test`: 292 passed. README warnings paragraph and two Limitations updated; `reports/audit.md` marks 1A and 4 as applied.
- Day 10 form: show `score.note` under the score range.

## Day 8: FastAPI backend (done 2026-10-22)

- [x] 0. Plan document: left untouched (decided by Dimitris). Today's decisions are recorded here and in the README:
  - our own in-memory rate limiter;
  - similar films from any year, never the film itself;
  - compare returns the changed fields and the middle shifts;
  - a packed in-memory autocomplete;
  - the History memory fix.
- [x] 1. Project structure (`backend/app/`, `make api`)
- [x] 2. Startup and database (lifespan, read-only connection per request, autocomplete index)
- [x] 3. Prediction endpoints (`/predict`, `/predict/compare`, cache, rate limit, 422s)
- [x] 4. Public endpoints (`/movies`, `/movies/{id}`)
- [x] 5. Form support endpoints (`/people`, `/companies`, `/collections`, `/meta/options`, `/health`)
- [x] 6. Tests (`tests/test_api.py`, `tests/test_api_golden.py`)
- [x] 7. Wrap-up and commit

### Task 1: project structure

- **New dependencies:** `fastapi` 0.159.1 and `uvicorn` 0.54.0 (with pydantic 2.14.1 and starlette 1.9.0). `make api` runs `uvicorn backend.app.main:app --reload --port 8000`.
- **Layout (`backend/app/`):**
  - `main.py` has `create_app(settings, predictor, lookups)`; tests inject a small `Predictor`, so the real models never load offline;
  - `settings.py` reads `MOVIES_DB`, `MODELS_DIR`, `CORS_ORIGINS` (default `http://localhost:5173`), `RATE_LIMIT` (30) and `CACHE_SIZE` (1000);
  - one router per resource in `routers/`, plus `schemas/`, `repo/` and `services/`;
  - CORS allows GET and POST from the configured origins only.
- **Real start:** with the real models the app was ready in about 14 s, with `/docs` served.

### Changes from the plan (task 1)

- **The router test reads the OpenAPI paths.** FastAPI 0.159 wraps included routers (`_IncludedRouter`), so `app.routes` no longer lists their paths.

### Checks (task 1)

- 5 tests: the injected predictor is used, docs and schema are served, every route is under `/api/v1`, CORS allows only the frontend origin, and settings come from the environment.

### Task 2: startup and database

- **Lifespan:** it loads the `Predictor` (manifest check, models, feature context, comparables), then builds the autocomplete lookups, the prediction service and the rate limiter onto `app.state`, plus `load_seconds` and `started` for `/health`.
- **Database:** `deps.get_db` opens one read-only connection per request (`mode=ro`) and closes it afterwards. It needs `check_same_thread=False` because sync endpoints run in the thread pool. A missing file is an error, never a new empty database.
- **Autocomplete (`services/lookups.py`):**
  - 29,012 directors, 321,259 actors, 43,310 companies and 4,263 franchises;
  - any word of a name can start the match ("hanks", "tom ha"), most films first, at most 10;
  - it builds in 2.3 s and takes 33 MB;
  - a lookup takes under 1 ms (7 ms for "a"; about 39 ms for the very first search).

### Changes from the plan (task 2)

- **A packed autocomplete index instead of plain lists (decided by Dimitris).** Plain Python lists of the 350k people and their 730k word keys took about 207 MB, which threatened Day 9's 450 MB gate. Names and keys now sit in byte blobs with int64 offsets, searched by binary search. Plain SQL per request was the other option (50–70 ms, up to about 140 ms for one letter).
- **The History memory fix (asked by Dimitris, outside the plan).**
  - The whole app took 1,236 MB after startup, of which `History` was about 874 MB: 350k small `_Track` objects with 8 numpy views each.
  - The tracks are now offsets into a few flat arrays: `row_offsets`, `days`, a running sequel count, and one `_Values` (days, values, offsets) each for revenue, score and budget. People are found by `np.searchsorted` in sorted ids per role. The merge now takes only the 5 numeric columns.
  - `History` now keeps 108 MB (43 MB of arrays plus the 41 MB name lookup). Building it briefly peaks at 476 MB (493 MB before the smaller merge).
  - **Identical:** the features table rebuilt in memory (79,199 × 177) matched the stored one bit for bit, after the rewrite and again after the merge change. The golden snapshot and all feature, leakage and sanity tests are unchanged.

| Whole app (Windows, real models) | Before | After |
| --- | --- | --- |
| After startup | 1,236 MB | 639 MB |
| After 50 more predictions with a synopsis (MiniLM loaded) | — | 746 MB |
| Startup | 14 s | about 10 s |

### Checks (task 2)

- 7 tests:
  - startup builds the lookups from the settings' database;
  - each request gets its own connection, closed after it, where a DELETE fails with "readonly";
  - a missing database raises and leaves no file;
  - the index rules: any word, running on into later words, case and spaces ignored, accents kept, most films first, limit, empty queries.

### Task 3: prediction endpoints

- **`POST /api/v1/predict`:**
  - the `PredictForm` schema (strict types, unknown fields refused) documents the form in `/docs`;
  - the rules stay in `contract.validate`, through `PredictionService`;
  - the output is `predict()`'s dict, plus `cached` and full poster URLs for the comparables;
  - the response models document every field for the Day 10 TypeScript types.
- **`POST /api/v1/predict/compare`:**
  - the body is `{base, variants: 1–3}`; each variant lists only what it changes, and `null` clears a field;
  - `differences` gives the changed fields, the money middles as a ratio, the score as points, and `mode_changed`;
  - all forms are checked first, so one 422 lists every problem as `base.x` or `variants.i.x`.
- **Cache:** an LRU of 1,000 entries keyed by the validated form as canonical JSON, guarded by a lock. The prediction itself runs outside the lock.
- **Rate limit:** 30 requests a minute per client IP, a sliding window shared by both endpoints. The 31st gets 429 "Please try again in a minute" with `Retry-After`.
- **Errors (`errors.py`):** every 422 is `{"detail": "Some fields need fixing", "errors": {dotted.field: message}}`. A shape error also lists every rule problem the contract finds, using the contract's wording ("must be a number", "unknown field", "required").
- **Measured over HTTP (real models):**
  - a prediction takes a median of 167 ms, about 400–500 ms on the first call (MiniLM loading), and about 3 ms from the cache;
  - compare with 3 variants takes about 0.53 s;
  - 12 different forms sent 8 at a time gave exactly the same answers as one at a time.

### Changes from the plan (task 3)

- **Shape errors list the rule errors too.** At first a Pydantic error hid the form's other problems (missing themes, year 2040), so the handler now merges the contract's messages for the whole body.
- **0 or 4 variants** read "needs 1 to 3 variants" instead of Pydantic's wording.
- **Behind a proxy**, `request.client.host` is the proxy. Day 14 must read `X-Forwarded-For`; this is in the README Limitations.

### Checks (task 3)

- 12 tests:
  - both revenue modes equal `predict()`, and comparables get posters;
  - the same film written two ways is one cache entry, and the cache drops the least recently used form;
  - rule errors and shape errors name every field;
  - compare's differences match separate predictions, and errors name the variant and field;
  - the 31st request is refused, the window slides and forgets idle clients;
  - `merge`, and the OpenAPI schema (required fields, limits, 422 and 429).
- Mutations:
  - a cache keyed on the raw form → 2 tests fail;
  - a rate limit off by one → 2 tests fail.

### Task 4: public endpoints

- **`GET /api/v1/movies`:**
  - `q` turns every word into a quoted prefix for FTS5 (`"spider"* "man"*`), so typed text is never syntax;
  - filters: `genre`, `year_from` / `year_to`, `language`, `has_money` (budget and revenue known, not suspect);
  - `sort` is popularity (default), newest, title or score (score only over films with a usable score);
  - `page` and `page_size` (at most 48), returning items, total, page, page_size and pages.
- **`GET /api/v1/movies/{id}`:** facts, our story themes, franchise, companies, countries, spoken languages, top 15 cast, key crew in job order, money (nominal and 2025 $, suspect flag and reason, incomplete flag), rating, posters (`w342` / `w780`) and 6 similar films. An unknown id is a 404.
- **Similar films:** `Index.query(..., as_of=None, exclude=id)` and `Index.row(id)` in `ml/explain/comparables.py`; the creator's comparables keep the date rule. A film outside the pool is matched on genres, themes, language, era and budget, without a synopsis.
- **Caching:** `Cache-Control: public, max-age=3600` on both endpoints.
- **On the real database:** 5–90 ms per request.
  - "spider-man" → 43 films, Spider-Man first;
  - "amelie" finds *Amélie*;
  - *Avengers: Infinity War*'s similar films are *Endgame*, *Green Lantern*, *Age of Ultron*, *Civil War*, *Justice League* and *Days of Future Past*.

### Changes from the plan (task 4)

- **A "relevance" sort (bm25) was tried and removed.** It put *LEGO Marvel Avengers* first for "avengers"; popularity orders searches better.
- **Movie pages show the film's themes** (not in the plan); they come from the same `themes.json` the model uses.
- **The default order is TMDB's popularity on the pull day**, a trending number: the first page starts with *Clue* (1985). It is a README Limitation; vote count would put the best-known films first.

### Checks (task 4)

- 21 tests:
  - paging through all 300 fixture films with the cache header;
  - prefix search in titles and overviews;
  - 11 hostile FTS inputs, and punctuation only finds nothing;
  - filters that combine, every sort, and named bad parameters;
  - a full movie page;
  - similar films never the film itself, and from the first year (2008) too, where a date rule would leave none;
  - a film outside the pool; 404 and 422 ids.
- Mutations:
  - letting a film list itself → 2 tests fail;
  - adding a date rule → 3 tests fail.

### Task 5: form support endpoints

- **Autocomplete:** `GET /people?role=director|actor&q=`, `/companies?q=` and `/collections?q=` return `[{id, name, n_films}]`, at most 10, cacheable for an hour. They answer in 2–10 ms on the real data: "tom ha" → Tom Hanks (85 films), Tom Hardy…; "gerwig" → Greta Gerwig; "marvel" → Marvel Studios (75); "harry pot" → Harry Potter Collection.
- **`GET /meta/options`:**
  - `contract.describe()` with the 27 themes filled in, plus genres and certifications;
  - the 60 most common languages and countries with counts;
  - months, and suggested release years from this year to +4, never past the contract's last year (2035);
  - it is built once per process: 30 ms the first time, about 3 ms after.
- **`GET /health`:** status, API and model version, what each model was trained on, the database build date and film count, start time, uptime, load time and the prediction cache's size, hits and misses. About 14 ms, `no-store`.

### Changes from the plan (task 5)

- **Languages and countries come as ISO codes only.** The browser can name them (`Intl.DisplayNames`), so no name table was added.
- **`/health` runs a COUNT on the database**, so a broken database makes it fail instead of reporting "ok".

### Checks (task 5)

- 6 tests:
  - people by role, most films first, with roles kept apart;
  - company and franchise autocomplete, and parameter errors;
  - options against the contract with themes filled in;
  - the year cap;
  - health's models, database and cache counts after one fresh and one cached prediction.

### Task 6: tests

- **`tests/test_api_golden.py`** (10 tests on the real models and database; skipped without them):
  - the golden forms over HTTP equal `predict()` and the golden snapshot;
  - a fresh prediction over HTTP takes a median under 400 ms;
  - compare, autocomplete, movie pages, options and health on the real data.
- **Added to `tests/test_api.py`:**
  - `ENDPOINTS` pins each of the 9 endpoints to the test that covers it, and the served set must equal it;
  - a wrong method is a 405;
  - 8 parallel requests with an empty cache equal the sequential answers.

### Changes from the plan (task 6)

- **Optional comparison fields are explicit `null` over HTTP.** When no budget is given, the response model writes the comparison's optional fields (`budget`, `position`, `ratio`, `sentence`) as `null`, where `predict()` leaves them out. That suits the generated TypeScript types, so the golden HTTP test treats missing and `null` as the same.

### Checks (task 6)

- A mutation adding an untested `/ping` endpoint fails the endpoint pin.
- `make test`: 356 passed in about 1.5–2 min (64 API tests: 54 offline, 10 on the real models).

### Task 7: wrap-up

- **README:**
  - a new "API" section: endpoint table, example request, prediction, compare, errors, limits and caching, search and lookups, measured timings and memory, and the tests;
  - the `make api` setup line, the `backend/` folder row, and the test time (about 2 min);
  - two new Limitations: popularity on the pull day; the rate limit behind a proxy.
- **CLAUDE.md:** the `backend/app/` architecture, `make api`, and the two API test files.
- **Commit:** `4b28ac1` on `day6`.

### Surprises / inputs for Day 9+

- **The memory gate is the biggest Day 9 risk.** The app takes 639 MB after startup and 746 MB once MiniLM loads, against a 450 MB gate. The biggest parts:

  | Part | Memory |
  | --- | --- |
  | Python libraries | about 180 MB |
  | History | 108 MB kept; a 476 MB peak while building, which Windows doesn't return |
  | MiniLM | about 105 MB once a synopsis comes in |
  | Comparables index | about 77 MB |
  | Models | about 43 MB |
  | Lookups | about 33 MB |

  Linux in Docker may return the build peak differently, so measure there first. The options already in the plan are an int8 encoder and smaller indexes; the History name lookup (41 MB) and the build peak are further ones.
- **Docker:**
  - the image needs `data/movies.db`, the 9 `.joblib` files and `manifest.json` in `ml/artifacts/final/`, `comparables.npz` and the MiniLM files;
  - the healthcheck is `GET /api/v1/health`;
  - one uvicorn worker, because the cache and rate limiter are per process;
  - `CORS_ORIGINS` must list the frontend's origin.
- **Smoke script:** `/health`, the three golden forms through `/predict`, and one `/predict/compare`. The golden HTTP test already does this in-process.
- **Day 10:**
  - generate the TypeScript types from `/openapi.json`;
  - required fields are documented in `PredictForm`, and optional fields are explicit `null`s in responses;
  - map 422 `errors` keys straight to form fields (`variants.1.budget` for compare), and a 429 to "try again in a minute" using `Retry-After`;
  - fill the theme chips from `/meta/options`, and name languages and countries with `Intl.DisplayNames`;
  - show `n_films` in autocomplete;
  - show `score.note` under the score range.
- **Day 14:** behind Render's proxy the rate limit must read `X-Forwarded-For`.

## Day 9: Tests and Docker (done 2026-10-22)

- [x] 0. Plan document: left untouched, as on Day 8. Today's decisions are recorded here and in the README:
  - Dimitris installs Docker Desktop while tasks 1–3 run;
  - for the memory gate, measure first, then propose cuts;
  - his picks: scikit-learn/scipy training-only, the 8-bit MiniLM, prebuilt track records, `malloc_trim`, the packed name lookups, flat arrays for companies and franchises, and plain-string titles.
- [x] 1. End-to-end pipeline test (`tests/test_e2e.py`, `tests/fixtures/mini_raw.jsonl`)
- [x] 2. Time-travel leakage test (`tests/test_time_travel.py`)
- [x] 3. Test hardening (fuzzing, coverage, the manifest check at startup)
- [x] 4. Docker image (`backend/Dockerfile`, `.dockerignore`, the dependency groups, the slim database)
- [x] 5. Compose, Make and smoke test (`docker-compose.yml`, `scripts/smoke.py`)
- [x] 6. Memory and startup gate (407 MB after 100 predictions, under 450 MB)
- [x] 7. Wrap-up and commit

### Task 1: end-to-end pipeline test

- **The fake pull** (`tests/fixtures/mini_raw.py` generates `mini_raw.jsonl`; a test checks the file is current):
  - **200 normal films (2005–2020):** 20 directors and 60 actors who recur, budgets that grow with the director's level, about 30 French films, sequels in a "Mini Saga" collection, and real theme keywords from `themes.json` (heist 395, friendship 3230).
  - **13 messy records:** a $0 and a $7 budget, token box office, a budget in local currency, runtimes of 0 and 900 minutes, an unreleased film, a film pulled twice, a blank title, no votes, no genres, and a film still earning.
- **The test (11 tests, about 4 s, marked `slow`):** raw → `build_db` → `FeatureContext.load` with a fake text model → the features table → tiny real `LgbmQuantile` models → `conformal_q` from backtest fold 2 → `Chain` + score model → `Index.build` → `Predictor` → `create_app` → HTTP.
  - each messy record trips its cleaning rule exactly once;
  - the training views keep the bad money out;
  - the feature columns match `feature_list.json`;
  - the budget model ranks 2016–18 films with Spearman above 0.3, and revenue stays monotone in budget;
  - `/predict` works in both modes, with comparables only from before the date;
  - movie pages, autocomplete and health answer.
- **`make test-fast`:** skips the `slow` and `real_data` tests (registered markers; the golden, sanity and real-API tests are now marked `real_data`).

### Changes from the plan (task 1)

- **The feature context uses the app's real loader** with the committed vocab, themes and PCA, and real theme keyword ids. With the fixture's own vocab, the column names would not have matched `feature_list.json`.
- **The estimated-mode correction is 1.25 × the given one** in this test. The real calibration code reads the default database only, and the test checks the pipeline works, not its accuracy.

### Checks (task 1)

- A mutation removing `money_suspect` from the revenue view → 2 end-to-end tests fail.
- `make test-fast`: 289 tests in about 13 s.

### Task 2: time-travel leakage test

- **The rule:** copy the database, delete every film released on or after a cut date with all its links, then judge the deleted films at the cut date with both databases. Every feature must be identical.
- **Fixture, cut 1 January 2017:** a film is released on the cut day itself, so a same-day leak would show; identical.
- **Real database, cut 1 January 2010:** 300 films sampled from the 2010–2025 films the cut deletes; identical, in about 25 s. The copy is made with SQLite's backup API in a temp folder, and `data/movies.db` has the same checksum before and after.
- **Refits on train films:** the refitted vocab equals `vocab.json`; every theme keyword is among the 300 most common keywords in train films; the PCA refitted on the cached train vectors has the same mean and the same 16 directions.

### Changes from the plan (task 2)

- **The forms are built once, from the full database.** The first real run flagged *Scare Package* (2019), an anthology with 8 directors. `film_to_form` picks the most experienced director at the film's own release, after the cut, so that choice may rightly differ. Only the features at the cut date are compared.

### Checks (task 2)

- A history that counts films released on the judging day is caught (a check built into the test).
- A franchise that counts its later films is caught: films 29 and 79 would see 8 earlier films instead of 6, and the real-database version fails too.

### Task 3: test hardening

- **Fuzzing (`tests/test_fuzz.py`, hypothesis, derandomized, marked `slow`):**
  - 300 random bodies go to `/predict` and 100 to `/compare`;
  - they include valid forms with every edge, values just past the limits or of the wrong type, NaN and ±Infinity, huge and unicode strings, unknown fields and non-objects;
  - the answer must be a 200 with ordered, finite ranges, or a 422 naming a field;
  - 23% of `/predict` cases and 42% of `/compare` cases get a 200.
- **A real bug, fixed:** a whole-number field sent as NaN or Infinity crashed `int(value)` with an `OverflowError`, inside the 422 handler, so the API answered 500. `contract._number` now refuses non-finite values ("must be a number"). There are 12 new contract tests, and 15 tests fail without the fix.
- **The manifest at startup:** with one byte of `score_meta.json` changed, the app refuses to start ("score_meta.json changed") and serves nothing.
- **Coverage (`make coverage`):**

  | Part | Coverage |
  | --- | --- |
  | Everything | 78.0% |
  | The code the app runs | 92.2% |
  | Data, evaluation, baselines and calibration | 82.3% |
  | The one-off scripts (audit, ablation, tune, final) | 13.3% |

### Changes from the plan (task 3)

- **The fuzz requests send raw JSON.** httpx refuses NaN in `json=`, so at first no NaN ever reached the server; a real client can still send it.
- **A valid-form branch was added**, because at first only 5% of `/predict` and 0.8% of `/compare` cases got a 200.
- **Coverage is reported in parts.** The 80% aim isn't met overall (78.0%), only on the code the app runs.

### Task 4: Docker image

- **Docker Desktop 4.96.2** is installed per user (`%LOCALAPPDATA%\Programs\DockerDesktop`); the shell used the full path until the PATH was refreshed.
- **`backend/Dockerfile`:**
  - two stages: `uv` 0.13.4 installs the locked runtime dependencies, then `python:3.11-slim` with `libgomp1`;
  - a non-root user and one uvicorn worker;
  - a healthcheck on `/api/v1/health`.
- **`.dockerignore`** whitelists `pyproject.toml`, `uv.lock`, `ml/`, `backend/` and `build/`, and leaves out the ≤2015 `.joblib` models and the full `model.onnx`.
- **Dependencies:**
  - runtime is 10 packages;
  - the `ml` group holds `optuna`, `matplotlib`, `scikit-learn` and `onnx`, `joblib` is now a direct dependency, and `[tool.uv] default-groups = ["dev", "ml"]` keeps `uv sync` complete locally;
  - the app no longer imports `optuna`: `Chain.load` imported it through `calibrate` and `tune`, and now does so only for models without `q_estimated`;
  - the three sklearn imports (GroupKFold, PCA, KMeans) moved inside the training functions.
- **`scripts/slim_db.py`:** a read-only backup, the `features` table dropped, VACUUM, and an FTS integrity check. 309 → 220 MB.
- **The 8-bit MiniLM:**
  - `text.quantize_model()` writes `model_q8.onnx` (uint8, per output channel, 23 MB), and `make model` builds it;
  - only `FeatureContext.embed`, the creator's synopsis, uses it;
  - on 1,000 overviews it has a mean cosine of 0.993 with the full model, and 89% find the same nearest overview (plain int8: 0.956 and 71%);
  - the golden comparables are unchanged, and a new test keeps the two models close.
- **Size:** 1.03 GB → 928 MB unpacked (436 → 357 MB compressed); 984 MB once the prebuilt file was added in task 6.

### Changes from the plan (task 4)

- **scipy stays:** LightGBM imports `scipy.sparse` at load time (143 MB).
- **The 100 MB of precompiled bytecode stays**, so startup doesn't recompile everything.
- **The image is above the ~700 MB aim** (README Limitation).

### Task 5: compose, Make and smoke test

- **`docker-compose.yml`:** the backend, with `CORS_ORIGINS` for the Vite dev server and port 8080 for the Day 10 frontend container.
- **Make:** `make docker-build` (slim database, prebuilt context, image), `make docker-run` (`compose up -d --wait`) and `make smoke` (`URL=` for the live site).
- **`scripts/smoke.py`:** waits for `/health`, then runs 10 checks:
  - the model version;
  - the three golden forms, middles equal to the snapshot to 6 significant figures;
  - compare, a bad form's 422, search, the *Infinity War* page, autocomplete and options.

  It exits 1 on any failure.
- **The golden forms** moved to `tests/golden/forms.json`, so the smoke script doesn't import the test code.

### Checks (task 5)

- All 10 smoke checks pass against the container.
- A wrong expected version → the `/health` check fails, exit 1.
- Nothing listening → "no healthy API … after 4 s", exit 1.

### Task 6: memory and startup gate

- **Measured with `/proc/1/status` and `docker stats`:** 100 different forms with synopses, so nothing comes from the cache, with the rate limit raised for the run.

| In the container | Task 6 start | Prebuilt + `malloc_trim` | All cuts |
| --- | --- | --- | --- |
| After startup | 576 MB | 466 MB | 323 MB |
| Highest point, during startup | 651 MB | 578 MB | 489 MB |
| After 100 predictions | 663 MB | 551 MB | **407 MB** (`docker stats` 385 MiB) |
| Until healthy | 12 s | 8.5 s | 8.3 s |
| `/predict` median | 171 ms | 165 ms | 175 ms |

- **The breakdown that drove the cuts:**

  | Part | Memory |
  | --- | --- |
  | Imports | 136 MB |
  | History built with pandas | +401 MB, of which about 320 MB freed but kept |
  | History's name dict, after prebuilding | 83 MB |
  | Companies + Franchises dicts | 52 MB |
  | Comparables index (incl. 17 MB of fixed-width titles) | 72 MB |
  | Models | 38 MB |
  | Lookups | 33 MB |
  | MiniLM session | 41 MB |
- **The cuts (all decided by Dimitris):**
  - `FeatureContext.load(con, prebuilt=path)` with `save_prebuilt` / `python -m ml.features.build prebuilt` (57 MB, stamped with `built_at` and the film count, refused on a mismatch), used through `CONTEXT_FILE` in the image;
  - `release_free_memory()` (glibc `malloc_trim`) after the lifespan loads, plus `MALLOC_ARENA_MAX=2`;
  - `history.NameMap` (packed sorted names) for History's and Companies' name lookups;
  - `history.Groups` (offsets into flat arrays) for Companies and Franchises;
  - comparables titles and posters as plain strings.
- **Identical:**
  - the full features table (79,199 × 177) matches bit for bit, built at startup and from the prebuilt file;
  - all 344,445 person and 42,519 company names resolve as before;
  - the golden snapshot, time-travel, end-to-end and smoke checks pass.
- **Under `--memory=512m`, like Render Free:** no out-of-memory kill, 100 predictions and the smoke test pass. A full 1,000-entry cache should add about 10 MB (100 entries added about 1 MB).

### Changes from the plan (task 6)

- **Five cuts instead of "an int8 encoder and smaller indexes".** The measurements showed the memory was in History's build and in Python containers, not in the encoder.
- **My first estimate for the name lookup was too low:** 35 MB estimated, 83 MB measured.

### Task 7: wrap-up

- **README:**
  - new "Running with Docker" and "Testing" sections;
  - updated setup commands, the folder table (`scripts/`), the API memory line, and the API test count (55);
  - four new Limitations: the image size, the 489 MB startup peak, the 8-bit model against the full-model index, and memory depending on the system.
- **CLAUDE.md:**
  - the new commands and test markers;
  - the Docker architecture and the rules that keep memory down: no `ml`-group imports when the app starts, the prebuilt stamp, and packed `NameMap` / `Groups` instead of dicts of small objects.
- **Commit:** `73a2cce` on `day6` (36 files).

### Surprises / inputs for Day 10+

- **Day 10 (frontend in compose):**
  - add the frontend service to `docker-compose.yml`; `CORS_ORIGINS` already allows port 8080;
  - the smoke script should check the home page too, as the plan says;
  - the API's JSON schema for `openapi-typescript` is at `/openapi.json` in the running container.
- **Day 14 (Render):**
  - the image is 370 MB compressed;
  - startup peaks at 489 MB under a 512 MB limit, so watch the first deploy's memory graph;
  - the rate limit must read `X-Forwarded-For` behind the proxy;
  - run `make smoke URL=https://…` with `--wait 180` against a sleeping free instance.
- **A new database build** means rerunning `make docker-build`, which rebuilds `build/movies.db` and `build/context.joblib`. A stale context file is refused at startup, so it can't silently serve old track records.
- **`make test` now takes about 2–2.5 min**; `make test-fast` (307 tests, about 15 s) is the quick loop.
