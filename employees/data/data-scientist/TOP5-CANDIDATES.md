# Data Scientist - Top-5 verified 2026 sources (depth pass 2026-06-13)

Scope: modeling / experimentation / A-B testing / statistics / feature engineering / forecasting / notebooks.
All metadata verified live on 2026-06-13 via the GitHub web UI and release pages (the api.github.com JSON endpoint was intermittently unreachable from the workspace this session; star/license/release facts were read from the rendered repo pages and release tags instead, which carry the same numbers).

Gate bar applied: established and safe, 100+ stars OR a 50+ notable maintainer, permissive license preferred (GPL/AGPL/NOASSERTION flagged), a commit/release within ~6 months of 2026-06-13.

Gate-0 method: grepped SKILL.md + rules.md for each candidate's concepts and named tools. "Present?" = is the concept already taught. "Content-duplicate?" = would absorbing it merely restate existing prose.

## The five

| # | Source | URL | Stars | License | Last activity | Maintainer | What it adds | Gate-0 verdict | Tag |
|---|--------|-----|-------|---------|---------------|-----------|--------------|----------------|-----|
| 1 | spotify/confidence | https://github.com/spotify/confidence | 286 | Apache-2.0 | release 4.1.0, 2026-02-26 | Spotify (notable maintainer) | Operational A-B analysis library bundling exactly the gaps this employee documents only conceptually: CUPED variance reduction, frequentist sequential testing (group-sequential + always-valid), SRM detection, guardrail metrics, non-inferiority margins, Welch and Z and chi-square, all as statsmodels wrappers. | Concepts PARTLY present (CUPED, SPRT, SRM, guardrails are named but rules.md:71 explicitly says "no in-house methodology codified yet"). NOT a content-duplicate: it operationalizes them. | ABSORB (methodology) |
| 2 | pymc-labs/CausalPy | https://github.com/pymc-labs/CausalPy | 1.2k | Apache-2.0 | release 0.8.1, 2026-05-15 | PyMC Labs (notable maintainer) | Quasi-experimental causal toolkit with depth beyond the current handbook table: staggered Difference-in-Differences, interrupted time series, geographical lift, regression kink, inverse-propensity weighting, plus decision-ready outputs (HDI credible intervals, ROPE practical-significance, directional tail probabilities). | DiD/RDD/synthetic-control/IV present from the causality handbook; staggered DiD, interrupted TS, geo-lift, regression kink, ROPE all ABSENT. NOT a duplicate. | ABSORB (methodology) |
| 3 | Nixtla/statsforecast | https://github.com/Nixtla/statsforecast | 4.8k | Apache-2.0 | pushed 2026-05-26 | Nixtla (notable maintainer) | Fast classical forecasting with the named models the rules only gesture at: AutoARIMA, AutoETS, AutoCES, AutoTheta, MSTL (multi-seasonal), with built-in probabilistic prediction intervals and conformal intervals. The strong, auto-tuned baseline family the forecasting workflow needs. | rules.md:94 only says "ARIMA/Prophet/state-space"; no Auto* models, no MSTL, no probabilistic/conformal intervals named. NOT a duplicate. | CONNECT / METHODOLOGY |
| 4 | feature-engine/feature_engine | https://github.com/feature-engine/feature_engine | 2.2k | BSD-3-Clause | release 1.9.4, 2026-02-27 | Train in Data / Soledad Galli (notable maintainer) | sklearn-compatible feature engineering and selection with leakage-safe fit/transform transformers: target/WoE/rare-label encoders, lag/window/expanding time-series features, cyclical encodings, DropHighPSIFeatures (drift), SmartCorrelationSelection, MRMR. The modeling-prep layer the employee references only as a one-line "time features without leakage". | Only rules.md:138 ("cyclical sin/cos, lag/rolling respecting the split") touches this. Whole feature-engineering territory otherwise ABSENT. NOT a duplicate. | CONNECT |
| 5 | Nixtla/mlforecast | https://github.com/Nixtla/mlforecast | 1.2k | Apache-2.0 | release 1.0.2, 2026-02-18 | Nixtla (notable maintainer) | ML-based forecasting (gradient-boosted and any sklearn regressor) with automatic leakage-safe lag/rolling/date feature generation respecting the temporal split, plus conformal prediction intervals and built-in cross-validation. The ML complement to statsforecast's classical lane. | Entirely ABSENT (no mlforecast, no gradient-boosted forecasting). NOT a duplicate. | CONNECT |

## Honorable mentions / rejected

- facebookincubator/GeoLift (MIT, R) - geo synthetic-control. REJECTED for the top-5: last clearly-datable activity (Apr 2025 issues, Oct 2025 PR) puts the last commit on or past the ~6-month edge, and its methodology overlaps CausalPy's geographical lift (which is Python, Apache-2.0, and clearly active). Logged as a future re-check.
- dmitry-brazhenko/ab-test-advanced-toolkit (MIT) - CUPED + gradient boosting. REJECTED: 31 stars, single-author, fails the 100-star and notable-maintainer bars. spotify/confidence covers CUPED with a real maintainer.
- educauchy/auto-ab - CUPED/CUPAC. REJECTED: small, unverified maintainer.
- jakorostami/expectation - e-values / confidence sequences / always-valid inference. REJECTED: small repo, last clear version 0.5.2 (2024), recency and stars unverified. The always-valid-inference need is met by spotify/confidence's sequential testing.
- GrowthBook - still NOASSERTION-licensed (the prior build flagged it). Stays rejected for absorption; usable only as a self-host platform reference.

## Licenses flagged
- None of the five are GPL/AGPL/NOASSERTION. All are Apache-2.0 or BSD-3-Clause (permissive). No copyleft self-host caveat required. Per fleet doctrine they are still treated as METHODOLOGY (no code/binaries bundled into the employee; all host-installed).
