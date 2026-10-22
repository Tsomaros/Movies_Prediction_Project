# Rolling backtest

_Generated 2026-10-21 17:54 UTC by `make evaluate`. Each fold is fitted on its train years and scored on the next three; the test split (2019+) is not used._

| Fold | Train | Test |
| --- | --- | --- |
| fold 1 | <=2009 | 2010-2012 |
| fold 2 | <=2012 | 2013-2015 |
| fold 3 | <=2015 | 2016-2018 |

## Revenue (log 2025 $)

**B0 global median**

| Fold | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 943 | 1.968 | 94% | 22.8% | — | 76.1% | 239.9× |
| fold 2 (2013-2015) | 905 | 1.992 | 92% | 24.1% | — | 75.7% | 274.4× |
| fold 3 (2016-2018) | 886 | 1.890 | 93% | 24.9% | — | 78.3% | 300.3× |
| mean | 911 | 1.950 | 93% | 23.9% | — | 76.7% | 271.5× |
| spread (std) | — | 0.043 | 1% | 0.9% | — | 1.2% | 24.7× |

**B1 genre median**

| Fold | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 943 | 1.905 | 92% | 23.2% | 0.267 | 76.6% | 201.8× |
| fold 2 (2013-2015) | 905 | 1.927 | 90% | 24.1% | 0.303 | 76.5% | 225.9× |
| fold 3 (2016-2018) | 886 | 1.796 | 91% | 26.2% | 0.314 | 78.6% | 240.1× |
| mean | 911 | 1.876 | 91% | 24.5% | 0.295 | 77.2% | 222.6× |
| spread (std) | — | 0.057 | 1% | 1.2% | 0.020 | 1.0% | 15.8× |

**B2 budget x genre multiple**

| Fold | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 943 | 1.292 | 70% | 41.0% | 0.739 | 80.8% | 52.3× |
| fold 2 (2013-2015) | 905 | 1.318 | 69% | 39.8% | 0.739 | 78.8% | 52.6× |
| fold 3 (2016-2018) | 886 | 1.316 | 71% | 39.8% | 0.709 | 79.7% | 53.4× |
| mean | 911 | 1.309 | 70% | 40.2% | 0.729 | 79.8% | 52.8× |
| spread (std) | — | 0.012 | 1% | 0.6% | 0.014 | 0.8% | 0.5× |

**LightGBM (tuned, calibrated)**

_Range correction learned on folds 1-2, so coverage there is fitted, not tested; fold 3 (2016-18) is the honest check. Settings tuned on folds 1-2 as well._

| Fold | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 943 | 1.129 | 65% | 45.9% | 0.805 | 79.4% | 30.5× |
| fold 2 (2013-2015) | 905 | 1.149 | 65% | 43.9% | 0.808 | 80.8% | 37.6× |
| fold 3 (2016-2018) | 886 | 1.093 | 66% | 46.8% | 0.807 | 83.6% | 36.2× |
| mean | 911 | 1.124 | 65% | 45.5% | 0.807 | 81.3% | 34.7× |
| spread (std) | — | 0.023 | 0% | 1.2% | 0.001 | 1.8% | 3.1× |

**LightGBM, budget estimated (calibrated)**

_Range correction learned on folds 1-2 with estimated budgets, so coverage there is fitted, not tested; fold 3 (2016-18) is the honest check._

| Fold | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 943 | 1.199 | 66% | 42.5% | 0.778 | 79.2% | 40.1× |
| fold 2 (2013-2015) | 905 | 1.242 | 72% | 40.3% | 0.773 | 81.0% | 49.5× |
| fold 3 (2016-2018) | 886 | 1.135 | 70% | 44.0% | 0.793 | 86.1% | 47.7× |
| mean | 911 | 1.192 | 69% | 42.3% | 0.781 | 82.1% | 45.7× |
| spread (std) | — | 0.044 | 3% | 1.5% | 0.008 | 2.9% | 4.1× |

## Budget (log 2025 $)

**B0 global median**

| Fold | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 1,354 | 1.428 | 89% | 30.3% | — | 81.1% | 104.6× |
| fold 2 (2013-2015) | 1,245 | 1.371 | 87% | 33.2% | — | 83.5% | 102.7× |
| fold 3 (2016-2018) | 1,162 | 1.272 | 80% | 35.7% | — | 83.1% | 97.7× |
| mean | 1,253 | 1.357 | 85% | 33.1% | — | 82.6% | 101.7× |
| spread (std) | — | 0.064 | 4% | 2.2% | — | 1.0% | 2.9× |

**B1 genre median**

| Fold | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 1,354 | 1.315 | 83% | 34.5% | 0.311 | 82.1% | 78.6× |
| fold 2 (2013-2015) | 1,245 | 1.296 | 83% | 34.6% | 0.318 | 83.0% | 76.7× |
| fold 3 (2016-2018) | 1,162 | 1.207 | 78% | 36.7% | 0.359 | 85.1% | 73.7× |
| mean | 1,253 | 1.273 | 81% | 35.3% | 0.329 | 83.4% | 76.4× |
| spread (std) | — | 0.047 | 2% | 1.0% | 0.021 | 1.3% | 2.0× |

**B2 genre median x sequel factor**

| Fold | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 1,354 | 1.311 | 83% | 34.9% | 0.329 | 82.6% | 77.8× |
| fold 2 (2013-2015) | 1,245 | 1.290 | 83% | 34.9% | 0.344 | 83.4% | 74.6× |
| fold 3 (2016-2018) | 1,162 | 1.193 | 78% | 37.3% | 0.389 | 86.0% | 72.0× |
| mean | 1,253 | 1.265 | 81% | 35.7% | 0.354 | 84.0% | 74.8× |
| spread (std) | — | 0.052 | 3% | 1.1% | 0.025 | 1.4% | 2.4× |

**LightGBM (tuned, calibrated)**

_Range correction learned on folds 1-2, so coverage there is fitted, not tested; fold 3 (2016-18) is the honest check. Settings tuned on folds 1-2 as well._

| Fold | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 1,354 | 0.701 | 46% | 65.0% | 0.854 | 79.9% | 8.5× |
| fold 2 (2013-2015) | 1,245 | 0.671 | 45% | 65.9% | 0.859 | 80.2% | 9.0× |
| fold 3 (2016-2018) | 1,162 | 0.613 | 39% | 70.9% | 0.859 | 84.3% | 8.1× |
| mean | 1,253 | 0.662 | 44% | 67.3% | 0.857 | 81.5% | 8.5× |
| spread (std) | — | 0.036 | 3% | 2.6% | 0.002 | 2.0% | 0.4× |

## Score (vote_average)

**B0 global median**

| Fold | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 2,881 | 0.753 | 0.727 | — | 78.7% | 2.20 pts |
| fold 2 (2013-2015) | 3,533 | 0.750 | 0.729 | — | 78.3% | 2.27 pts |
| fold 3 (2016-2018) | 3,600 | 0.692 | 0.685 | — | 82.6% | 2.30 pts |
| mean | 3,338 | 0.731 | 0.714 | — | 79.9% | 2.26 pts |
| spread (std) | — | 0.028 | 0.020 | — | 2.0% | 0.04 pts |

**B1 genre median**

| Fold | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 2,881 | 0.676 | 0.653 | 0.414 | 78.3% | 2.05 pts |
| fold 2 (2013-2015) | 3,533 | 0.669 | 0.654 | 0.431 | 79.7% | 2.04 pts |
| fold 3 (2016-2018) | 3,600 | 0.627 | 0.625 | 0.392 | 81.3% | 2.04 pts |
| mean | 3,338 | 0.657 | 0.644 | 0.412 | 79.8% | 2.04 pts |
| spread (std) | — | 0.021 | 0.013 | 0.016 | 1.2% | 0.00 pts |

**B2 genre median + director**

| Fold | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 2,881 | 0.633 | 0.610 | 0.529 | 79.0% | 1.91 pts |
| fold 2 (2013-2015) | 3,533 | 0.629 | 0.614 | 0.530 | 79.1% | 1.94 pts |
| fold 3 (2016-2018) | 3,600 | 0.602 | 0.599 | 0.485 | 81.0% | 1.96 pts |
| mean | 3,338 | 0.621 | 0.607 | 0.515 | 79.7% | 1.94 pts |
| spread (std) | — | 0.014 | 0.006 | 0.021 | 0.9% | 0.02 pts |

**LightGBM (tuned, calibrated)**

_Range correction learned on folds 1-2, so coverage there is fitted, not tested; fold 3 (2016-18) is the honest check. Settings tuned on folds 1-2 as well._

| Fold | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 2,881 | 0.513 | 0.505 | 0.715 | 79.8% | 1.67 pts |
| fold 2 (2013-2015) | 3,533 | 0.509 | 0.508 | 0.712 | 80.2% | 1.70 pts |
| fold 3 (2016-2018) | 3,600 | 0.496 | 0.501 | 0.687 | 81.0% | 1.68 pts |
| mean | 3,338 | 0.506 | 0.505 | 0.704 | 80.3% | 1.68 pts |
| spread (std) | — | 0.007 | 0.003 | 0.012 | 0.5% | 0.01 pts |
