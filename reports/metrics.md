# Metrics

_Generated 2026-10-21 13:35 UTC by `make evaluate`. Fitted on train (≤2015), scored on validation (2016–18); the test split (2019+) is not used._

## Revenue (log 2025 $)

| Model | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 886 | 1.890 | 93% | 24.9% | — | 78.3% | 300.3× |
| B1 genre median | 886 | 1.796 | 91% | 26.2% | 0.314 | 78.6% | 240.1× |
| B2 budget x genre multiple | 886 | 1.316 | 71% | 39.8% | 0.709 | 79.7% | 53.4× |

## Budget (log 2025 $)

| Model | Films | MAE log | Median % error | Within 2× | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 1,162 | 1.272 | 80% | 35.7% | — | 83.1% | 97.7× |
| B1 genre median | 1,162 | 1.207 | 78% | 36.7% | 0.359 | 85.1% | 73.7× |
| B2 genre median x sequel factor | 1,162 | 1.193 | 78% | 37.3% | 0.389 | 86.0% | 72.0× |

## Score (vote_average)

| Model | Films | MAE | Weighted MAE | Spearman | Coverage 10–90 | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| B0 global median | 3,600 | 0.692 | 0.685 | — | 82.6% | 2.30 pts |
| B1 genre median | 3,600 | 0.627 | 0.625 | 0.392 | 81.3% | 2.04 pts |
| B2 genre median + director | 3,600 | 0.602 | 0.599 | 0.485 | 81.0% | 1.96 pts |
