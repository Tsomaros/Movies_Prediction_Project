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
