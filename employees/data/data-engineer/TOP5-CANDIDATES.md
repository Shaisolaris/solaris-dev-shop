# Top-5 Verified 2026 Sources - Data Engineer

Research date 2026-06-13. Verification: GitHub REST API (dlt confirmed live; others rate-limited mid-run, cross-checked via web search of repo/release pages). Gate-0 = grep of ACTUAL content in SKILL.md + rules.md + plugin.json of THIS employee.

Star/license/recency legend: stars rounded; license SPDX; last-commit = repo pushed_at or latest release. FLAG = non-permissive (GPL/AGPL/NOASSERTION).

---

## 1. dlt-hub/dlt - ABSORB
- URL: https://github.com/dlt-hub/dlt
- Stars: 5,345 (API-confirmed 2026-06-13)
- License: Apache-2.0 (permissive, clean)
- Last commit: 2026-05-20 (API pushed_at; within 6mo)
- Maintainer: dltHub (commercial OSS, well-funded, established)
- What it adds: Pythonic ELT extract/load library - the ingestion-tier methodology the employee lacks. Schema inference + evolution on load, declarative incremental loading (merge/append/replace with primary_key + cursor), REST API / SQL-database / filesystem source factories, pipeline state + load packages for idempotent reruns, "write any connector" pattern for SaaS sources with no maintained Fivetran/Airbyte connector. Fills the custom-connector branch the current rules name but do not operationalize.
- Gate-0 verdict: NOT PRESENT (grep dlt|dlthub|"data load tool" = 0 hits). Net-new. The ingestion section currently jumps from "managed connector" straight to "custom connector only when none exists" with no methodology for the custom case - dlt IS that methodology.
- Tag: ABSORB (Apache-2.0, methodology only - no code bundled per doctrine)

## 2. dagster-io/dagster - METHODOLOGY
- URL: https://github.com/dagster-io/dagster
- Stars: ~15.7k (web-confirmed 2026-06-12)
- License: Apache-2.0 (permissive)
- Last commit: active 2026-06 (continuous; within 6mo)
- Maintainer: Dagster Labs (established orchestration vendor)
- What it adds: Asset-based (software-defined assets) orchestration paradigm - a genuine alternative model to the Airflow task-DAG patterns already codified. Declarative asset graph, asset checks for inline data quality, partitions + backfills first-class, built-in lineage/observability, native dbt integration (@dbt_assets). SKILL description NAMES Dagster/Prefect but rules.md has ZERO Dagster decision rules - only Airflow.
- Gate-0 verdict: content-PARTIAL. "Dagster" appears only in SKILL/plugin description strings; no decision rule, no asset-vs-task guidance, no orchestrator-choice table. Orchestration methodology is 100% Airflow-shaped. Net-new methodology.
- Tag: METHODOLOGY (paradigm + orchestrator-choice rule; no config bundled)

## 3. apache/iceberg - METHODOLOGY
- URL: https://github.com/apache/iceberg
- Stars: ~8.9k (web-confirmed 2026-06-07)
- License: Apache-2.0 (permissive)
- Last commit: release 1.10.2 on 2026-05-18 (within 6mo; continuous main)
- Maintainer: Apache Software Foundation (gold-standard governance)
- What it adds: Open lakehouse table format - the single biggest topical gap. Hidden partitioning, schema + partition evolution without rewrite, snapshot isolation + time-travel, MERGE/upsert on object storage, catalog choice (REST/Glue/Polaris), engine-agnostic (Spark/Trino/Flink/Snowflake/BigQuery). Employee covers warehouses (Snowflake/BQ/Databricks) but has NO table-format / lakehouse-storage layer.
- Gate-0 verdict: NOT PRESENT (grep iceberg|lakehouse|"table format"|"delta lake"|hudi = 0 hits). Net-new. "data lake" appears once as a trigger word with no backing methodology.
- Tag: METHODOLOGY (when-to-reach-for-a-table-format + Iceberg-vs-warehouse-table decision; no infra bundled)

## 4. sodadata/soda-core - METHODOLOGY (FLAG: AGPL)
- URL: https://github.com/sodadata/soda-core
- Stars: ~2.4k (web-confirmed 2026-06)
- License: AGPL-3.0 - FLAGGED (copyleft network license; methodology + self-host note only, never bundle/derive code)
- Last commit: 2026-05-17; release 4.1.1 on 2026-03-05 (within 6mo)
- Maintainer: Soda Data (established DQ vendor; repo now positioned as "Data Contracts engine")
- What it adds: Standalone data-quality + data-contracts engine that runs OUTSIDE dbt - SodaCL checks (freshness, schema, row_count, distribution, anomaly, reconciliation), checks-as-config, contract verification at pipeline boundaries on NON-dbt and pre-transform data. Operationalizes the "validate source BEFORE transformation" rule the employee asserts but cannot currently execute (dbt tests only run inside the dbt DAG).
- Gate-0 verdict: content-PARTIAL. "SodaCL" named once inside the wshobson data-contract YAML pattern; the data-contract CONCEPT exists, but no Soda-as-a-gate methodology, no pre-transform validation tool, no checks-as-config guidance. Methodology net-new; license forces methodology-only treatment.
- Tag: METHODOLOGY (AGPL self-host note)

## 5. great-expectations/great_expectations - CONNECT/METHODOLOGY
- URL: https://github.com/great-expectations/great_expectations
- Stars: ~11.5k (web-confirmed 2026-05-04)
- License: Apache-2.0 (permissive)
- Last commit: 2026-05-04 (within 6mo)
- Maintainer: Great Expectations (established DQ vendor)
- What it adds: Expectation-suite data validation with Data Docs (human-readable validation results), profiling-driven expectation generation, checkpoints, broad backend coverage (Spark/Pandas/SQL). Alternative/complement to Soda for teams wanting validation-as-documentation outside the dbt test framework.
- Gate-0 verdict: NOT PRESENT (grep great.expectation = 0 hits). Net-new, but topically OVERLAPS Soda + dbt tests - lower marginal value than 1-4. Listed as a connect-or-pick alternative.
- Tag: CONNECT / METHODOLOGY (name as the Apache-licensed alternative when AGPL Soda is a blocker)

---

## Considered + rejected
- dbt-labs/dbt-agent-skills (Apache-2.0, actively maintained 2026): already the spine of this employee (4 skills absorbed at file level in the 2026-06-10 rebuild). Gate-0 = content-DUPLICATE. Re-verified current; no new skill files warrant re-absorb this pass.
- apache/airflow (~40k, Apache-2.0): orchestration patterns already deeply absorbed from wshobson. Duplicate.
- apache/spark (Apache-2.0): big-data branch already named (>1TB/day -> Spark); Spark internals out of scope for a pipeline employee.

## Flags summary
- Soda Core = AGPL-3.0 -> methodology + self-host note ONLY; do not bundle, vendor, or derive code.
- All other top-5 = Apache-2.0, clean/permissive, established maintainers, 100+ stars, commits within 6 months.
