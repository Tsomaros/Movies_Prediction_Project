# Final test run

_Run once on 2026-10-21 by `uv run python -m ml.eval.final test`. Every model is fitted on films released up to 2018 and scored on the locked test split (2019+). Ranges are widened by corrections from out-of-fold predictions on all three backtest folds (2010–18)._

| Correction | q | Calibration films | Fold coverage before → after |
| --- | --- | --- | --- |
| revenue | +0.399 log | 2,734 | 65.4% → 80.0% |
| budget | +0.363 log | 3,761 | 58.7% → 80.0% |
| score | +0.159 pts | 10,014 | 69.9% → 80.0% |
| revenue, budget estimated | +0.505 log | 2,734 | 62.9% → 80.0% |

## Revenue (log 2025 $)

| Model | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 1,485 | 2.031 | 110% | 23.6% | — | 76.6% | 303.1× |
| B1 genre median | 1,485 | 1.973 | 106% | 24.4% | 0.237 | 76.1% | 240.2× |
| B2 budget x genre multiple | 1,485 | 1.455 | 82% | 36.2% | 0.664 | 77.6% | 53.9× |
| LightGBM (tuned, calibrated) | 1,485 | 1.230 | 76% | 41.1% | 0.761 | 77.4% | 33.8× |
| LightGBM, budget estimated (calibrated) | 1,485 | 1.266 | 78% | 38.7% | 0.744 | 78.2% | 41.7× |

**Without 2020–21**

| Model | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 1,163 | 1.989 | 98% | 23.2% | — | 77.0% | 303.1× |
| B1 genre median | 1,163 | 1.926 | 96% | 24.5% | 0.250 | 76.6% | 240.2× |
| B2 budget x genre multiple | 1,163 | 1.418 | 79% | 36.1% | 0.667 | 77.7% | 53.9× |
| LightGBM (tuned, calibrated) | 1,163 | 1.189 | 74% | 42.4% | 0.764 | 78.2% | 33.3× |
| LightGBM, budget estimated (calibrated) | 1,163 | 1.225 | 75% | 39.8% | 0.751 | 79.4% | 41.1× |

**Rough-estimate label** (frozen cut-offs)

| Model | Labelled | MAE log labelled / rest | Within 2× labelled / rest |
| --- | --- | --- | --- |
| LightGBM (tuned, calibrated) | 18% | 1.647 / 1.137 (1.45×) | 27% / 44% |
| LightGBM, budget estimated (calibrated) | 24% | 1.619 / 1.155 (1.40×) | 25% / 43% |

**budget size: B2 budget x genre multiple**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 534 | 1.684 | 94% | 27.9% | 0.292 | 70.2% | 53.9× |
| $10-50M | 621 | 1.458 | 89% | 37.0% | 0.255 | 78.9% | 53.9× |
| $50-150M | 222 | 1.124 | 65% | 45.5% | 0.347 | 85.6% | 53.9× |
| $150M+ | 108 | 0.987 | 51% | 52.8% | 0.191 | 89.8% | 53.9× |

**budget size: LightGBM (tuned, calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 534 | 1.357 | 80% | 36.7% | 0.558 | 79.4% | 59.2× |
| $10-50M | 621 | 1.231 | 75% | 39.8% | 0.522 | 78.9% | 33.7× |
| $50-150M | 222 | 1.013 | 69% | 50.9% | 0.597 | 74.8% | 12.4× |
| $150M+ | 108 | 1.040 | 70% | 50.9% | 0.397 | 63.9% | 6.4× |

**budget size: LightGBM, budget estimated (calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 534 | 1.421 | 90% | 33.7% | 0.544 | 80.7% | 73.1× |
| $10-50M | 621 | 1.266 | 76% | 38.3% | 0.467 | 78.7% | 41.6× |
| $50-150M | 222 | 1.028 | 67% | 45.9% | 0.563 | 74.3% | 15.3× |
| $150M+ | 108 | 0.988 | 63% | 50.0% | 0.454 | 71.3% | 7.9× |

**language: B2 budget x genre multiple**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 986 | 1.450 | 79% | 37.8% | 0.696 | 77.8% | 53.9× |
| other languages | 499 | 1.464 | 91% | 32.9% | 0.534 | 77.2% | 53.9× |

**language: LightGBM (tuned, calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 986 | 1.246 | 78% | 40.7% | 0.781 | 76.8% | 34.1× |
| other languages | 499 | 1.197 | 75% | 42.1% | 0.690 | 78.6% | 33.6× |

**language: LightGBM, budget estimated (calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 986 | 1.269 | 78% | 38.0% | 0.768 | 77.5% | 42.1× |
| other languages | 499 | 1.259 | 76% | 39.9% | 0.670 | 79.8% | 41.5× |

**director: B2 budget x genre multiple**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 315 | 1.705 | 96% | 27.6% | 0.532 | 70.2% | 53.9× |
| experienced director | 1,170 | 1.388 | 79% | 38.5% | 0.670 | 79.6% | 53.9× |

**director: LightGBM (tuned, calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 315 | 1.401 | 85% | 35.2% | 0.700 | 80.6% | 61.1× |
| experienced director | 1,170 | 1.184 | 74% | 42.7% | 0.758 | 76.5% | 28.8× |

**director: LightGBM, budget estimated (calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 315 | 1.416 | 80% | 35.6% | 0.690 | 80.0% | 75.5× |
| experienced director | 1,170 | 1.225 | 77% | 39.5% | 0.740 | 77.8% | 35.6× |

**franchise: B2 budget x genre multiple**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 240 | 1.023 | 59% | 45.0% | 0.825 | 87.5% | 53.9× |
| original | 1,245 | 1.538 | 91% | 34.5% | 0.597 | 75.7% | 53.9× |

**franchise: LightGBM (tuned, calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 240 | 0.828 | 49% | 61.3% | 0.879 | 75.8% | 9.9× |
| original | 1,245 | 1.307 | 80% | 37.3% | 0.704 | 77.7% | 41.1× |

**franchise: LightGBM, budget estimated (calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 240 | 0.901 | 58% | 53.8% | 0.861 | 76.7% | 12.3× |
| original | 1,245 | 1.336 | 80% | 35.7% | 0.685 | 78.6% | 50.7× |

## Budget (log 2025 $)

| Model | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 1,964 | 1.303 | 82% | 34.9% | — | 83.2% | 92.0× |
| B1 genre median | 1,964 | 1.266 | 81% | 34.4% | 0.321 | 82.7% | 68.3× |
| B2 genre median x sequel factor | 1,964 | 1.247 | 80% | 34.3% | 0.360 | 83.7% | 66.7× |
| LightGBM (tuned, calibrated) | 1,964 | 0.682 | 45% | 66.7% | 0.827 | 79.9% | 7.6× |

**Rough-estimate label** (frozen cut-offs)

| Model | Labelled | MAE log labelled / rest | Within 2× labelled / rest |
| --- | --- | --- | --- |
| LightGBM (tuned, calibrated) | 24% | 1.020 / 0.576 (1.77×) | 49% / 72% |

**budget size: B2 genre median x sequel factor**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 840 | 1.706 | 296% | 17.0% | 0.178 | 84.6% | 66.7× |
| $10-50M | 748 | 0.582 | 43% | 67.6% | 0.116 | 96.7% | 66.7× |
| $50-150M | 259 | 1.338 | 72% | 9.7% | 0.200 | 72.2% | 66.7× |
| $150M+ | 117 | 1.990 | 87% | 0.0% | 0.227 | 18.8% | 66.7× |

**budget size: LightGBM (tuned, calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 840 | 0.855 | 59% | 60.4% | 0.528 | 79.2% | 10.3× |
| $10-50M | 748 | 0.544 | 41% | 71.3% | 0.487 | 82.6% | 7.0× |
| $50-150M | 259 | 0.580 | 40% | 70.3% | 0.480 | 76.8% | 4.7× |
| $150M+ | 117 | 0.540 | 29% | 75.2% | 0.392 | 74.4% | 3.9× |

**language: B2 genre median x sequel factor**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 1,220 | 1.273 | 73% | 34.3% | 0.436 | 78.4% | 66.7× |
| other languages | 744 | 1.203 | 149% | 34.4% | 0.330 | 92.2% | 66.7× |

**language: LightGBM (tuned, calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 1,220 | 0.694 | 45% | 65.6% | 0.853 | 78.2% | 6.9× |
| other languages | 744 | 0.661 | 45% | 68.5% | 0.683 | 82.7% | 8.6× |

**director: B2 genre median x sequel factor**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 490 | 1.668 | 228% | 25.1% | 0.292 | 81.0% | 66.7× |
| experienced director | 1,474 | 1.107 | 74% | 37.4% | 0.366 | 84.5% | 66.7× |

**director: LightGBM (tuned, calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 490 | 0.917 | 57% | 55.1% | 0.695 | 77.1% | 12.1× |
| experienced director | 1,474 | 0.603 | 42% | 70.6% | 0.833 | 80.8% | 6.6× |

**franchise: B2 genre median x sequel factor**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 278 | 1.227 | 77% | 25.2% | 0.344 | 77.7% | 66.7× |
| original | 1,686 | 1.250 | 81% | 35.8% | 0.297 | 84.6% | 66.7× |

**franchise: LightGBM (tuned, calibrated)**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 278 | 0.463 | 33% | 80.6% | 0.917 | 84.5% | 5.2× |
| original | 1,686 | 0.717 | 47% | 64.4% | 0.798 | 79.1% | 8.0× |

## Score (vote_average)

| Model | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 7,461 | 0.651 | 0.651 | — | 83.8% | 2.30 pts |
| B1 genre median | 7,461 | 0.588 | 0.595 | 0.430 | 81.9% | 2.03 pts |
| B2 genre median + director | 7,461 | 0.574 | 0.578 | 0.503 | 80.8% | 1.94 pts |
| LightGBM (tuned, calibrated) | 7,461 | 0.493 | 0.491 | 0.641 | 81.1% | 1.67 pts |

**language: B2 genre median + director**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| English | 4,194 | 0.555 | 0.562 | 0.527 | 82.3% | 1.94 pts |
| other languages | 3,267 | 0.598 | 0.603 | 0.457 | 78.9% | 1.94 pts |

**language: LightGBM (tuned, calibrated)**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| English | 4,194 | 0.491 | 0.488 | 0.638 | 80.2% | 1.64 pts |
| other languages | 3,267 | 0.496 | 0.494 | 0.634 | 82.2% | 1.71 pts |

**director: B2 genre median + director**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| new director | 2,713 | 0.591 | 0.594 | 0.499 | 80.0% | 1.94 pts |
| experienced director | 4,748 | 0.565 | 0.570 | 0.509 | 81.2% | 1.94 pts |

**director: LightGBM (tuned, calibrated)**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| new director | 2,713 | 0.520 | 0.521 | 0.637 | 81.9% | 1.77 pts |
| experienced director | 4,748 | 0.478 | 0.475 | 0.644 | 80.6% | 1.61 pts |

**franchise: B2 genre median + director**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| sequel | 692 | 0.584 | 0.600 | 0.515 | 80.1% | 1.94 pts |
| original | 6,769 | 0.573 | 0.576 | 0.503 | 80.9% | 1.94 pts |

**franchise: LightGBM (tuned, calibrated)**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| sequel | 692 | 0.482 | 0.481 | 0.623 | 77.2% | 1.55 pts |
| original | 6,769 | 0.494 | 0.492 | 0.642 | 81.5% | 1.68 pts |
