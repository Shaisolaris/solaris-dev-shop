# AI/ML Engineer - Learnings (Pending)

```
Format: - **<YYYY-MM-DD> - <project/context>**: <what> *Proposed rule: <takeaway>* Tags: [#classical], [#dl], [#cv], [#ts], [#mlops], [#fine-tune], [#leakage], [#drift], [#promoted?]
```

---

## Pending observations

- **2026-04-24 - AI/ML Engineer rebuild**: Clear altitude split from LLM Agent Designer. Training = this employee. Prompting = LLM Agent Designer. Fine-tuning sits here only when truly required (4-question decision tree usually says no).
  *Proposed rule: "If prompting solves it, don't fine-tune" is a bright-line rule. Ship the prompting solution; come back to fine-tune only if volume + cost math justifies.*
  Tags: [#fine-tune-discipline], [#altitude-split]

- **2026-04-24 - AI/ML Engineer rebuild**: "Baseline before complexity" is the single most-violated rule in ML work. Codified as mandatory first step.
  *Proposed rule: Every ML project starts with a baseline (linear or tree, 30 min). Complex models only justify themselves against a baseline floor.*
  Tags: [#baseline-first], [#promoted?]

- **2026-04-24 - AI/ML Engineer rebuild**: For Solaris clients (mostly small-to-medium), classical ML (XGBoost, scikit-learn) covers 95% of real needs. Deep learning on tabular is almost always over-engineering.
  *Proposed rule: Default to classical tabular ML unless data size + problem type genuinely demands deep learning. Computer vision + NLP have different defaults.*
  Tags: [#tabular-classical-default]

---

## Promotion log

| Date | Observation → Rule | Location |
|------|-------------------|----------|
| | | |

## 2026-05-01 - M4 absorption: MetaGPT Engineer spec→code handoff (v0.4.0)
- Pattern: 8-step sequence; schema discipline (verbatim signatures); no scope creep; imports from Shared Knowledge
- Anti-patterns refused: improvements, helper additions, renames
- Source: github.com/FoundationAgents/MetaGPT

## 2026-06-13 - depth pass: ML engineering stack (v0.6.0)
- Added references/ml-engineering-stack.md: fine-tune (Unsloth/Axolotl) -> evaluate (DeepEval) -> track (MLflow) -> serve (vLLM). All Apache-2.0, methodology-only, runtimes host-installed.
- Key bright lines locked: QLoRA-first defaults (rank16/alpha16, 4-bit nf4); eval is a pytest-style test suite with per-metric thresholds (before AND after fine-tune); MLflow registry stage-promotion (Staging->Production) instead of hardcoded paths; serve the model + contract, hand GPU cluster to DevOps; LoRA-adapter hot-swap in vLLM for many-fine-tunes-one-base.
- Fixed: rules.md had 6 phantom reference paths (content was inline in SKILL) - replaced with real files. rag-architecture.md existed but was unregistered in plugin.json - now registered (RAG *builds* still route to LLM Agent Designer).
- Added small-task/prototype lane to SKILL so quick feasibility checks do not get over-built into full pipelines.
## Sources

- Upstream: Unsloth (license not recorded); Axolotl (license not recorded); DeepEval (license not recorded); MLflow (license not recorded); vLLM (license not recorded)
- What was used: noted: Unsloth, Axolotl, DeepEval, vLLM; methodology only: MLflow
- License notes: licenses not recorded in scan for: Unsloth, Axolotl, DeepEval, MLflow, vLLM - verify before reuse; no code vendored
