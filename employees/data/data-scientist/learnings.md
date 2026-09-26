# Data Scientist - Learnings (Pending)

## Pending observations
- **2026-04-24 - Clean build**: Pre-registration + multiple-comparisons correction are the two most-violated rigor principles in industry DS work. Codified both as hard rules.
- **2026-04-24 - Clean build**: Causal claims require causal methods - not just regression. DAG-first approach written in.

- **2026-06-13 - Depth pass (v1.1.0)**: Top-5 verified 2026 sources absorbed as methodology (spotify/confidence, CausalPy, statsforecast, feature-engine, mlforecast) - all permissive, all Gate-0 net-new or operationalizing a rule that was previously only conceptual. Lesson: the employee TAUGHT CUPED/sequential/forecasting/feature-engineering as principles but named no runnable tool; the build_notes had even confessed "no in-house methodology codified yet" for CUPED. A principle without a named tool is a gap, even when the principle is correct.
- **2026-06-13 - Operationalized the open candidate**: CUPED had sat in absorption_candidates since the prior build because the only source found was NOASSERTION (GrowthBook). spotify/confidence (Apache-2.0) closed it cleanly. Lesson: an open candidate is a standing search target - re-run it each pass, the licensing landscape moves.
- **2026-06-13 - Added a proportionate-rigor lane**: every workflow was launch-gated; a quick "is this roughly real?" had no home, so the temptation was to either over-ceremony or skip rigor entirely. Workflow 0 gives the small-task lane with the two non-negotiables kept (effect size + CI, confidence tag). Lesson: rigor must scale to the stakes or it gets bypassed.

## Fleet doctrine
- **Memory writes are namespaced by scope key `{client}:data-scientist:{project}`** (e.g. `acme:data-scientist:checkout-ab-q3`). Never write a client's baseline rate, MDE, or experiment verdict to an unscoped key; never let one client's metric definition leak into another's namespace.
- **SHA-pin any CI-wired check** (a scheduled forecast-accuracy job, an experiment-analysis run) - pin to a commit SHA, not a floating tag.
- **No em-dashes** in any employee file (fleet was purged of them).

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
## Sources

- Upstream: spotify/confidence (license not stated: 286); pymc-labs/CausalPy (license not stated: 1.2k); Nixtla/statsforecast (license not stated: 4.8k); feature-engine/feature_engine (license not stated: 2.2k); Nixtla/mlforecast (license not stated: 1.2k)
- What was used: methodology only: spotify/confidence; noted: pymc-labs/CausalPy, Nixtla/statsforecast, feature-engine/feature_engine, Nixtla/mlforecast
- License notes: licenses not recorded in scan for: spotify/confidence, pymc-labs/CausalPy, Nixtla/statsforecast, feature-engine/feature_engine, Nixtla/mlforecast - verify before reuse; no code vendored
