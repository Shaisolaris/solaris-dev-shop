# Data Analyst - Learnings (Pending)

## Pending observations
- **2026-04-24 - Clean build**: Altitude split clear - Analyst does business insights + dashboards + SQL; Scientist does stats + ML + experiments; Engineer builds pipelines.
- **2026-04-24 - Clean build**: "Clarify the decision first" is the meta-skill; queries without a decision behind them are waste.

- **2026-06-09 - Source rebuild**: v0.3.0 credited 7 sources but never wrote their workflows in. Rebuilt from the actual repos; sickn33's sql/kpi skills turned out to be wshobson mirrors - only its analytics-tracking skill was original. Lesson: a credit without an extraction log is a placeholder, not an absorption.

- **2026-06-13 - Depth pass (v1.2.0)**: Top-5 verified sources for the analyst compute/reporting layer (DuckDB, Polars, Great Expectations, marimo, Evidence) - all Gate-0 net-new, all permissive licenses. Lesson: the employee taught SQL + dashboards + Excel but had no local-first compute layer (no warehouse-free way to query a client file drop) and no notebook-reporting surface. Filled both as methodology, no binaries bundled.
- **2026-06-13 - Found + fixed an orphaned reference**: references/excel-mcp-patterns.md existed on disk and was cited in SKILL.md/rules.md prose but was missing from plugin.json `references[]`. Lesson: a file on disk is not registered until it's in references[]; check list-vs-exists both directions.
- **2026-06-13 - Operationalized the DQS score**: the gate had weights (30/25/20/15/10) and bands but never stated how to combine dimensions into the 0-100 number. Added the explicit weighted formula + per-dimension 0-100 scoring. Lesson: a score with weights but no formula is unrunnable; spell out the arithmetic.

## Fleet doctrine
- **Memory writes are namespaced by scope key `{client}:{employee}:{project}`** (e.g. `acme:data-analyst:q3-churn-review`). Never write a cross-client fact to an unscoped key; never let one client's metric definition leak into another's namespace.
- **SHA-pin any CI actions** (e.g. a Great Expectations or dbt check wired into CI) - pin to a commit SHA, not a floating tag.
- **No em-dashes** in any employee file (fleet was purged of them).

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
