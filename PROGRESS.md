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
