# Breakdowns (validation)

_Generated 2026-10-21 13:35 UTC by `make evaluate`. Fitted on train (≤2015), scored on validation (2016–18); the test split (2019+) is not used._

## Revenue (log 2025 $)

**budget size: B0 global median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 296 | 2.287 | 500% | 22.0% | — | 81.1% | 300.3× |
| $10-50M | 389 | 1.481 | 80% | 33.7% | — | 89.2% | 300.3× |
| $50-150M | 134 | 1.693 | 84% | 18.7% | — | 72.4% | 300.3× |
| $150M+ | 67 | 2.907 | 95% | 0.0% | — | 14.9% | 300.3× |

**budget size: B1 genre median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 296 | 2.208 | 451% | 23.0% | 0.063 | 79.7% | 240.1× |
| $10-50M | 389 | 1.498 | 79% | 32.9% | 0.101 | 86.4% | 240.1× |
| $50-150M | 134 | 1.482 | 76% | 26.1% | 0.187 | 74.6% | 240.1× |
| $150M+ | 67 | 2.335 | 91% | 1.5% | 0.195 | 35.8% | 240.1× |

**budget size: B2 budget x genre multiple**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 296 | 1.574 | 77% | 34.8% | 0.272 | 72.0% | 53.4× |
| $10-50M | 389 | 1.381 | 79% | 37.0% | 0.394 | 78.7% | 53.4× |
| $50-150M | 134 | 0.890 | 59% | 50.7% | 0.481 | 89.6% | 53.4× |
| $150M+ | 67 | 0.652 | 49% | 56.7% | 0.595 | 100.0% | 53.4× |

**language: B0 global median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 639 | 1.977 | 91% | 22.8% | — | 73.7% | 300.3× |
| other languages | 247 | 1.664 | 182% | 30.4% | — | 90.3% | 300.3× |

**language: B1 genre median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 639 | 1.860 | 88% | 24.9% | 0.351 | 74.8% | 240.1× |
| other languages | 247 | 1.631 | 157% | 29.6% | 0.240 | 88.3% | 240.1× |

**language: B2 budget x genre multiple**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 639 | 1.308 | 71% | 41.3% | 0.764 | 79.8% | 53.4× |
| other languages | 247 | 1.336 | 74% | 36.0% | 0.426 | 79.4% | 53.4× |

**director: B0 global median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 159 | 2.356 | 248% | 19.5% | — | 74.2% | 300.3× |
| experienced director | 727 | 1.788 | 91% | 26.1% | — | 79.2% | 300.3× |

**director: B1 genre median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 159 | 2.289 | 251% | 23.9% | 0.168 | 74.8% | 240.1× |
| experienced director | 727 | 1.688 | 88% | 26.7% | 0.344 | 79.4% | 240.1× |

**director: B2 budget x genre multiple**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 159 | 1.621 | 75% | 35.2% | 0.580 | 71.7% | 53.4× |
| experienced director | 727 | 1.249 | 71% | 40.9% | 0.718 | 81.4% | 53.4× |

**franchise: B0 global median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 137 | 2.030 | 90% | 16.1% | — | 59.9% | 300.3× |
| original | 749 | 1.864 | 95% | 26.6% | — | 81.7% | 300.3× |

**franchise: B1 genre median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 137 | 1.803 | 87% | 19.7% | 0.348 | 64.2% | 240.1× |
| original | 749 | 1.795 | 93% | 27.4% | 0.251 | 81.2% | 240.1× |

**franchise: B2 budget x genre multiple**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 137 | 1.000 | 58% | 48.2% | 0.865 | 82.5% | 53.4× |
| original | 749 | 1.374 | 74% | 38.3% | 0.644 | 79.2% | 53.4× |

## Budget (log 2025 $)

**budget size: B0 global median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 477 | 1.780 | 291% | 12.6% | — | 84.3% | 97.7× |
| $10-50M | 473 | 0.451 | 36% | 75.1% | — | 100.0% | 97.7× |
| $50-150M | 144 | 1.631 | 80% | 0.0% | — | 63.2% | 97.7× |
| $150M+ | 68 | 2.656 | 93% | 0.0% | — | 0.0% | 97.7× |

**budget size: B1 genre median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 477 | 1.704 | 300% | 17.4% | 0.175 | 85.3% | 73.7× |
| $10-50M | 473 | 0.534 | 42% | 70.4% | 0.109 | 97.7% | 73.7× |
| $50-150M | 144 | 1.358 | 74% | 7.6% | 0.228 | 75.0% | 73.7× |
| $150M+ | 68 | 2.079 | 88% | 0.0% | 0.179 | 17.6% | 73.7× |

**budget size: B2 genre median x sequel factor**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <$10M | 477 | 1.726 | 306% | 17.0% | 0.182 | 85.3% | 72.0× |
| $10-50M | 473 | 0.530 | 41% | 70.4% | 0.130 | 97.5% | 72.0× |
| $50-150M | 144 | 1.268 | 71% | 13.2% | 0.265 | 79.2% | 72.0× |
| $150M+ | 68 | 1.910 | 86% | 0.0% | 0.293 | 25.0% | 72.0× |

**language: B0 global median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 802 | 1.302 | 75% | 33.4% | — | 80.2% | 97.7× |
| other languages | 360 | 1.203 | 107% | 40.8% | — | 89.7% | 97.7× |

**language: B1 genre median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 802 | 1.190 | 72% | 36.7% | 0.421 | 83.3% | 73.7× |
| other languages | 360 | 1.244 | 142% | 36.9% | 0.289 | 89.2% | 73.7× |

**language: B2 genre median x sequel factor**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | 802 | 1.165 | 71% | 37.7% | 0.451 | 84.5% | 72.0× |
| other languages | 360 | 1.256 | 145% | 36.4% | 0.333 | 89.2% | 72.0× |

**director: B0 global median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 270 | 1.756 | 216% | 25.2% | — | 78.1% | 97.7× |
| experienced director | 892 | 1.125 | 71% | 38.9% | — | 84.6% | 97.7× |

**director: B1 genre median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 270 | 1.683 | 227% | 25.6% | 0.353 | 80.7% | 73.7× |
| experienced director | 892 | 1.063 | 71% | 40.1% | 0.367 | 86.4% | 73.7× |

**director: B2 genre median x sequel factor**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new director | 270 | 1.683 | 230% | 25.2% | 0.371 | 81.1% | 72.0× |
| experienced director | 892 | 1.045 | 70% | 40.9% | 0.391 | 87.4% | 72.0× |

**franchise: B0 global median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 151 | 1.507 | 83% | 27.2% | — | 64.2% | 97.7× |
| original | 1,011 | 1.237 | 77% | 37.0% | — | 86.0% | 97.7× |

**franchise: B1 genre median**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 151 | 1.333 | 79% | 25.2% | 0.446 | 70.9% | 73.7× |
| original | 1,011 | 1.188 | 78% | 38.5% | 0.318 | 87.2% | 73.7× |

**franchise: B2 genre median x sequel factor**

| Group | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sequel | 151 | 1.226 | 76% | 29.1% | 0.446 | 79.5% | 72.0× |
| original | 1,011 | 1.188 | 78% | 38.5% | 0.318 | 86.9% | 72.0× |

## Score (vote_average)

**language: B0 global median**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| English | 2,154 | 0.701 | 0.685 | — | 82.4% | 2.30 pts |
| other languages | 1,446 | 0.678 | 0.684 | — | 82.9% | 2.30 pts |

**language: B1 genre median**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| English | 2,154 | 0.623 | 0.617 | 0.428 | 81.6% | 2.04 pts |
| other languages | 1,446 | 0.634 | 0.639 | 0.321 | 80.9% | 2.04 pts |

**language: B2 genre median + director**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| English | 2,154 | 0.602 | 0.596 | 0.514 | 81.4% | 1.96 pts |
| other languages | 1,446 | 0.602 | 0.604 | 0.413 | 80.4% | 1.96 pts |

**director: B0 global median**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| new director | 1,222 | 0.739 | 0.735 | — | 79.8% | 2.30 pts |
| experienced director | 2,378 | 0.667 | 0.662 | — | 84.1% | 2.30 pts |

**director: B1 genre median**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| new director | 1,222 | 0.656 | 0.651 | 0.444 | 80.2% | 2.04 pts |
| experienced director | 2,378 | 0.613 | 0.613 | 0.364 | 81.9% | 2.04 pts |

**director: B2 genre median + director**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| new director | 1,222 | 0.656 | 0.651 | 0.444 | 77.6% | 1.96 pts |
| experienced director | 2,378 | 0.574 | 0.575 | 0.511 | 82.8% | 1.96 pts |

**franchise: B0 global median**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| sequel | 347 | 0.672 | 0.657 | — | 80.4% | 2.30 pts |
| original | 3,253 | 0.694 | 0.688 | — | 82.8% | 2.30 pts |

**franchise: B1 genre median**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| sequel | 347 | 0.627 | 0.623 | 0.395 | 79.5% | 2.04 pts |
| original | 3,253 | 0.628 | 0.625 | 0.394 | 81.5% | 2.04 pts |

**franchise: B2 genre median + director**

| Group | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| sequel | 347 | 0.544 | 0.540 | 0.600 | 85.0% | 1.96 pts |
| original | 3,253 | 0.608 | 0.606 | 0.474 | 80.6% | 1.96 pts |
