# Analyst compute + reporting stack (local-first methodology)

Methodology lifted 2026-06-13 from four verified 2026 sources (no code/binaries bundled - all host-installed tools, see install notes). Each passed Gate-0 against this employee's content (zero prior coverage). Stars/license/last-commit verified live via the GitHub API on 2026-06-13.

This file gives the analyst a local-first compute + reporting layer that sits UNDER the existing BI-tool list and Excel delivery: query large files without a warehouse, transform in memory without choking pandas, write reproducible analysis, and ship BI as reviewable code.

## 1. In-process SQL over files - DuckDB
[duckdb/duckdb, MIT, 38.3k stars, pushed 2026-05-20 - METHODOLOGY]
- Use when: a client hands over Parquet/CSV/Arrow/a pandas frame and you want analytical SQL NOW, with no warehouse, no server, no Snowflake account.
- Patterns the analyst already knows, now runnable on a laptop: window functions, CTEs, `read_parquet('*.parquet')`, `read_csv_auto(...)`, joins, `EXPLAIN ANALYZE` for the costliest-node review from the SQL playbook.
- Doctrine carried over: still state the grain in the alias, still sargable predicates, still `EXPLAIN` before delivery. DuckDB does not change the SQL rules - it just removes the server.
- Relationship to Snowflake CONNECT: DuckDB is the free, local, exploratory complement; Snowflake is the live, commercial, governed warehouse. Profile/prototype in DuckDB; promote durable logic to the warehouse (or to Data Engineer's dbt) when it recurs.
- Host install: `pip install duckdb` (Python) or the standalone CLI. Read-only over the source files - never write back over a client's raw drop.

## 2. Fast in-memory DataFrames - Polars
[pola-rs/polars, MIT, 38.7k stars, pushed 2026-06-02 - METHODOLOGY]
- Use when: a transform is too big or too slow for pandas, or you want lazy execution with predicate/projection pushdown.
- Analyst-relevant patterns: `pl.scan_parquet(...).filter(...).group_by(...).agg(...).collect()` - lazy frame defers work and pushes filters down, the in-memory equivalent of a sargable predicate. Eager `pl.read_csv` for small cuts.
- When to reach for which: small tidy cut -> pandas (ubiquitous, fine). Big local file + SQL mindset -> DuckDB. Big local file + DataFrame chained transforms -> Polars. They interoperate via Arrow, so mix freely.
- Doctrine carried over: the data-quality gate runs FIRST regardless of engine; a faster frame does not excuse skipping null/dupe/type profiling.
- Host install: `pip install polars`.

## 3. Reproducible notebook reporting - marimo
[marimo-team/marimo, Apache-2.0, 21k stars, release 2026-05-11, NumFOCUS-affiliated - METHODOLOGY]
- Use when: the deliverable is an analysis someone must re-run, review, or trust later - not a throwaway query.
- Why over classic Jupyter: stored as pure `.py` (git-diffable, PR-reviewable), no hidden state (deleting a cell scrubs its variables), deterministic execution order by variable dependency, first-class SQL cells, and the same file runs as a script (`python nb.py`) or deploys as an app (`marimo run nb.py`).
- Doctrine: a reproducible notebook still carries the Data Foundation block (sources + quality, n, period + seasonality, methodology) and still tags findings Verified / Likely / Assumed. The notebook is the lab; the report is the story - don't ship the lab as the report.
- Host install: `pip install marimo`; `marimo edit` to author, `marimo run` to serve.

## 4. BI as code - Evidence.dev
[evidence-dev/evidence, MIT, 6.4k stars, pushed 2026-02-18 (oldest of the set, re-verify next pass) - METHODOLOGY]
- Use when: a recurring report should be version-controlled and reviewed like code, not maintained by hand in a GUI BI tool.
- What it is: SQL + Markdown compiled to an interactive BI website; SQL blocks run against a data source (DuckDB is a natural local engine), charts/components render from results, templated pages generate many pages from one template.
- Where it fits the existing stack: alongside the GUI BI tools (Metabase/Looker/Tableau/Power BI/Superset/Grafana) and Excel - this is the code-first, PR-reviewable, git-deployed report. Same dashboard rules apply: one altitude per report, metric contract per number, source documented per panel, owner + review date.
- Doctrine: numbers trace to the same canonical query as any other surface - Evidence is a presentation surface, not a second source of truth (same rule as the Excel layer).
- Host install: `npm install` an Evidence project (`npx degit evidence-dev/template my-report`); runs locally, deploys as a static site.

## Cross-cutting
- All four are local-first and free; none replace the data-quality gate, the metric-contract discipline, or the QA gate - they are surfaces those rules run ON.
- Engine choice never changes the analytical conclusion. If two engines disagree, that is a data or definition bug, not a tool preference.
- License recap: DuckDB MIT, Polars MIT, marimo Apache-2.0, Evidence MIT - all permissive, none GPL/AGPL/NOASSERTION.
