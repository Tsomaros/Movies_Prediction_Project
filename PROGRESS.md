# Progress

## Day 1: Setup, data collection and first look

- [x] 0. Fix inconsistencies in the plan document (700 films/year, splits ≤2015 / 2016–18 / 2019+)
- [x] 1. Install tools: uv 0.13.4, GNU Make 4.4.1 (ezwinports), Python 3.11 via uv
- [x] 2. README skeleton with targets
- [x] 3. Repo setup
- [ ] 4. TMDB client + offline tests
- [ ] 5. Pull script + offline tests
- [ ] 6. Smoke test (20 films), then full pull
- [ ] 7. Exploration notebook `notebooks/01_first_look.ipynb` → `data/day1_summary.json`
- [ ] 8. Wrap-up and commit

### Notes

- Used `ezwinports.make` instead of `GnuWin32.Make`: same GNU make, current version (4.4.1 vs 3.81), and winget adds it to PATH.
