# Data Analyst - Top-5 Verified 2026 Source Candidates

Verified 2026-06-13. Stars/license/last-commit pulled live from the GitHub REST API (api.github.com/repos/...) except where noted (WebSearch). Gate-0 = grep of THIS employee's actual content (SKILL.md, rules.md, learnings.md, references/) for the capability before crediting net-new.

Scope covered by the brief: pandas/Polars, SQL analytics, viz, notebook reporting, data-quality/profiling, BI.

| # | Source | URL | Stars | License | Last commit | Maintainer | Gate-0 (in employee already?) | Tag |
|---|--------|-----|-------|---------|-------------|------------|-------------------------------|-----|
| 1 | DuckDB | https://github.com/duckdb/duckdb | 38,323 | MIT | 2026-05-20 (pushed) | DuckDB Foundation / DuckDB Labs | NONE (grep "duckdb" -> 0 hits) | METHODOLOGY |
| 2 | Polars | https://github.com/pola-rs/polars | 38,658 | MIT | 2026-06-02 (pushed) | pola-rs (Ritchie Vink + org) | NONE (grep "polars" -> 0 hits) | METHODOLOGY |
| 3 | Great Expectations | https://github.com/great-expectations/great_expectations | 11,526 | Apache-2.0 | 2026-05-26 (pushed) | Great Expectations (GX) org | NONE (grep "expectation"/"great expectation" -> 0 hits; DQS gate exists but no contract-test concept) | METHODOLOGY |
| 4 | marimo | https://github.com/marimo-team/marimo | 21,000 | Apache-2.0 | 2026-05-11 (release 0.23.6) | marimo-team (NumFOCUS affiliated) | NONE (grep "marimo"/"notebook" -> 0 hits) | METHODOLOGY |
| 5 | Evidence.dev | https://github.com/evidence-dev/evidence | 6,425 | MIT | 2026-02-18 (pushed) | evidence-dev org | NONE (grep "evidence" -> only the English word "evidence" in a hand-off row; no BI-as-code) | METHODOLOGY |

## Per-source detail

### 1. DuckDB (METHODOLOGY)
- What it adds: in-process OLAP SQL engine. Lets the analyst run analytical SQL directly over Parquet/CSV/Arrow/pandas frames with zero warehouse and zero server - the local-first complement to the (commercial, host-installed) Snowflake CONNECT. Window functions, CTEs, `read_parquet`/`read_csv_auto`, `EXPLAIN ANALYZE` - the exact SQL-analysis surface this employee already teaches, but runnable on a laptop against a client file drop.
- Gate-0 verdict: net-new. The SQL playbook (Workflow 2) assumes a server/replica; nothing covers in-process/embedded analytics. NOT a content duplicate.
- Safety: MIT, 38k stars, foundation-backed, monthly releases. Safe.
- Why METHODOLOGY not ABSORB: it is an engine/CLI, not skill content; lift the analyst-facing patterns (embedded SQL over files, EXPLAIN locally, push the cut into Excel/Evidence) into a reference, no binary bundled.

### 2. Polars (METHODOLOGY)
- What it adds: fast columnar DataFrame library (lazy + eager). Net-new dataframe muscle for the analyst beyond pandas idioms: lazy scan/`collect`, predicate/projection pushdown, group-by aggregations, joins without the pandas memory blow-up. Pairs with the data-quality gate (profile a large file the pandas way would choke on).
- Gate-0 verdict: net-new. No dataframe library named anywhere; the employee jumps from SQL to Excel with no in-memory transform layer. NOT a duplicate.
- Safety: MIT, 38k stars, very active (pushed within the week). Safe.
- Why METHODOLOGY: library, not content; lift the analyst-relevant patterns (lazy frame for big local files, sargable-equivalent pushdown, when to reach for Polars vs DuckDB vs pandas) into a reference.

### 3. Great Expectations (METHODOLOGY)
- What it adds: declarative data-quality as executable, versioned "expectations" (unit tests for data) + auto-generated Data Docs. This is the missing operational layer under the employee's existing DQS gate: today the gate is a manual scoring rubric; GX is how you turn it into repeatable, CI-runnable checks (expect_column_values_to_not_be_null, _to_be_between, _to_be_unique, etc.) mapped 1:1 onto the five DQS dimensions.
- Gate-0 verdict: net-new methodology. DQS rubric exists; the contract-test / expectation-suite concept and Data Docs do not. NOT a duplicate - it deepens an existing gate.
- Safety: Apache-2.0 (permissive), 11.5k stars, pushed within 3 weeks. Safe.
- Why METHODOLOGY: heavy framework; lift the expectation-suite pattern + DQS-to-expectation mapping into the rules, no install bundled.

### 4. marimo (METHODOLOGY)
- What it adds: reactive, git-friendly Python notebook stored as pure .py; runs as script OR deploys as an app; first-class SQL cells. Net-new "notebook reporting" surface - reproducible analysis the analyst can hand off as a versioned artifact (no hidden-state Jupyter JSON), or publish as a lightweight interactive app. Directly serves the brief's "notebook reporting" gap.
- Gate-0 verdict: net-new. No notebook tooling of any kind in the employee. NOT a duplicate.
- Safety: Apache-2.0, 21k stars, NumFOCUS-affiliated, release within ~5 weeks. Safe.
- Why METHODOLOGY: tool, not content; lift the reproducible-notebook doctrine (pure-Python, no hidden state, deterministic order, SQL cells, deploy-as-app) into the notebook-reporting reference.

### 5. Evidence.dev (METHODOLOGY)
- What it adds: business-intelligence-as-code - SQL + Markdown compiled to a versioned, PR-reviewed, deployable BI site. Net-new delivery surface alongside the existing BI-tool list (Metabase/Looker/Tableau/etc., all GUI) and Excel: a code-first, git-reviewable report that pairs naturally with DuckDB as its query engine.
- Gate-0 verdict: net-new. The only "evidence" hit is the English word in a hand-off table row; no BI-as-code concept exists. NOT a duplicate.
- Safety: MIT, 6.4k stars, pushed 2026-02-18 (within 6mo, on the older edge - flag for re-check next pass). Safe.
- Why METHODOLOGY: framework, not content; lift the BI-as-code doctrine (SQL+MD, version-controlled reports, PR review, templated pages) into the notebook/BI-reporting reference.

## Flags
- License: none GPL/AGPL/NOASSERTION. 3x MIT, 2x Apache-2.0 - all permissive.
- Evidence.dev last push (2026-02-18) is ~4 months back - inside the 6mo window but the oldest of the five; re-verify activity at next pass.
- ydata-profiling (https://github.com/ydataai/ydata-profiling, MIT, ~13.5k stars per WebSearch, last update 2026-01-14) was a strong profiling candidate but is edged out by Great Expectations for the data-quality slot (GX maps onto the existing DQS gate; ydata is one-shot EDA HTML). Honorable mention; not in the top-5. (GitHub API returned empty bodies for this repo on 2026-06-13; figures are WebSearch-sourced, lower confidence.)

## Disposition this pass
All five tagged METHODOLOGY. One consolidated methodology reference added this pass (references/analyst-compute-and-reporting-stack.md) covering DuckDB + Polars + marimo + Evidence; the Great Expectations expectation-suite pattern is lifted into rules.md under the DQS gate. No code/binaries bundled; all are host-installed tools, install notes included.
