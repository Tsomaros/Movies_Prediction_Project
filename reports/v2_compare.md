# v2 against v1

_Generated 2026-10-31 16:59 UTC by `uv run python -m ml.eval.compare_v2 compare`. Validation = fitted on train (≤2015), scored on 2016–18; backtest = the three rolling folds. The test split (2019+) is not used._

**Verdict: reject v2.**

- revenue validation MAE log 1.101 is not lower than v1's 1.090

Keep rule: revenue lower than v1 on validation and on the backtest mean, revenue validation coverage in 77–83%; budget and score no worse than v1 (validation and backtest mean) by more than v1's backtest std. `revenue_estimated` is reported only.

## Like for like

Films in both versions for the same target and part; both versions scored against v2's target.

| Target | Version | Metric | Validation | Backtest mean | Backtest std | Coverage | Films (val) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revenue | v1 | mae_log | 1.090 | 1.118 | 0.020 | 83.8% | 875 |
| revenue | v2 | mae_log | 1.101 | 1.113 | 0.008 | 82.3% | 875 |
| revenue_estimated | v1 | mae_log | 1.130 | 1.186 | 0.042 | 86.1% | 875 |
| revenue_estimated | v2 | mae_log | 1.147 | 1.188 | 0.031 | 82.5% | 875 |
| budget | v1 | mae_log | 0.604 | 0.656 | 0.039 | 84.6% | 1,148 |
| budget | v2 | mae_log | 0.586 | 0.649 | 0.045 | 84.0% | 1,148 |
| score | v1 | mae | 0.496 | 0.506 | 0.007 | 81.0% | 3,600 |
| score | v2 | mae | 0.497 | 0.504 | 0.006 | 80.0% | 3,600 |

## All films (v2)

v2 on every film it has, new ones included.

| Target | Version | Metric | Validation | Backtest mean | Backtest std | Coverage | Films (val) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revenue | v2 | mae_log | 1.133 | 1.135 | 0.010 | 82.4% | 998 |
| revenue_estimated | v2 | mae_log | 1.196 | 1.219 | 0.023 | 81.9% | 998 |
| budget | v2 | mae_log | 0.766 | 0.727 | 0.028 | 81.8% | 1,651 |
| score | v2 | mae | 0.498 | 0.505 | 0.006 | 79.9% | 3,633 |

## Films

| Target | Part | Shared | Target changed | v1 missing from v2 | New in v2 |
| --- | --- | --- | --- | --- | --- |
| revenue | validation | 875 | 0 | 11 | 123 |
| revenue | fold 1 | 929 | 0 | 14 | 70 |
| revenue | fold 2 | 890 | 0 | 15 | 106 |
| revenue | fold 3 | 875 | 0 | 11 | 123 |
| revenue_estimated | validation | 875 | 0 | 11 | 123 |
| revenue_estimated | fold 1 | 929 | 0 | 14 | 70 |
| revenue_estimated | fold 2 | 890 | 0 | 15 | 106 |
| revenue_estimated | fold 3 | 875 | 0 | 11 | 123 |
| budget | validation | 1,148 | 0 | 14 | 503 |
| budget | fold 1 | 1,339 | 0 | 15 | 154 |
| budget | fold 2 | 1,230 | 0 | 15 | 197 |
| budget | fold 3 | 1,148 | 0 | 14 | 503 |
| score | validation | 3,600 | 0 | 0 | 33 |
| score | fold 1 | 2,881 | 0 | 0 | 0 |
| score | fold 2 | 3,533 | 0 | 0 | 6 |
| score | fold 3 | 3,600 | 0 | 0 | 33 |
