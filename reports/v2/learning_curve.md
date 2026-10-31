# Learning curve

_Generated 2026-10-31 17:04 UTC by `uv run python -m ml.eval.learning_curve`. The middle (p50) LightGBM with the tuned settings, fitted on a random share of the train films (≤2015, seeds 0, 1, 2) and scored on validation (2016–18). MAE log for revenue and budget, MAE in points for score; the spread is the std over seeds (one fit at 100%)._

## revenue

| Share of train | Films | MAE (mean) | Spread (std) |
| --- | --- | --- | --- |
| 15% | 1,267 | 1.228 | 0.012 |
| 25% | 2,112 | 1.199 | 0.007 |
| 40% | 3,378 | 1.172 | 0.007 |
| 55% | 4,645 | 1.160 | 0.001 |
| 70% | 5,912 | 1.149 | 0.002 |
| 85% | 7,179 | 1.135 | 0.001 |
| 100% | 8,446 | 1.133 | 0.000 |

## budget

| Share of train | Films | MAE (mean) | Spread (std) |
| --- | --- | --- | --- |
| 15% | 1,853 | 0.862 | 0.020 |
| 25% | 3,089 | 0.808 | 0.008 |
| 40% | 4,942 | 0.800 | 0.007 |
| 55% | 6,796 | 0.783 | 0.005 |
| 70% | 8,649 | 0.776 | 0.001 |
| 85% | 10,503 | 0.772 | 0.002 |
| 100% | 12,356 | 0.766 | 0.000 |

## score

| Share of train | Films | MAE (mean) | Spread (std) |
| --- | --- | --- | --- |
| 15% | 3,308 | 0.526 | 0.004 |
| 25% | 5,514 | 0.520 | 0.002 |
| 40% | 8,822 | 0.512 | 0.005 |
| 55% | 12,131 | 0.506 | 0.003 |
| 70% | 15,439 | 0.501 | 0.002 |
| 85% | 18,748 | 0.500 | 0.001 |
| 100% | 22,056 | 0.498 | 0.000 |
