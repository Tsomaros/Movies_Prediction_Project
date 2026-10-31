---
license: mit
language: en
library_name: lightgbm
tags:
  - tabular-regression
  - quantile-regression
  - conformal-prediction
  - movies
datasets:
  - TMDB (own API pull, 79,199 films, 1960–2025)
metrics:
  - mae
  - coverage
---

# Model card: Movie Prediction App

Three models that give a planned film's **budget**, **worldwide box office** and **TMDB audience score** as ranges (10th, 50th and 90th percentile), calibrated so about 80% of real outcomes fall inside. The numbers below are the ones the app's "How accurate is this?" panel shows: they come from `ml/artifacts/final/model_card.json`, which is built from `reports/final_test.md` and `reports/audit.md`. Model version **2026-10-21.849304a7**. Back to the [README](README.md).

## Model details

- **Type:** LightGBM gradient-boosted trees, three per target (10th, 50th, 90th percentile).
  - **Budget and score:** quantile objectives.
  - **Revenue:** a monotone Huber middle model (revenue never falls as the budget rises), plus quantile models of its residuals.
- **Calibration:** our own conformalized quantile regression. Each range is widened by a learned amount, from out-of-fold predictions on 2010–18 backtest folds.
- **The chain:** one revenue model with two corrections. "Budget given" uses the creator's budget; "budget estimated" uses the budget model's middle and gets wider ranges.
- **Inputs:** only what a creator knows before release, from the 14-field form in `ml/features/contract.py`:
  - genres, themes, release month and year, runtime, language, certification;
  - director, 5–10 actors, studio, country, franchise, budget.
  - Track records count only earlier films (revenue and score once a film is 182 days old), shrunk toward the average.
- **Not inputs:** popularity, vote counts, the score itself, or anything known after release. The synopsis is embedded but no model uses it (no gain in the ablation).
- **Explanations:** LightGBM's `pred_contrib`, grouped into 12 creator-friendly groups, plus 5 comparable earlier films.
- **Made by:** Dimitris (Tsomaros), with Claude, as a portfolio project, October 2026.

## Intended use

- **For:** creators and students sanity-checking a film pitch.
  - What range of budget is typical for a film like this?
  - What box office and audience score have films like it had?
  - Which factors move the estimate?
- **How to read it:** a range, not a number. The middle is the most likely value; the ends mark where 8 in 10 similar films landed.
- **Not for:**
  - investment or green-light decisions;
  - judging individual people;
  - films outside what the data covers (mostly English-language films from after 1980 for revenue);
  - predicting a film's score in its first months, while TMDB scores are still settling.

## Training data

- **Source:** our own TMDB API pull: the 1,200 most-voted films per year, 1960–2025, in all languages (79,199 films). Money is in 2025 dollars (US CPI-U).
- **Cleaning:** unknown or placeholder money (below $1,000) is dropped from training, and suspect money (token box office, budgets in local currency) is flagged and left out.
- **Films with a usable target:** 10,421 for revenue, 14,460 for budget and 33,077 for score (50+ votes, weighted by log(1 + votes)).
- **Splits:** train ≤2015, validation 2016–18, test 2019+.
  - The served models are retrained on 1960–2025 with the frozen settings.
  - The test numbers below come from models trained on films up to 2018.

## Evaluation

**Test, 2019+:** opened once, on 2026-10-21, and no model was changed after it. B2 is the best simple baseline: budget × genre multiple for revenue, genre median × sequel factor for budget, and genre median + director for score.

| Target | Films | Model error | B2 error | Within 2× (model / B2) | Coverage (target 80%) | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| Revenue, budget given | 1,485 | MAE log 1.230 | 1.455 | 41% / 36% | 77.4% | 34× |
| Revenue, budget estimated | 1,485 | MAE log 1.266 | 1.455 (with the real budget) | 39% / 36% | 78.2% | 42× |
| Budget | 1,964 | MAE log 0.682 | 1.247 | 67% / 34% | 79.9% | 7.6× |
| Score | 7,461 | MAE 0.493 points | 0.574 | — | 81.1% | 1.67 points |

**2026 holdout:** films released after the training data ends, scored by the app's own models. Revenue and score count only films at least 182 days old (pulled 2026-10-22).

| Target | Films | Model error | B2 error | Coverage |
| --- | --- | --- | --- | --- |
| Revenue, budget given | 70 | MAE log 1.052 | 1.295 | 81.4% |
| Budget | 223 | MAE log 0.781 | 1.366 | 81.2% |
| Score | 190 | MAE 0.590 points | 0.731 | 73.7% |

- **MAE log 1.23** means the middle is typically off by a factor of about 3.4. Revenue before release is hard to predict, which is why the ranges are wide.
- **Revenue is harder on 2019+ than on 2016–18** for every model (MAE log 1.093 → 1.230). Leaving out 2020–21, the COVID years, gives 1.189.
- **More:** groups, the backtest and bootstrap intervals are in [Evaluation and testing](docs/evaluation.md).

## Known failure cases

- **Big-budget revenue:** for $150M+ films on 2019+, MAE log is 1.04 against B2's 0.99, and only 64% fall inside the range.
- **Revenue above about a $300M budget stops rising.** Trees can't extrapolate past the 130 training films with a budget over $250M; the app warns about it.
- **Breakouts land outside the range:** *Get Out* earned $340M against a range of $160K–$59M.
- **Young films' scores:** TMDB scores start high and settle. 2026 films under six months old score +0.41 above the middle, so the ranges cover 60% of them.
- **Empty optional fields count against a film.** No studio or country looks like the obscure films in the data that have none; the app warns about it.
- **Uneven coverage in some groups on 2016–18:** budgets under $10M (77%), and the scores of animated (72%) and romance (74%) films.
- **Incomplete revenues in the data:** 2% of training films earned under 1% of their budget, and some of those seem to record only part of the box office.

## Bias and limitations

- **Coverage of the world's cinema is uneven.** Only 21% of English films have both budget and revenue, and most other languages are under 10%. Revenue is mostly an English-language, post-1980 model.
- **Track records reward people with past hits.** That's what the data shows, not a judgement of anyone's work. New directors and casts get the average, shrunk, and wider ranges.
- **TMDB's ratings come from its users,** who are not a sample of all audiences. Track-record scores use today's ratings, not the ratings when a later film came out.
- **Drivers describe the model, not causes.** "A $40M budget strongly raises the expected revenue" doesn't mean spending more earns more.
- **The models are frozen.** They know 2025's world: no streaming deals, no marketing spend, no competition in a release month.

## What we tried to improve accuracy

None of these changed the models; they are the reason the numbers above are v1's. Details in [Modeling](docs/modeling.md#what-we-tried-to-improve-the-models).

- **More films:** the learning curves flattened for revenue and score.
- **Wikidata budgets and box office (V1.5):** revenue got slightly worse on the same films (MAE log 1.101 against 1.090); not kept.
- **Release plan from TMDB release dates:** the number of countries a film opened in looked like a big gain but was a popularity leak. The planned US opening (wide or limited) helps revenue by about 1.5% but isn't confirmed on the 2026 holdout yet (revisit mid-2027), and doesn't help the score.

## How to use

- **The app:** https://movie-prediction-2f1b0265282c.onrender.com/predict (it sleeps when idle; the first visit takes about 1.5 minutes).
- **The API:** `POST /api/v1/predict` with the form; the accuracy numbers are at `GET /api/v1/model-card` ([API](docs/api.md)).
- **In Python:** `ml.predict.Predictor.load().predict(form)` (needs the database and the models; see the README's [Setup](README.md#setup)).
