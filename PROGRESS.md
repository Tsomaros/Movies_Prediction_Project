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

### Pull stats (2026-10-21)

- 46,199 films, 1960–2025 (700 per year; 2005 has 699). 0 missing (404), 0 failed, 0 duplicates.
- About 39 min at 19.9 requests/second; `data/raw/tmdb_movies.jsonl` is 126 MB and not in git.
- A rerun fetches nothing (resume check passed).
- TMDB caching rule: re-pull or delete the raw data by 2027-04-21.

### Key numbers (details in the notebook's Findings)

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

### Build stats (2026-10-21)

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
