# Learning curve

_Generated 2026-10-31 15:30 UTC by `uv run python -m ml.eval.learning_curve`. The middle (p50) LightGBM with the tuned settings, fitted on a random share of the train films (≤2015, seeds 0, 1, 2) and scored on validation (2016–18). MAE log for revenue and budget, MAE in points for score; the spread is the std over seeds (one fit at 100%)._

## revenue

| Share of train | Films | MAE (mean) | Spread (std) |
| --- | --- | --- | --- |
| 15% | 1,208 | 1.222 | 0.023 |
| 25% | 2,012 | 1.199 | 0.017 |
| 40% | 3,220 | 1.157 | 0.014 |
| 55% | 4,428 | 1.142 | 0.010 |
| 70% | 5,635 | 1.125 | 0.014 |
| 85% | 6,842 | 1.104 | 0.006 |
| 100% | 8,050 | 1.093 | 0.000 |

## budget

| Share of train | Films | MAE (mean) | Spread (std) |
| --- | --- | --- | --- |
| 15% | 1,700 | 0.666 | 0.011 |
| 25% | 2,834 | 0.647 | 0.005 |
| 40% | 4,534 | 0.631 | 0.006 |
| 55% | 6,234 | 0.625 | 0.004 |
| 70% | 7,934 | 0.617 | 0.004 |
| 85% | 9,634 | 0.614 | 0.005 |
| 100% | 11,334 | 0.614 | 0.000 |

## score

| Share of train | Films | MAE (mean) | Spread (std) |
| --- | --- | --- | --- |
| 15% | 3,302 | 0.531 | 0.003 |
| 25% | 5,504 | 0.516 | 0.002 |
| 40% | 8,806 | 0.507 | 0.001 |
| 55% | 12,109 | 0.504 | 0.002 |
| 70% | 15,411 | 0.499 | 0.001 |
| 85% | 18,714 | 0.499 | 0.003 |
| 100% | 22,016 | 0.496 | 0.000 |
