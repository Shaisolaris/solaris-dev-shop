# Measurement Science - MMM, Incrementality, CLV/LTV

Deepened/registered 2026-06-13. Operationalises the attribution layer that `rules.md` and the description only name-drop (MMM, incrementality testing, LTV:CAC). Methodology only - no library code is bundled. Each tool is self-host / run-on-host; auto-deploy does NOT install or run these. The rules in `rules.md` (gates, bidding, audit) remain the source of truth; this file is the triangulation + true-lift + LTV-derivation layer that the platform-reported numbers get checked against.

Core stance (unchanged from rules.md, made operational here): **platform-reported ROAS is self-attributed and inflated.** Three independent lenses must agree before a spend verdict is trusted: (1) platform/MTA last-touch (directional, biased high), (2) incrementality test (causal, gold standard, expensive), (3) MMM (holistic, privacy-safe, no user-level data). When they disagree, incrementality wins on causality and MMM wins on allocation.

---

## 1. Marketing Mix Modeling (MMM) - the post-cookie allocation layer

When to reach for it: spend is material (rule of thumb >$30-50K/mo total or multi-channel where MTA cannot see cross-channel halo), iOS 14.5 / cookie loss has gutted user-level attribution, or the question is "how should I split next quarter's budget across channels" rather than "which ad won". MMM uses aggregated time-series (weekly spend + KPI + controls), so it survives privacy changes.

### The two transforms every MMM rests on (know these even if a library does the math)
- **Adstock (carryover):** ad effect decays over time, it does not all land in week 0. Model spend_effect_t = spend_t + theta * spend_effect_{t-1}, theta in [0,1) = retention rate. High-consideration B2B carries longer (theta ~0.6-0.8); impulse ecom shorter (~0.1-0.3). A model with no adstock systematically under-credits upper-funnel channels.
- **Saturation (diminishing returns):** doubling spend does not double conversions. Hill / logistic curve maps spend to response with an inflection + ceiling. The marginal ROI (mROI = slope at current spend) is what drives reallocation, NOT average ROI. Move budget from channels at/near saturation to channels still on the steep part of their curve.

### MMM workflow (tool-agnostic)
1. **Data:** 2-3 years weekly (or daily if available) per channel: spend, impressions, optionally reach/frequency; plus the KPI (revenue or conversions) and control variables (seasonality, promotions, price, competitor activity, macro). Minimum ~52 weekly observations; more channels need more history.
2. **Model:** Bayesian regression with adstock + saturation per channel. Use priors - do not let the model invent ROI for a channel from noise.
3. **Calibrate with experiments (critical):** feed incrementality-test results (section 2) as priors. An uncalibrated MMM is a correlation machine; calibrated, it becomes causal. This is the single highest-leverage MMM step and the reason MMM + incrementality are run together, not as alternatives.
4. **Validate:** holdout / time-series cross-validation; check fit on held-out weeks, residual patterns, and that channel ROIs are economically plausible (a channel showing 20x ROAS is usually a confound, not a goldmine).
5. **Decide:** read mROI per channel and run the budget-allocation optimiser to a target (max revenue at fixed budget, or min spend at target revenue). Re-run on a fixed cadence (quarterly) and refresh as new weeks arrive.

### Tooling (METHODOLOGY - run on host, none bundled)
- **google/meridian** (Apache-2.0, 1.4k stars, v1.6.1 2026) - Bayesian geo + national MMM; NUTS sampler (GPU recommended), reach-and-frequency optimisation, built-in GeoLift-style experiment calibration, scenario planner to Looker Studio. Strongest for geo-level data. Self-host: `pip install google-meridian`; runs in Colab/own infra, not in this agent.
- **pymc-labs/pymc-marketing** (Apache-2.0, 987 stars, active) - MMM + budget optimiser + CLV in one toolbox; lighter setup than Meridian, no geo requirement. Self-host: `pip install pymc-marketing`.
- Both are permissive (Apache-2.0) - safe to recommend, install on host, and cite. Do not bundle source into this plugin; reference the method and have the host run the library.

---

## 2. Incrementality testing - the causal gold standard

Why: every other number (platform, MTA, even MMM pre-calibration) is correlational. Incrementality answers "what would have happened if I had NOT run this?" - the only honest ROAS. Run it to (a) calibrate MMM, (b) settle a channel whose self-reported ROAS nobody believes (brand search, retargeting, PMax), (c) prove budget cases.

### Methods, cheapest-to-cleanest
- **Conversion-lift / ghost-ads (platform-run):** platform holds out a randomised control that sees a placebo. Cleanest user-level causal read where available (Meta Conversion Lift, Google). Free-ish but platform-controlled and minimum-spend gated.
- **Geo holdout / Synthetic Control (GeoLift):** turn a channel OFF (or up) in a set of geos, leave matched geos as control, measure the divergence. Works when user-level lift is not feasible (cross-channel, offline, privacy-limited). This is the workhorse for advertiser-run tests.
- **Budget-split / scaled-back tests:** crude but cheap - pause a channel for a clean window and watch blended CAC/MER. Confounded by seasonality; use only when geo tests are impossible.

### Geo-test design discipline (where most tests die)
1. **Power FIRST.** Before spending a dollar on the test, run a power calculation: given historical geo variance, how big a lift can this test detect, over how many weeks, with how many treatment geos? If the minimum detectable effect is larger than the lift you expect, the test is dead on arrival - do not run it.
2. **Market selection by matching**, not by gut - pick treatment/control geos whose pre-period KPI trends track each other (synthetic control finds the weighted combination of control geos that best reconstructs treatment's pre-period). Never hand-pick "similar-looking" cities.
3. **Pre-period >= test period** for a stable counterfactual; clean treatment window (no overlapping promos/launches in treatment-only geos).
4. **One change per test.** A geo test with two simultaneous changes measures their sum, not either.
5. **Read lift + confidence interval + cost-per-incremental-conversion**, then feed the point estimate (and its uncertainty) back into the MMM as a prior.

### Tooling
- **facebookincubator/GeoLift** (MIT, 241 stars) - canonical synthetic-control geo-test package: power calculators, market selection, multi-cell, inference + plots, MMM-calibration whitepapers. FLAG: repo is STALE (last release May 2023, no 2025-26 commits) - the METHOD is sound and still the reference, but do not treat the package as a maintained live dependency. For live work prefer Meridian's built-in experiment calibration / a maintained synthetic-control implementation, and use GeoLift's whitepapers + power-calc logic as the methodology. MIT = method freely citable; self-host R package if used at all.

---

## 3. CLV / LTV derivation - so LTV:CAC stops being a guess

`rules.md` makes LTV:CAC >= 3:1 a governing rule but never says how to get LTV; "LTV unknown but spending aggressively" is a red flag with no remedy. This closes that loop.

- **Contractual (subscription/SaaS):** LTV = ARPA * gross_margin / churn_rate (monthly churn -> monthly LTV horizon). Segment churn by cohort/plan; blended churn flatters LTV. For paid-ads targeting, prefer **early-LTV** (e.g. 90-day contribution) over lifetime - it is observable fast enough to optimise bids on.
- **Non-contractual (ecom/transactional):** use a BTYD model (BG/NBD for purchase frequency + Gamma-Gamma for monetary value) rather than a flat "avg order x repeat" guess - it accounts for customers who have silently churned. `pymc-marketing` ships these CLV/BTYD models (Apache-2.0, self-host).
- **Feed it back into bidding:** segment-level LTV drives value-based bidding (tROAS / Max Value) and lookalike seeds (the rule already says seed lookalikes from HIGH-LTV customers - this is how you identify them). High-LTV-predicted segments justify higher tCPA; low-LTV segments get capped or excluded.
- **CAC for the ratio** = blended CAC (total spend / new customers), not platform-reported CPA. Pair early-LTV with CAC payback (<12mo rule) so a healthy LTV:CAC with a 24-month payback still gets flagged on cash grounds.

---

## 4. Putting the three lenses together (the triangulation rule, operational)
- **Default monthly read:** blended CAC + MER (already in cadence) = the floor of truth.
- **Quarterly:** run/refresh MMM for allocation; the SKILL.md "incrementality sanity check" becomes: is there a live or recent geo/lift test calibrating the MMM? If not, schedule one for the most-contested channel.
- **Reconciliation order when numbers fight:** incrementality (causal) > MMM (calibrated, allocation) > MTA/platform (directional only). Never reallocate budget on platform-reported ROAS alone; never declare a channel dead on MTA last-touch alone (it cannot see assist/halo).
- **Connector tie-in:** the live Google/Meta MCPs (rules.md "Live ad-platform connectors") supply the spend + conversion time series MMM needs and the per-geo reads geo-tests need - but their self-attributed ROAS still passes through this triangulation before any verdict.

---

## CONNECT / self-host summary (auto-deploy installs none of these)
- Meridian (Apache-2.0): `pip install google-meridian`; host/Colab, GPU recommended. Methodology + optional host run.
- pymc-marketing (Apache-2.0): `pip install pymc-marketing`; host. MMM + budget opt + CLV.
- GeoLift (MIT, STALE): R package; method/whitepapers only, not a maintained dependency.
- All three are permissive licenses - cite and recommend freely; bundle nothing into the plugin.

Memory scope key for any saved test results / model outputs: `marketing/paid-ads-manager/measurement/<account-id>` (per-account, never global) so one client's MMM priors or geo-test lift never bleed into another account's verdicts.
