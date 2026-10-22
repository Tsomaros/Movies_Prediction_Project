# Audit after Day 7: logic, science and performance

_Written 2026-10-22, after Day 7 and before the Day 8 API. It reviews the whole pipeline, tests the app's logic on the real models and measures performance again. The 2019+ test split stays locked: its Day 6 numbers are quoted, not recomputed. The numbers behind this page are in `reports/audit_metrics.md` / `.json` (`uv run python -m ml.eval.audit`) and the logic rules in `tests/test_sanity.py`._

## Verdict in one paragraph

The method is sound: no leak was found, and every step uses an accepted technique for its job:
- the 182-day lag and strictly-earlier dates;
- time-ordered splits with a rolling backtest;
- quantile regression with conformal widening;
- TreeSHAP for the drivers.

The app behaves logically under 42 new rule tests. On films it has never seen (released in 2026), it beats every baseline by a wide margin, and its money ranges hit their 80% target. The real problems are in the data, not the code:
1. TMDB scores of young films start high and drift down, so score ranges under-cover recent films (74% instead of 80% on 2026).
2. Only 13% of films have both money figures, so revenue is learned from the better-documented films.
3. Release years after 2025 stretch the "years active" track record, which lowers predictions for far-future releases.

No code bug needed fixing. One test gap was closed (see Mutation checks).

## Part A: method and science, stage by stage

| Stage | What the code does | Standard it is checked against | Verdict |
| --- | --- | --- | --- |
| Money units | TMDB `0` = unknown; 1–999 nulled as "millions" shorthand; US CPI-U annual average to 2025 $ (`ml/data/clean.py:205-213`) | CPI deflating is the usual practice for multi-decade box-office data | Sound, with a caveat: one US index is applied to every country's films, and TMDB revenue is worldwide gross (not studio income), with budgets that exclude marketing |
| Suspect money | revenue/budget < 0.0001 or a non-English budget over 3× its language's 99th percentile (leave-one-out) → kept for display, out of training (`clean.py:236-290`) | robust outlier rules; leave-one-out stops a value from setting its own cap | Sound |
| Targets | log money; score = TMDB `vote_average` with 50+ votes, weighted by log(1 + votes) (`clean.py:296-301`) | Box-office revenue is extremely heavy-tailed (De Vany & Walls 1999), so errors are multiplicative and logs are the standard scale | Sound for money. **Score caveat:** the target is today's rating, which is still settling for young films (Finding 1) |
| Selection | the 1,200 most-voted films per year; budget known for 6% (1970) to 38% (2010) of them; revenue model on 10,421 of 79,199 films | sample-selection bias (films with reported money are bigger and better documented) | **Caveat** (Finding 2): ranges describe films like those that report money. Coverage on small films (<$10M) was 79% on 2019+, so in practice it holds |
| Leakage | history only from films released strictly before `as_of`; revenue and score count after 182 days, budget from release; vocab, themes and PCA fitted on ≤2015; a franchise needs an earlier entry (`ml/features/history.py:13-23`, `basic.py:8-11`); 244 theme keywords checked by hand for post-release words such as "cult classic" or "box office flop": none | target leakage (Kaufman et al. 2012) | Sound. Two known limits: an earlier film's score is today's score, and keywords are TMDB's current ones |
| Train vs app date | training judges a film at its release day, the app at the 1st of the month | train/serve skew | Sound: over 200 films from 2016–18 the middle moves by a median of 0.000 to 0.002 (log or points); the 90th percentile of the shift is below 0.04 (`test_sanity.py`) |
| Track record | median of earlier films shrunk towards the typical film as if 4 extra average films (`history.py:98-102`) | empirical-Bayes shrinkage (Efron & Morris 1975) | Sound. The 4 is a fixed choice, not fitted |
| Splits | train ≤2015, validation 2016–18, test 2019+ locked; 3-fold rolling-origin backtest | out-of-time evaluation for forecasts (Tashman 2000) | Sound |
| Models | LightGBM quantile models (pinball loss) for budget and score; revenue = Huber middle, monotone in budget / director revenue / franchise revenue, plus quantile models of out-of-fold residuals that never see those columns (`ml/models/train.py:125-160`) | quantile regression (Koenker & Bassett 1978); crossed quantiles sorted (rearrangement, Chernozhukov et al. 2010) | Sound. The monotone constraint is checked: over 12 budgets from $100K to $500M no part of the range ever drops |
| Calibration | CQR: score = max(p10 − y, y − p90), q = the ⌈(n+1)·0.8⌉-th smallest, range widened by q on both sides; learned on folds that never trained the model (`ml/models/calibrate.py:42-45`) | Romano, Patterson & Candès 2019 (NeurIPS), exactly as published | Sound. The guarantee assumes exchangeable films; time drift breaks it in principle (Barber et al. 2023). Measured coverage: 77–81% on 2019+, 81% money / 74% score on 2026 |
| Metrics | MAE log, within 2×, Spearman, coverage, width | plus proper scoring rules: pinball loss, interval score (Gneiting & Raftery 2007), added in this audit | Sound; now also proper |
| Drivers | LightGBM `pred_contrib` (TreeSHAP) on each middle model, summed in 12 groups (`ml/explain/drivers.py`) | SHAP values are additive, so group sums are exact (Lundberg et al. 2020) | Sound. They describe the model, not causes (already in the README Limitations) |
| Domain sense | budget is the top revenue driver for 70% of films; sequels, studio and track record raise revenue; stars matter mainly through budget | Ravid 1999 (budget, sequels and family ratings matter in regressions; stars don't once budget is in); Elberse 2007 (stars add a little); Einav 2007 (summer and holiday demand) | Consistent: in matched pairs a franchise lifts revenue 1.9×, Universal vs A24 2.0×, a known director 2.0×, July/December vs September +18% / +12% |

## Part B: does the app stay within the bounds of logic?

`tests/test_sanity.py` runs 42 rule tests on the real all-data models in about 55 s. All pass.

| Rule | How it is tested | Result |
| --- | --- | --- |
| Ranges are ordered, finite and positive; score within 0–10; JSON-ready | the 3 golden forms + 60 real 2016–18 films written as forms (both revenue modes) | holds |
| No range is narrower than its correction (2q) | every 2016–18 budget and score film through the app models | holds |
| A higher budget never lowers revenue | 12 budgets, $100K–$500M, × 3 forms | no drop in p10, p50 or p90; revenue rises 50–90× over the grid (elasticity about 0.5) |
| Inputs no model uses change nothing | another synopsis, no synopsis; reversed genre/theme/actor order | ranges and drivers identical |
| The two revenue modes agree | estimated mode vs given mode at the estimated budget | same middle; the estimated range is strictly wider |
| Edge-of-form inputs work | $1K and $1B budgets, runtime 40 and 300, years 1960 and 2035, 5 genres, 10 actors, an unknown language, unrated | sensible ranges and the right warnings |
| Out-of-form inputs are refused | every genre, runtime 1, $10B, a negative budget, year 2040, 4 actors, no themes | `InvalidForm` names the field |
| Matched pairs move the way studies report | budget 10× → revenue > 2×; franchise > none; known > new director; major > small > no studio; summer and December ≥ September | holds |
| Comparables never come from the future | 30 films judged at their own release | never the film itself, never a later film |
| The creator's date barely changes the features | 200 films at release day vs the 1st of the month, ≤2015 models | median shift < 0.01 |

**Mutation checks** (break the code on purpose, then confirm a test fails):
- Letting same-day films into comparables makes the sanity test fail.
- Giving estimated mode the "given" correction made only the golden snapshot fail at first. The sanity test only checked that the estimated range was at least as wide, so it was made strict: the estimated range must now be wider, and the test now fails. This was the one test gap.
- Removing the sort of crossed quantiles changes no test. The app models' crossings only ever put the middle model past one end, never p10 above p90 (2.2% / 1.3% of budget films, under 0.1% for score), and `apply_q` already clamps the ends to the middle. Both versions give ordered ranges, so this is a design choice (rearrangement), not a hole.

**Behaviours worth knowing (not bugs):**
- **Revenue stops rising above about $300M.** A $300M, $400M and $1B Avengers film get the same $1.58B middle. Trees can't extrapolate past the 130 training films with a budget over $250M. The budget elasticity is about 0.5 (1% more budget → about 0.5% more revenue) and falls to 0 at the top.
- **Far-future releases look worse.** The same small drama earns a $23M middle in 2026, $17M in 2030 and a lower range still in 2035. The only features that change are `year` and the "years active" of the director and actors, which keep growing although no new films can be counted after 2025 (Finding 3).
- **"Unrated" lowers revenue a lot** (the small drama's range moves from $2M–$170M to $820K–$57M, about −60%), like the empty-field effect already in the Limitations: in the data, unrated films are mostly obscure ones.
- **Longer runtimes raise the score** (80 min 6.8 → 180 min 7.3). This is a real pattern in TMDB (long films are often prestige dramas), not a cause.

## Part C: how well do the models perform?

### Reproduction

All 13 models (B0–B2 and LightGBM for each target, plus revenue with an estimated budget) were refitted from scratch exactly as `make evaluate` does. Every validation metric, and every backtest fold's MAE, matches `reports/metrics.md` / `backtest.md` to the last digit (largest difference 0).

### Proper scores and uncertainty (2016–18, ≤2015 models)

Pinball loss and the interval score reward a sharp range and punish misses, so a model can't look good by being vague. Lower is better. The interval score is in log units for money and points for score, and it adds 10× the size of every miss to the range width (α = 0.2).

| Target | Interval score B2 → LightGBM | R² of the middle B2 → LightGBM | LightGBM MAE, 95% CI | LightGBM − B2 MAE, 95% CI |
| --- | --- | --- | --- | --- |
| Revenue (given) | 6.69 → **5.24** | 0.41 → **0.58** | 1.02–1.17 log | −0.27 to −0.18 |
| Budget | 5.49 → **3.25** | 0.12 → **0.70** | 0.57–0.65 log | −0.64 to −0.53 |
| Score | 2.67 → **2.28** | 0.22 → **0.46** | 0.48–0.51 pts | −0.12 to −0.09 |

- LightGBM has the better interval score than B2 in every backtest fold for every target (e.g. revenue 5.54 / 5.39 / 5.24 vs 6.62 / 6.61 / 6.69). No bootstrap interval of the gap to B2 comes near zero, so the gain is not luck.
- Day 6 test (2019+, quoted from `reports/final_test.md`): revenue MAE 1.230 vs B2 1.455, coverage 77.4%; budget 0.682 vs 1.247, coverage 79.9%; score 0.493 vs 0.574, coverage 81.1%.

### Where the ranges miss (2016–18)

Overall coverage is 81–84%, but the misses are not always balanced:

| Group | Coverage | Below p10 | Above p90 | Reading |
| --- | --- | --- | --- | --- |
| Budget, films under $10M | 77.4% | **22.0%** | 0.6% | small films are often cheaper than the model thinks |
| Budget, Horror / Thriller | 75.3% / 78.3% | 21.3% / 20.0% | 3.4% / 1.7% | the same: low-budget genres |
| Score, Animation | 71.6% | 7.1% | **21.3%** | animated films score higher than predicted |
| Score, Romance | 74.4% | 5.8% | **19.8%** | the same |
| Score, all films | 81.1% | 6.9% | 12.1% | slightly more misses above, rising from 9.9% (2016) to 14.3% (2018); the young-score effect of Finding 1 points the same way |
| Revenue, $150M+ | 91.0% | 7.5% | 1.5% | wide enough on 2016–18, but only 63.9% on 2019+ (already a warning in the app) |

These are honest out-of-sample numbers, and a global q can't fix them per group. A per-group correction (Mondrian conformal) is the standard remedy, but it changes the models (Proposal 6).

### Fresh holdout: films released in 2026 (first test of the app's own models)

The all-data models were trained on 1960–2025, so until now nothing had tested them out of sample. 1,199 films of 2026 were pulled from TMDB on 2026-10-22 into `data/holdout_2026/`; `data/movies.db` is unchanged (same checksum before and after). Revenue and score use the 609 films that were 182+ days old; budget uses every film with one. Each film is judged at the 1st of its release month, exactly as in the app.

| Target | Films | Model | MAE | Within 2× | Spearman | R² | Coverage 10–90 (target 80%) | Width |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Revenue, budget given | 70 | B2 | 1.295 log | 35.7% | 0.630 | 0.26 | 80.0% | 53.9× |
| | | **App** | **1.052 log** (95% CI 0.86–1.25) | **42.9%** | **0.736** | **0.56** | **81.4%** | **43.6×** |
| Revenue, budget estimated | 70 | **App** | 1.095 log | 37.1% | 0.716 | 0.55 | 88.6% | 53.8× |
| Budget | 223 | B2 | 1.366 log | 35.0% | 0.359 | 0.01 | 75.8% | 66.7× |
| | | **App** | **0.781 log** (0.67–0.92) | **61.9%** | **0.843** | **0.62** | **81.2%** | **8.9×** |
| Score, 182+ days old | 190 | B2 | 0.731 pts | — | 0.467 | 0.00 | 70.0% | 1.94 pts |
| | | **App** | **0.590 pts** (0.52–0.66) | — | **0.592** | **0.32** | 73.7% | 1.66 pts |
| Score, under 182 days | 200 | App | 0.695 pts | — | 0.524 | 0.10 | 60.0% | 1.64 pts |

What this shows:
- **Money holds up on new films.** Revenue and budget errors on 2026 are no worse than on 2019+ (revenue MAE 1.05 vs 1.23 log; budget 0.78 vs 0.68). Both ranges hit 80%. The app beats B2 by 0.24 log on revenue and 0.59 log on budget, but with 70 revenue films the interval is wide (±0.2).
- **Score has a measurement problem (Finding 1).** 2026 films score +0.17 above the app's middle when 182+ days old, +0.41 when younger, and +0.72 for films with 500+ votes (all ages). Films with 50+ votes have a mean score of 6.24 for 2016, 6.57 for 2025 and 6.87 for 2026. A film's TMDB score starts high, when its fans vote first, and settles later. This matches the self-selection of early reviewers described by Li & Hitt (2008), whose evidence comes from Amazon book reviews. The ranges are calibrated on settled scores, so they under-cover young films.
- The R² of 0.56 for log revenue is slightly above the 0.45–0.53 that published pre-release studies report. Those studies use other films, years and validation, so this is only a rough check.

## Findings and proposals

Nothing below was changed: each item would change the frozen models, the data or the app's numbers, so each is Dimitris's decision.

1. **Young films' scores are not settled.**
   - *Proposal A (cheap, for Day 8–10):* show a note on the score: "TMDB scores of new films usually start higher and settle in the first year."
   - *Proposal B (needs a retrain, after the course):* give the score target a maturity rule like revenue's, for example scores count only once a film is a year old. Or train on each film's score at a fixed age, which would need dated score snapshots that TMDB doesn't provide.
2. **Revenue is learned from the 13% of films that report money.** The ranges hold on small films so far (79% coverage under $10M on 2019+). *Proposal:* keep it as a README Limitation; no change.
3. **Release years after 2025 stretch "years active".**
   - *Proposal (a `predict()` change, about 5 lines):* judge the track record at the end of the data (2025-12-31) when the release is later. Keep `year` as it is.
   - Effect: the small drama in 2035 would score like 2026. Caveat: the golden snapshot would change.
4. **Revenue plateaus above about $300M.** It is expected from trees, and the $150M+ warning already covers it. *Proposal:* add one line to the warning: "budgets above $300M don't raise the estimate further".
5. **The 2026 holdout is small.** 70 revenue films; TMDB revenue for 2026 is still being filled in. *Proposal:* rerun `ml.eval.audit holdout` after a new pull in spring 2027.
6. **Coverage is uneven across groups** (small-budget films, animation and romance scores). *Proposal (after the course):* a separate conformal q per group (Mondrian CQR). It needs enough calibration films per group, and it means a retrain of the corrections, which are frozen since Day 6.

## Sources

- Romano, Patterson & Candès (2019), Conformalized Quantile Regression, NeurIPS — https://proceedings.neurips.cc/paper_files/paper/2019/file/5103c3584b063c431bd1268e9b5e76fb-Paper.pdf
- Barber, Candès, Ramdas & Tibshirani (2023), Conformal prediction beyond exchangeability, Annals of Statistics — https://arxiv.org/abs/2202.13415
- Gneiting & Raftery (2007), Strictly proper scoring rules, prediction, and estimation, JASA 102(477)
- Lundberg et al. (2020), From local explanations to global understanding with explainable AI for trees, Nature Machine Intelligence 2, 56–67 — https://arxiv.org/abs/1905.04610
- De Vany & Walls (1999), Uncertainty in the movie industry, Journal of Cultural Economics 23, 285–318
- Ravid (1999), Information, blockbusters, and stars, Journal of Business 72(4), 463–492 — https://ideas.repec.org/a/ucp/jnlbus/v72y1999i4p463-92.html
- Elberse (2007), The power of stars, Journal of Marketing 71(4), 102–120
- Einav (2007), Seasonality in the U.S. motion picture industry, RAND Journal of Economics 38(1), 127–145 — https://ideas.repec.org/a/bla/randje/v38y2007i1p127-145.html
- Li & Hitt (2008), Self-selection and information role of online product reviews, Information Systems Research 19(4), 456–474 — https://faculty.wharton.upenn.edu/wp-content/uploads/2012/04/Self-selection.pdf
- Pre-release R² examples: https://arxiv.org/pdf/1804.03565 (0.45–0.50), https://publish.tntech.edu/index.php/PSRCI/article/view/296/535 (0.53)
- Koenker & Bassett (1978), Regression quantiles, Econometrica; Chernozhukov, Fernández-Val & Galichon (2010), Quantile and probability curves without crossing, Econometrica; Efron & Morris (1975), JASA; Tashman (2000), International Journal of Forecasting; Kaufman et al. (2012), ACM TKDD — standard references, cited from the literature, not re-read for this audit
