# Audit metrics

_Generated 2026-10-22 09:29 UTC by `uv run python -m ml.eval.audit`. Validation: models fitted on ≤2015 exactly as `make evaluate` does, scored on 2016–18. Holdout: the app's all-data models on films released in 2026. The test split (2019+) is not used._

## Reproduction of reports/metrics.md

| Target | Model | Largest difference |
| --- | --- | --- |
| revenue | B0 global median | 0.0e+00 |
| revenue | B1 genre median | 0.0e+00 |
| revenue | B2 budget x genre multiple | 0.0e+00 |
| revenue | LightGBM (tuned, calibrated) | 0.0e+00 |
| revenue | LightGBM, budget estimated (calibrated) | 0.0e+00 |
| budget | B0 global median | 0.0e+00 |
| budget | B1 genre median | 0.0e+00 |
| budget | B2 genre median x sequel factor | 0.0e+00 |
| budget | LightGBM (tuned, calibrated) | 0.0e+00 |
| score | B0 global median | 0.0e+00 |
| score | B1 genre median | 0.0e+00 |
| score | B2 genre median + director | 0.0e+00 |
| score | LightGBM (tuned, calibrated) | 0.0e+00 |

## Proper scores on 2016–18 (lower is better, except R²)

Pinball loss scores each quantile on its own; the interval score is the range width plus 10× every miss (α = 0.2). Units: log 2025 $ for money, points for score.

### revenue

| Model | Pinball p10 | p50 | p90 | Mean | Interval score | R² | Below p10 | Above p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 0.507 | 0.945 | 0.359 | 0.604 | 8.66 | -0.045 | 9.5% | 12.2% |
| B1 genre median | 0.502 | 0.898 | 0.329 | 0.576 | 8.30 | 0.023 | 10.7% | 10.7% |
| B2 budget x genre multiple | 0.414 | 0.658 | 0.255 | 0.442 | 6.69 | 0.410 | 10.5% | 9.8% |
| LightGBM (tuned, calibrated) | 0.301 | 0.547 | 0.223 | 0.357 | 5.24 | 0.584 | 8.6% | 7.8% |
| LightGBM, budget estimated (calibrated) | 0.305 | 0.568 | 0.232 | 0.368 | 5.36 | 0.571 | 8.2% | 5.6% |

LightGBM 95% intervals (1,000 resamples of films): MAE 1.023 to 1.169, coverage 81.1% to 85.8%, MAE minus B2's -0.268 to -0.180.

| Fold | Films | LightGBM interval score | B2 interval score | LightGBM MAE (reported) |
| --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 943 | 5.54 | 6.62 | 1.129 (1.129) |
| fold 2 (2013-2015) | 905 | 5.39 | 6.61 | 1.149 (1.149) |
| fold 3 (2016-18) | 886 | 5.24 | 6.69 | 1.093 (1.093) |

**LightGBM coverage by year**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| 2016 | 320 | 85.0% | 9.1% | 5.9% |
| 2017 | 287 | 80.8% | 9.1% | 10.1% |
| 2018 | 279 | 84.9% | 7.5% | 7.5% |

**LightGBM coverage by main genre**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| Action | 160 | 81.9% | 10.6% | 7.5% |
| Adventure | 55 | 81.8% | 9.1% | 9.1% |
| Animation | 42 | 81.0% | 7.1% | 11.9% |
| Comedy | 126 | 92.9% | 3.2% | 4.0% |
| Crime | 38 | 78.9% | 15.8% | 5.3% |
| Drama | 228 | 82.5% | 10.5% | 7.0% |
| Horror | 62 | 83.9% | 1.6% | 14.5% |
| Thriller | 39 | 82.1% | 12.8% | 5.1% |
| other | 136 | 82.4% | 8.1% | 9.6% |

**LightGBM coverage by language**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| English | 639 | 83.7% | 9.5% | 6.7% |
| other languages | 247 | 83.4% | 6.1% | 10.5% |

**LightGBM coverage by budget size**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| $10-50M | 389 | 81.7% | 9.8% | 8.5% |
| $150M+ | 67 | 91.0% | 7.5% | 1.5% |
| $50-150M | 134 | 86.6% | 7.5% | 6.0% |
| <$10M | 296 | 83.1% | 7.8% | 9.1% |

### budget

| Model | Pinball p10 | p50 | p90 | Mean | Interval score | R² | Below p10 | Above p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 0.349 | 0.636 | 0.264 | 0.417 | 6.14 | -0.022 | 6.5% | 10.4% |
| B1 genre median | 0.322 | 0.603 | 0.237 | 0.387 | 5.58 | 0.103 | 6.0% | 8.9% |
| B2 genre median x sequel factor | 0.319 | 0.597 | 0.231 | 0.382 | 5.49 | 0.116 | 6.0% | 8.0% |
| LightGBM (tuned, calibrated) | 0.186 | 0.307 | 0.139 | 0.210 | 3.25 | 0.703 | 10.9% | 4.7% |

LightGBM 95% intervals (1,000 resamples of films): MAE 0.573 to 0.652, coverage 82.2% to 86.5%, MAE minus B2's -0.636 to -0.530.

| Fold | Films | LightGBM interval score | B2 interval score | LightGBM MAE (reported) |
| --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 1,354 | 3.51 | 5.97 | 0.701 (0.701) |
| fold 2 (2013-2015) | 1,245 | 3.41 | 5.84 | 0.671 (0.671) |
| fold 3 (2016-18) | 1,162 | 3.25 | 5.49 | 0.613 (0.613) |

**LightGBM coverage by year**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| 2016 | 421 | 85.5% | 10.0% | 4.5% |
| 2017 | 377 | 83.8% | 10.3% | 5.8% |
| 2018 | 364 | 83.5% | 12.6% | 3.8% |

**LightGBM coverage by main genre**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| Action | 206 | 87.4% | 7.3% | 5.3% |
| Adventure | 62 | 88.7% | 4.8% | 6.5% |
| Animation | 48 | 93.8% | 4.2% | 2.1% |
| Comedy | 173 | 83.8% | 11.6% | 4.6% |
| Crime | 44 | 79.5% | 15.9% | 4.5% |
| Drama | 287 | 85.4% | 11.1% | 3.5% |
| Horror | 89 | 75.3% | 21.3% | 3.4% |
| Thriller | 60 | 78.3% | 20.0% | 1.7% |
| other | 193 | 83.4% | 8.8% | 7.8% |

**LightGBM coverage by language**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| English | 802 | 84.3% | 11.7% | 4.0% |
| other languages | 360 | 84.4% | 9.2% | 6.4% |

**LightGBM coverage by budget size**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| $10-50M | 473 | 89.4% | 4.7% | 5.9% |
| $150M+ | 68 | 89.7% | 0.0% | 10.3% |
| $50-150M | 144 | 88.2% | 0.0% | 11.8% |
| <$10M | 477 | 77.4% | 22.0% | 0.6% |

### score

| Model | Pinball p10 | p50 | p90 | Mean | Interval score | R² | Below p10 | Above p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 0.160 | 0.346 | 0.140 | 0.215 | 3.00 | -0.005 | 7.8% | 9.6% |
| B1 genre median | 0.145 | 0.314 | 0.135 | 0.198 | 2.80 | 0.149 | 8.7% | 9.9% |
| B2 genre median + director | 0.138 | 0.301 | 0.129 | 0.189 | 2.67 | 0.221 | 9.1% | 9.9% |
| LightGBM (tuned, calibrated) | 0.121 | 0.248 | 0.108 | 0.159 | 2.28 | 0.455 | 6.9% | 12.1% |

LightGBM 95% intervals (1,000 resamples of films): MAE 0.484 to 0.509, coverage 79.7% to 82.2%, MAE minus B2's -0.117 to -0.094.

| Fold | Films | LightGBM interval score | B2 interval score | LightGBM MAE (reported) |
| --- | --- | --- | --- | --- |
| fold 1 (2010-2012) | 2,881 | 2.38 | 2.89 | 0.513 (0.513) |
| fold 2 (2013-2015) | 3,533 | 2.35 | 2.79 | 0.509 (0.509) |
| fold 3 (2016-18) | 3,600 | 2.28 | 2.67 | 0.496 (0.496) |

**LightGBM coverage by year**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| 2016 | 1,200 | 81.9% | 8.2% | 9.9% |
| 2017 | 1,200 | 81.3% | 6.5% | 12.2% |
| 2018 | 1,200 | 79.7% | 6.0% | 14.3% |

**LightGBM coverage by main genre**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| Action | 387 | 81.9% | 8.0% | 10.1% |
| Animation | 169 | 71.6% | 7.1% | 21.3% |
| Comedy | 740 | 80.9% | 6.9% | 12.2% |
| Documentary | 167 | 77.8% | 5.4% | 16.8% |
| Drama | 850 | 83.5% | 5.8% | 10.7% |
| Horror | 287 | 84.7% | 7.7% | 7.7% |
| Romance | 172 | 74.4% | 5.8% | 19.8% |
| Thriller | 204 | 83.3% | 7.8% | 8.8% |
| other | 624 | 79.6% | 7.7% | 12.7% |

**LightGBM coverage by language**

| Group | Films | Coverage | Below p10 | Above p90 |
| --- | --- | --- | --- | --- |
| English | 2,154 | 81.6% | 7.0% | 11.4% |
| other languages | 1,446 | 80.1% | 6.7% | 13.2% |

## Fresh holdout: films released in 2026

1,199 films of 2026 pulled from TMDB; 609 were 182+ days old (released by 2026-04-23). Revenue and score use those only, budget every film with one. The app's models were trained on 1960–2025, so none of these films was seen; the baselines are fitted on ≤2018. Each film is judged at the 1st of its release month, as in the app.

### revenue (70 films released 2026-01-01 to 2026-04-23)

| Model | Films | MAE | Within 2× | Spearman | Coverage 10–90 | Width | Interval score | R² | Bias | MAE 95% interval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 70 | 1.657 | 30.0% | — | 85.7% | 303.1× | 7.46 | -0.123 | -0.72 | 1.349 to 2.003 |
| B1 genre median | 70 | 1.667 | 27.1% | 0.185 | 87.1% | 240.2× | 7.18 | -0.150 | -0.79 | 1.369 to 1.998 |
| B2 budget x genre multiple | 70 | 1.295 | 35.7% | 0.630 | 80.0% | 53.9× | 6.13 | 0.260 | -0.38 | 1.044 to 1.602 |
| LightGBM app (budget given) | 70 | 1.052 | 42.9% | 0.736 | 81.4% | 43.6× | 4.78 | 0.559 | -0.01 | 0.857 to 1.253 |
| LightGBM app (budget estimated) | 70 | 1.095 | 37.1% | 0.716 | 88.6% | 53.8× | 4.82 | 0.545 | +0.03 | 0.896 to 1.293 |

### budget (223 films released 2026-01-01 to 2026-10-19)

| Model | Films | MAE | Within 2× | Spearman | Coverage 10–90 | Width | Interval score | R² | Bias | MAE 95% interval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 223 | 1.441 | 36.8% | — | 80.3% | 92.0× | 6.74 | -0.026 | -0.32 | 1.273 to 1.635 |
| B1 genre median | 223 | 1.390 | 34.5% | 0.320 | 76.7% | 68.3× | 6.83 | 0.006 | -0.26 | 1.221 to 1.584 |
| B2 genre median x sequel factor | 223 | 1.366 | 35.0% | 0.359 | 75.8% | 66.7× | 6.76 | 0.014 | -0.32 | 1.197 to 1.568 |
| LightGBM app | 223 | 0.781 | 61.9% | 0.843 | 81.2% | 8.9× | 3.85 | 0.615 | -0.15 | 0.671 to 0.916 |

### score (190 films released 2026-01-01 to 2026-04-23)

| Model | Films | MAE | Within 2× | Spearman | Coverage 10–90 | Width | Interval score | R² | Bias | MAE 95% interval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 190 | 0.772 | — | — | 76.3% | 2.30 pts | 3.77 | -0.119 | +0.32 | 0.679 to 0.858 |
| B1 genre median | 190 | 0.750 | — | 0.389 | 70.0% | 2.03 pts | 3.78 | -0.102 | +0.43 | 0.661 to 0.837 |
| B2 genre median + director | 190 | 0.731 | — | 0.467 | 70.0% | 1.94 pts | 3.55 | -0.006 | +0.41 | 0.652 to 0.815 |
| LightGBM app | 190 | 0.590 | — | 0.592 | 73.7% | 1.66 pts | 2.85 | 0.323 | +0.17 | 0.523 to 0.662 |
| LightGBM app, 200+ votes | 64 | 0.662 | — | 0.572 | 60.9% | 1.56 pts | 3.15 | 0.168 | +0.42 | 0.556 to 0.774 |
| LightGBM app, films under 182 days old | 200 | 0.695 | — | 0.524 | 60.0% | 1.64 pts | 3.38 | 0.096 | +0.41 | 0.627 to 0.765 |
