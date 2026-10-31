# Models and explanations

The three LightGBM models, their validation results, the ablation, and how a prediction is explained. Back to the [README](../README.md).

## Results

### Models

Revenue, budget and score each have a LightGBM model (`ml/models/`) with the same `fit` / `predict` interface as the baselines.

- **Revenue:**
  - The middle prediction is a Huber model on log 2025 dollars, using the film's real budget during training.
  - It is non-decreasing in budget, the director's earlier revenue and the franchise's earlier revenue, so raising the budget never lowers any prediction. LightGBM doesn't allow these constraints on quantile models.
  - The 10th/90th come from quantile models of the middle model's out-of-fold errors. They leave out those three columns, so each film gets its own range width and the whole range moves with the middle.
- **Budget (Day 6):** three quantile models (10th, 50th, 90th) on log 2025 dollars from `v_train_budget`, with every form field except the budget as input and no constraints.
- **Score:** three quantile models (10th, 50th, 90th) on `vote_average`, weighted by log(1 + votes), with no budget input. Outputs are sorted if they cross and clipped to 0–10.
- **Features:** every allowed feature except the 16 synopsis numbers, which the ablation below found don't help. Revenue and budget also use the 6 budget track-record features (Day 6); for revenue they lowered validation MAE log by 0.020 and the backtest mean by 0.006. Score doesn't use them. That leaves 158 features for revenue, 157 for budget (no `log_budget`) and 151 for score.
- **Tuning:** Optuna, 15 minutes per target, on backtest folds 1–2 only (≤2015).
  - Early stopping on each fold's test years sets the tree count: 1,032 for revenue, 1,404 for budget and 925 for score.
  - The final model trains on all of train with that count.
  - Every trial is logged in `reports/experiments.csv`.
  - Tuning improved fold MAE by only 1.4% for revenue, 2.1% for budget (96 trials) and 0.8% for score.
- **Calibration:** conformalized quantile regression, written as our own short function.
  - Out-of-fold predictions on folds 1–2 (2010–15) give the amount each range is widened on both sides: 0.448 log (about 1.6×) for revenue, 0.399 log (about 1.5×) for budget and 0.165 points for score.
  - 2016–18 is never used to fit, stop or calibrate anything, so its coverage is an honest check.
- **The chain (Day 6):** one revenue model, two range corrections (`ml/models/chain.py`).
  - **Budget given:** the creator's budget goes into the revenue model, with the 0.448 correction above.
  - **Budget estimated:** the budget model's middle prediction goes in instead. Its correction, 0.585 log (about 1.8×), is learned the same way on folds 1–2, with each fold's revenue predictions fed budgets from a budget model trained on that fold's train years.
  - The revenue range models never see the budget, so the estimated range is wider only by its larger correction, and it is never allowed to be narrower than the given one.
  - `predict_revenue(features, budget=None)` picks the mode: a budget means "given", none means "estimated".

### Results (validation, 2016–18)

| Revenue | MAE log | Median % error | Within 2× | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| B2 budget × genre multiple | 1.316 | 71% | 39.8% | 0.709 | 79.7% | 53× |
| **LightGBM, budget given** | **1.093** | **66%** | **46.8%** | **0.807** | 83.6% | **36×** |
| LightGBM, budget estimated | 1.135 | 70% | 44.0% | 0.793 | 86.1% | 48× |

| Budget | MAE log | Median % error | Within 2× | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- | --- |
| B2 genre median × sequel factor | 1.193 | 78% | 37.3% | 0.389 | 86.0% | 72× |
| **LightGBM** | **0.613** | **39%** | **70.9%** | **0.859** | 84.3% | **8.1×** |

| Score | MAE | Weighted MAE | Spearman | Coverage | Range width |
| --- | --- | --- | --- | --- | --- |
| B2 genre median + director | 0.602 | 0.599 | 0.485 | 81.0% | 1.96 pts |
| **LightGBM** | **0.496** | **0.501** | **0.687** | 81.0% | **1.68 pts** |

Rolling backtest, mean ± spread across the three folds:

| | B2 | LightGBM | LightGBM per fold (2010–12 / 2013–15 / 2016–18) |
| --- | --- | --- | --- |
| Revenue MAE log | 1.309 ± 0.012 | **1.124 ± 0.023** | 1.129 / 1.149 / 1.093 |
| Revenue MAE log, budget estimated | 1.309 ± 0.012 | 1.192 ± 0.044 | 1.199 / 1.242 / 1.135 |
| Budget MAE log | 1.265 ± 0.052 | **0.662 ± 0.036** | 0.701 / 0.671 / 0.613 |
| Score MAE | 0.621 ± 0.014 | **0.506 ± 0.007** | 0.513 / 0.509 / 0.496 |

**What the results show**
- **All three models beat B2 on validation and in every backtest fold.** Error is 17% lower for revenue, 49% lower for budget and 18% lower for score, with narrower ranges at about 80% coverage.
- **They also beat B2 in every breakdown group:**

  | Group | LightGBM | B2 |
  | --- | --- | --- |
  | $150M+ films, MAE log | 0.48 | 0.65 |
  | Sequels, revenue within 2× | 62% | 48% |
  | New directors, score MAE | 0.53 | 0.66 |
  | $150M+ films, budget within 2× | 90% | 0% |

- **Ranges now fit the groups better.** Revenue coverage is 82–91% in every group (B2: 72–100%), and score coverage is 80–82%.
- **An estimated budget costs revenue some accuracy, but less than having no budget at all.** Validation MAE log is 1.135 with an estimated budget, against 1.093 with the real one and 1.219 for a model with no budget input (ablation). Even estimated, it beats B2, which uses the real budget (1.316). The estimate is within 2× of the real budget for 75% of revenue films.
- **Estimated-budget ranges are wider and slightly cautious.** They are typically 48× wide (36× with the budget given) and cover 86% of 2016–18 films, above the 80% target; every group is covered 84–94%.
- **Revenue coverage on 2016–18 is 84%, a little above the target.** Calibrated on 2010–15, the ranges are slightly cautious for 2016–18. On the test years they are slightly narrow instead (77%; see [the 2019+ test](evaluation.md#final-test-results-2019)).
- **The budget model learns what the baselines couldn't.** B2 budget barely beat the median; LightGBM puts 71% of films within 2× (B2: 37%). Earlier budgets of the companies, director and actors carry most of it: without them, validation MAE log rises from 0.613 to 0.667.
- **Budget coverage on 2016–18 is 84%,** slightly cautious like revenue, but only 77% for films under $10M. Budget ranges are typically 8× wide (5× for $150M+ films, 12× under $10M and for new directors).
- **Small films are still hard.** Under $10M, revenue MAE log is 1.34 and only 36% are within 2× (B2: 35%); budget MAE log is 0.85 (0.33 at $150M+).
- **Revenue ranges are wide.** The high end is typically 36× the low end, meaning a film's revenue is honestly very uncertain before release. Score ranges average 1.7 points.

### Rough-estimate label

A revenue or budget prediction is labelled a **rough estimate** when its high end is more than 81× (revenue) or 12× (budget) its low end. These cut-offs are the widest quarter of 2016–18 ranges, rounded, and are frozen in `ml/artifacts/rough_estimate.json` (`uv run python -m ml.models.rough`). Score gets no label: its ranges barely vary (1.3–2.0 points) and their width hardly predicts the error (Spearman 0.09). The plan's starting point of 4× would have labelled 98% of revenue and 93% of budget predictions.

| Validation, 2016–18 | Labelled | MAE log, labelled / rest | Within 2×, labelled / rest |
| --- | --- | --- | --- |
| Revenue, budget given | 25% | 1.54 / 0.95 (1.6×) | 34% / 51% |
| Revenue, budget estimated | 32% | 1.55 / 0.95 (1.6×) | 31% / 50% |
| Budget | 27% | 0.86 / 0.52 (1.7×) | 54% / 77% |

The cut-offs were chosen on these films, so the test set gives the honest check.

### Budget comparison

Every prediction includes "Similar films usually cost $X–Y": the budget model's calibrated 10th–90th range for the same form. It is shown even when the creator gives a budget, and the budget is then placed below, within or above that range (`Chain.compare_budget` in `ml/models/chain.py`; `predict()` also says "at the low / high end" within 5% of an edge). On 2016–18, 84% of real budgets fall within, 11% below and 5% above, so the model overestimates more often than it underestimates. For example, *Get Out* ($5.9M) gets "$1.4M–$20M" and *Avengers: Infinity War* ($380M) gets "$180M–$580M".

### Ablation

Each row removes one part and reuses the tuned settings. The full model here means every allowed feature, synopsis included. Lower error is better, and the change is the row minus the full model (`reports/ablation.md`).

| Run | Revenue MAE log | Change | Backtest change | Score MAE | Change | Backtest change |
| --- | --- | --- | --- | --- | --- | --- |
| Full model | 1.126 | — | — | 0.498 | — | — |
| No synopsis embeddings | 1.113 | −0.013 | −0.006 | 0.496 | −0.001 | −0.000 |
| 32 synopsis numbers | 1.124 | −0.002 | +0.008 | 0.498 | +0.001 | +0.004 |
| No track-record features | 1.136 | +0.010 | +0.017 | 0.501 | +0.003 | +0.016 |
| No themes | 1.135 | +0.008 | +0.012 | 0.503 | +0.005 | +0.007 |
| No budget | 1.219 | +0.092 | +0.108 | — | — | — |
| No monotone constraints | 1.122 | −0.004 | −0.001 | — | — | — |

- **Budget is by far the strongest revenue input.** Without it, revenue within 2× falls from 44.7% to 39.3%.
- **Track record and themes earn their place** in the revenue and score models, by about 0.01–0.02 in the backtest.
- **The synopsis embeddings don't help either model, and 32 numbers don't help either**, so the saved models leave them out. The features table still stores 16, for the app and for later tries.
- **Monotone constraints cost no accuracy**, so "what if" changes in the app behave sensibly for free.
- **Budget (Day 6):**

  | Run | Budget MAE log | Change | Backtest change |
  | --- | --- | --- | --- |
  | Full model (every allowed feature) | 0.613 | — | — |
  | No synopsis embeddings (saved) | 0.613 | +0.000 | −0.004 |
  | 32 synopsis numbers | 0.617 | +0.004 | +0.008 |
  | No budget track record | 0.667 | +0.054 | +0.061 |
  | No track-record features | 0.636 | +0.023 | +0.026 |
  | No themes | 0.608 | −0.005 | +0.001 |

  Removing the budget track record costs the most, more than the whole people track record. The synopsis doesn't help the budget model either, so it is left out. Themes are a wash (−0.005 on validation, +0.001 in the backtest) and stay in, as in the other models.
- **The budget track record (Day 6) helps revenue, mostly on 2016–18.** Added to the saved model's features, it lowers validation MAE log from 1.113 to 1.093 and the backtest mean from 1.130 to 1.124. The backtest gain comes from fold 3 (2016–18, −0.020); folds 1–2 change by +0.004 and −0.002. The revenue and score rows in the first table leave it out.

## What we tried to improve the models

After the 2019+ test (Oct 21) the models were frozen. Three later attempts tried to make them more accurate; none was kept. Details and every number are in [Decisions](decisions.md#v15-wikidata-budgets-and-box-office-not-kept) and the spike reports on branch `spike/release-plan`.

| Attempt | Revenue (MAE log, validation) | Budget | Score (MAE) | Kept? |
| --- | --- | --- | --- | --- |
| **More films of the same kind** (learning curve: 15%–100% of the ≤2015 films) | 1.135 at 85% → 1.133 at 100%: flat | small gain | 0.500 → 0.498: flat | — |
| **V1.5 Wikidata budgets and box office** (+615 revenue films, retuned) | 1.101 against v1's 1.090 on the same films | 0.586 against 0.604 | 0.497 against 0.496 | No |
| **Release plan: country count** (spike 1) | 0.943, but a popularity leak | — | — | No |
| **Release plan: planned US opening** (spikes 2–3) | 1.076 against 1.093 (−0.025 on films with a US opening); 2026 holdout +0.007 | — | — | Not yet |
| **Release plan for score** (spike 4) | — | — | ±0.003, nothing | No |
| Earlier: tuning, synopsis embeddings, 32 synopsis numbers (Days 5–6) | ≤0.03 | ≤0.015 | ≤0.002 | Tuning only |

- **Where the revenue error is:** 6% of validation films (revenue under 5% of budget) cause 23% of it, and the model is about 2× too high for the least-voted quarter of films and 1.6× too low for the most-voted. Both point at things not known before release (marketing, how the release went), not at the model type.
- **The trap we avoided:** spike 1's −0.15 looked like the best result of the project. Checking it against `vote_count` showed it was mostly popularity, which the hard rules keep out of the features. Every comparison since uses the same films for both models, a paired bootstrap, the backtest and the 2026 holdout, and asks whether a creator could honestly give the input.
- **Why every variant was trained from scratch:** continuing from saved trees would only add trees on top; the old ones would never use a new input. Training all three revenue models takes about 3 minutes.

## Explanations and `predict()`

Day 7 turns the app's models into one call: `ml.predict.predict(form)` returns budget, revenue and score ranges, the top 5 drivers of each in plain English, 5 comparable past films and warnings. `notebooks/07_explanations.ipynb` checks the cut-offs and weights below and runs six famous films through it.

### Drivers

- **What is explained:** each target's middle (p50) model. LightGBM's `pred_contrib` splits a prediction into one amount per feature plus the typical film's value, and these add up exactly to the middle that is shown (`ml/explain/drivers.py`). When the budget or score quantile models cross, the sorted middle is not the p50 model's own (about 3% of 2016–18 budget films), and those amounts are scaled to match.
- **Groups:** the 158 features are merged into 12 groups a creator recognises: budget, director, cast, franchise, studio, genre, themes, release timing, runtime, certification, language and country (`ml/explain/groups.py`). The budget track record joins the group it describes, and the synopsis numbers have no group because no model uses them.
- **Strength:** money effects are "strong" from +50% (or −33%), "moderate" from +20% (or −17%), otherwise "slight"; score effects from 0.3 and 0.1 points. The plan started at +25% / +10%, which made 99% of top revenue drivers on 2016–18 "strong"; with +50% / +20%, 30% of the top 5 drivers are strong, 53% moderate and 17% slight.
- **Sentences:** one template per group, filled with the creator's values (`ml/explain/sentences.py`), for example "Being part of The Avengers Collection (2 earlier films) strongly raises the expected revenue." or "Jordan Peele, with no earlier films as director in our data, lowers the expected revenue." Release timing names whichever part pushes most: "Releasing in 2026 (recent films earn less in our data)" or "Releasing in December (holiday season)". In "budget estimated" mode the budget driver says so: "The estimated budget of about $29M …".

| 2016–18, ≤2015 models | Most often the top driver |
| --- | --- |
| Revenue | budget 70%, studio 9% |
| Budget | studio 73% (90% of it the companies' earlier budgets), cast 14% |
| Score | cast 44%, genre 26%, runtime 19% |

### Comparable films

`ml/explain/comparables.py` returns 5 earlier films like the planned one, with their real budget, revenue (2025 $) and score, and up to 3 short reasons why each is similar, strongest first: the shared genres or themes by name ("Same genres", "Also superhero, science fiction"), "Similar story" (synopsis cosine 0.5+), "Similar budget" (within 2×), "Same era" (about 5 years) or, for films not in English, "Same language". The pool is the 33,077 films with a usable score; only films released before the planned date can be returned, and of the 50 most similar, those with a reported budget or revenue come first. Similarity is a weighted average of genres (0.3), themes (0.2), synopsis (0.3, cosine on the MiniLM vectors, skipped without a synopsis), era (0.1), budget level (0.2, the creator's budget or the budget model's estimate) and the same original language (0.1). The index (`ml/artifacts/final/comparables.npz`, 26 MB, not in git) is built by `uv run python -m ml.explain.comparables`; a query takes about 8 ms.

The language weight and the doubled budget weight were chosen on 600 films from 2016–18, each judged at its release:

| Weights | Comparables' revenue vs the film's (MAE log) | Score MAE | Same language |
| --- | --- | --- | --- |
| Planned (no language, budget 0.1) | 1.883 | 0.602 | 60% |
| Chosen (language 0.1, budget 0.2) | 1.802 | 0.584 | 84% |
| Chosen + a tie-break towards well-known films | 1.931 | 0.572 | 83% |

For example, *Avengers: Infinity War* gets *Green Lantern*, *Avengers: Age of Ultron*, *Captain America: Civil War*, *Justice League* and *X-Men: Days of Future Past*, and *Paddington 2* gets *Paddington* first.

### `predict()`

`Predictor.load()` loads the all-data models from `ml/artifacts/final/`, the feature context from `data/movies.db` (read-only) and the comparables index, about 11 s once; `predictor.predict(form)` then takes about 150 ms (median of 30 calls for each of three forms, under the 400 ms target). The steps are: validate the form (`ml/features/contract.py`; an invalid form raises `InvalidForm` with one message per field), build the features, predict the budget, revenue (with the creator's budget, or the estimated one) and score, then the drivers and comparables. The output is a JSON-ready dict:

- `budget`, `revenue`, `score`: low, middle and high (2025 $ or points), a text range such as "$5.2M–$62M", and the rough-estimate flag (revenue and budget only); revenue also has its `mode` and the budget it used;
- `budget.comparison`: "Similar films usually cost $X–Y" and, with a budget, "Your budget of $X is below / at the low end of / within / at the high end of / above what similar films usually cost" (within 5% of an edge counts as "at the end", since both can round to the same figure);
- `drivers`, `comparables`, `warnings`, `model_version` and `as_of` (the 1st of the release month, the date the film is judged at).

Warnings appear for a budget of $150M or more (revenue for these films was the weak spot on 2019+, and above $300M a bigger budget no longer raises the estimate), a director or actors we can't match, an empty production country or studio (past films with none recorded are mostly small, so an empty field lowers the ranges), and a release after 2025, where the data ends. The score always carries a note that new films' TMDB scores start higher and settle during their first year, so the range is for the settled score (audit, Finding 1).

`ml/artifacts/final/manifest.json` (`uv run python -m ml.predict manifest`) lists every model file with its checksum, the training years, the corrections, the LightGBM version and the `final-models` tag; the predictor refuses to load models that don't match it. The rough-estimate rule is copied into the same folder, so it holds everything the app reads except the database.

| Example form | Budget | Revenue | Score |
| --- | --- | --- | --- |
| Franchise blockbuster (Russo brothers, Avengers cast, Marvel, $300M, May 2027) | $180M–$600M | $500M–$3.6B | 6.4–8.2 |
| Small drama (Greta Gerwig, A24, no budget given, October 2026) | $5.2M–$62M, rough | $2M–$170M (budget estimated), rough | 6.2–7.6 |
| Unknown cast (horror, new director and actors, $2M, no studio or country) | $18K–$7M, rough | $38K–$14M, rough | 4.8–6.9 |

These three forms are the golden examples in `tests/ml/test_golden.py`: the tests check rules (ordered ranges, mode, warnings, earlier comparables, speed) and a snapshot of the output in `tests/golden/predictions.json`, which is rewritten only on purpose (`UPDATE_GOLDEN=1 uv run pytest tests/ml/test_golden.py`).
