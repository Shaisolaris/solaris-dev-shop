# Experimentation + forecasting stack (operational methodology)

Methodology lifted 2026-06-13 from five verified 2026 sources (no code or binaries bundled - all host-installed tools, see install notes). Stars/license/last-activity verified live on 2026-06-13. Each passed Gate-0 against this employee's existing content (see TOP5-CANDIDATES.md for the per-source verdict).

This file sits UNDER the existing rules.md gates. It does not change a single statistical rule - it gives the rules a named, runnable tool so the employee stops gesturing ("supported by major experimentation platforms", "ARIMA/Prophet/state-space") and can actually run CUPED, sequential tests, staggered DiD, and auto-tuned forecasts. The gate always wins: a tool is a surface the rules run ON, never a license to skip pre-registration, the assumption block, or the verdict tag.

## 1. A-B analysis with variance reduction + sequential testing - spotify/confidence
[spotify/confidence, Apache-2.0, 286 stars, release 4.1.0 2026-02-26, maintainer Spotify - ABSORB methodology]

Closes the longest-standing open candidate on this employee: CUPED was logged as "no in-house methodology codified yet" (rules.md). This is the in-house methodology.

- Use when: you are analysing a frequentist A-B test and want CUPED variance reduction, a sequential read, an SRM check, or a guardrail/non-inferiority call without hand-rolling the math on top of statsmodels.
- CUPED (variance reduction): fit a linear model on a pre-exposure covariate (the same metric measured in a pre-period) and analyse the residualised metric. Cuts variance, so the same MDE needs fewer users / less time. Doctrine that still binds: validate SRM and pre-period balance FIRST (a CUPED adjustment on a broken randomisation is garbage); the covariate must be pre-treatment (using any post-exposure signal reintroduces the bias CUPED removes). CUPED lowers N, it does not lower rigor.
- Sequential testing: supports group-sequential tests (pre-scheduled looks with alpha-spending) and always-valid inference (look anytime). This is the operational answer to the peeking gate - instead of "do not peek", you pre-commit a spending function and CAN look. Map to rules.md: peeking inflates alpha 0.05 -> ~0.13 with three naive looks; a group-sequential design spends alpha across those looks so the family-wise rate stays at 0.05. The stopping rule is still pre-committed - sequential testing is a licensed way to look, not a license to stop on a good day.
- SRM detection: ships a sample-ratio-mismatch check; wire it to the rules.md SRM gate (|n_c - n_t|/expected < 1% or the experiment is broken).
- Guardrails + non-inferiority margins: native support for guardrail metrics and non-inferiority bounds, matching the metric-triad rule (primary / secondary / guardrail) and the "guardrail failure kills the ship even if the primary wins" principle.
- Output discipline carried over: every read still returns effect size + CI (not a bare p), still answers statistical AND practical significance, still ends in the Bottom Line -> What -> Why -> How to Act readout with a Verified/Likely/Inconclusive tag.
- Host install: `pip install spotify-confidence`. Pure Python on top of statsmodels (already absorbed) and pandas; optional Chartify charts.

## 2. Quasi-experimental causal inference - pymc-labs/CausalPy
[pymc-labs/CausalPy, Apache-2.0, 1.2k stars, release 0.8.1 2026-05-15, maintainer PyMC Labs - ABSORB methodology]

Extends the causal method table in rules.md with the designs the python-causality-handbook chapters do not cover, plus decision-ready uncertainty outputs.

- Net-new methods over the existing DiD/PSM/RDD/synthetic-control/IV table:
  - Staggered Difference-in-Differences: units adopt treatment at different times; uses an imputation approach (model untreated outcomes, compare observed to counterfactual) that avoids the negative-weighting bias of naive two-way fixed effects. Use when a rollout is staggered, not a clean single before/after.
  - Interrupted time series: level/trend change at a known intervention point for a single series with no control group. The honest assumption: the pre-intervention trend would have continued absent the intervention (state it, plot it).
  - Geographical lift: synthetic-control-style measurement of a geo-targeted campaign by building a synthetic control region from untreated geos. This is the Python, Apache-2.0, clearly-active alternative to GeoLift (R, recency-borderline).
  - Regression kink: a slope change (not a jump) at a threshold - the kink analogue of RDD.
  - Inverse-propensity weighting as a first-class method (the table only named PSM/IPW in passing).
- Decision-ready outputs that match this employee's quality bar: HDI (highest-density interval) credible intervals on Bayesian fits and confidence intervals on the OLS fits (the "CI on every claim" rule); ROPE (region of practical equivalence) for the practical-vs-statistical-significance call; directional tail probabilities P(effect > 0) for "probability the variant is better" semantics (the Bayesian-vs-frequentist standing call).
- Doctrine that still binds: the named assumption for each design is still checked FIRST and honestly. Bayesian-first estimation does not relax the parallel-trends / overlap / continuity / pre-treatment-fit checks; if the assumption fails, the deliverable is still "not causally answerable with this data". Sensitivity analysis still accompanies any exec-bound causal claim.
- When NOT to use it (from the repo's own framing, worth carrying): causal discovery from weakly identified observational data, or fully automated black-box causal answers with no stated design. Those stay refusals.
- Host install: `pip install CausalPy` (or `conda install causalpy -c conda-forge`). Built on PyMC + ArviZ, with an scikit-learn OLS path for non-Bayesian fits.

## 3. Classical auto-forecasting - Nixtla/statsforecast
[Nixtla/statsforecast, Apache-2.0, 4.8k stars, pushed 2026-05-26, maintainer Nixtla - CONNECT / METHODOLOGY]

Gives the forecasting workflow named, auto-tuned models instead of the current "ARIMA/Prophet/state-space" gesture, with the probabilistic intervals the assumption-block rule demands.

- Use when: the forecast is a real time series (revenue, demand, traffic) and you want a strong statistical baseline fast.
- Models: AutoARIMA, AutoETS, AutoCES, AutoTheta (each auto-selects orders/parameters), and MSTL for multiple seasonalities (daily + weekly + yearly). The rules already mandate "baseline first (naive/seasonal-naive)"; this is the next tier - and statsforecast also ships the naive/seasonal-naive baselines, so the baseline-vs-model accuracy comparison (MAE/RMSE/MAPE against naive) is a single API.
- Probabilistic forecasting: native prediction intervals and conformal intervals. This is how the three-number deliverable (low/base/high) gets its band defensibly, and it satisfies "a single undefended number is refused". State the interval method in the assumption block alongside rate/window/weighting/coverage.
- Validation discipline carried over: walk-forward / out-of-sample only - statsforecast's `cross_validation` does rolling-origin evaluation that respects the temporal order (never a random split on time series). The CoV input-reliability bands and cohort-decomposition rules from commercial-forecaster still run first; the tool forecasts the series, the rules decide whether the series is forecastable.
- Host install: `pip install statsforecast`. Scales to many series; optional Spark/Dask/Ray backends.

## 4. Leakage-safe feature engineering - feature-engine/feature_engine
[feature-engine/feature_engine, BSD-3-Clause, 2.2k stars, release 1.9.4 2026-02-27, maintainer Train in Data - CONNECT]

The modeling-prep layer the employee only referenced as a one-line "time features without leakage". feature-engine makes the leakage-safe pattern the default by being sklearn-Pipeline native (fit on train, transform train+test).

- Use when (statistical-QA side, the part this employee owns): you are escalated a model whose features were built ad hoc, and you need to check or rebuild the feature step without train/test leakage. Training itself still belongs to AI/ML Engineer - this is for the leakage/calibration/baseline QA the rules already require.
- Net-new, leakage-safe transformers worth knowing by name:
  - Time-series features: LagFeatures, WindowFeatures, ExpandingWindowFeatures - generate lag/rolling/expanding features inside a Pipeline so they are fit on the training window only (the operational form of rules.md:138).
  - Cyclical encodings: CyclicalFeatures (sin/cos for day-of-week, month) - the documented anti-leakage time encoding.
  - Categorical encoders: MeanEncoder (target), WoEEncoder, RareLabelEncoder - the dangerous ones for leakage; as transformers they learn the mapping on train and apply it to test, which is exactly the discipline to enforce.
  - Selection with drift awareness: DropHighPSIFeatures (drops features whose Population Stability Index shifts across a split - the same PSI used in drift monitoring), SmartCorrelationSelection, MRMR.
- Doctrine that binds: a feature step is part of the leakage check in the model-eval QA (rules.md). "Leakage check between train and test" now has a concrete failure mode to look for - any encoder or aggregate fit on the full dataset before splitting. EDA still precedes feature work (distributions, missingness, outliers documented).
- Host install: `pip install feature_engine`. Pure-Python, scikit-learn compatible.

## 5. ML-based forecasting - Nixtla/mlforecast
[Nixtla/mlforecast, Apache-2.0, 1.2k stars, release 1.0.2 2026-02-18, maintainer Nixtla - CONNECT]

The ML complement to statsforecast's classical lane, for when the series has rich exogenous features or non-linear structure a gradient-boosted model captures better than ARIMA/ETS.

- Use when: the forecast benefits from covariates (price, promo, holidays) and a tree model (LightGBM/XGBoost) or any sklearn regressor, and you still need it leakage-safe.
- The key safety property: mlforecast auto-generates lag, rolling, and date features and applies them respecting the forecast horizon, so the temporal-split / no-leakage rule is enforced by construction rather than by hand. Same principle as feature-engine's time-series transformers, specialised for forecasting.
- Conformal prediction intervals: distribution-free intervals for the three-number band, an alternative to statsforecast's parametric intervals - state which one you used in the assumption block.
- Validation: built-in rolling-origin cross-validation (walk-forward), the only valid out-of-sample protocol for time series; always report MAE/RMSE/MAPE against the naive baseline.
- Relationship to statsforecast (CONNECT): classical first (statsforecast AutoARIMA/AutoETS as the strong baseline), reach for mlforecast when covariates or non-linearity justify it, and always compare both against naive. Two engines disagreeing is a data/definition signal, not a tool preference.
- Host install: `pip install mlforecast` (plus your chosen regressor, e.g. `lightgbm`).

## Cross-cutting doctrine
- All five are permissive (Apache-2.0 / BSD-3-Clause), local-first, free, host-installed. None is bundled into the employee. None replaces a gate.
- Tool choice never changes a statistical conclusion. CUPED lowers N but not rigor; a Bayesian causal fit still checks the design assumption; an auto-forecast still ships the assumption block and the naive-baseline comparison.
- Pinning: when any of these is wired into CI (a scheduled forecast-accuracy check, an experiment-analysis job), SHA-pin the action and pin the package version - reproducibility requires the exact environment, per the seeds/dataset-version rule.
- Memory writes about a specific experiment or forecast are namespaced by scope key `{client}:data-scientist:{project}` - never an unscoped key, never leak one client's baseline or MDE into another's namespace.
