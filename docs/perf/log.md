| Task | Metric | Before | After | Kept? |
|------|--------|--------|-------|-------|
| 1 | Timing middleware, bench.py, perf_snapshot/perf_check, baseline | n/a (tool) | n/a (tool) | n/a (not a speed change) |
| 2 | Runtime import audit + guard test (tests/api/test_runtime_imports.py): no ml-group package on the serving path; no unused runtime dependency | n/a (guard) | n/a (guard) | n/a (not a speed change) |
| 2 | Image size: drop `tests`/`test` folders from the runtime venv (builder stage) | 1.51 GB (1,513 MB) | 1.40 GB (1,397 MB), -116 MB | Kept |
| 2 | Throttled startup (0.1 CPU, start -> /health 200) | 95 s (same-day rerun of the old image; baseline 86-100 s) | 80 s | Kept (within noise; no claim) |
| 2 | Idle RAM, throttled, 20 s after health | 312 MiB | 315 MiB | n/a (unchanged, within noise) |
| 2 | OMP_NUM_THREADS=1, PYTHONDONTWRITEBYTECODE=1, PYTHONUNBUFFERED=1, one worker, multi-stage, slim base, .dockerignore whitelist | - | - | already in place, no change |
| 2 | Split app/train requirements files | - | - | already in place, no change (pyproject groups; image installs runtime only) |
| 2 | Replace scikit-learn/MAPIE calibration with numpy | - | - | n/a: calibration is own CQR; sklearn is only imported inside training functions |
