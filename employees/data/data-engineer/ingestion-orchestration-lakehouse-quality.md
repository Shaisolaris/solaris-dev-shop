# Ingestion, asset-orchestration, lakehouse + standalone DQ - methodology

Deepen pass 2026-06-13. Methodology distilled from verified 2026 Tier-1 sources; NO upstream code bundled. Covers four gaps the prior build named but did not operationalize: custom ingestion, asset-based orchestration, lakehouse table format, and data-quality gates that run OUTSIDE dbt.

Citation keys (this file): [dlt] dlt-hub/dlt Apache-2.0 5,345* pushed 2026-05-20 · [dag] dagster-io/dagster Apache-2.0 ~15.7k* · [ice] apache/iceberg Apache-2.0 ~8.9k* rel 1.10.2 2026-05-18 · [soda] sodadata/soda-core AGPL-3.0 ~2.4k* (METHODOLOGY ONLY) · [ge] great-expectations/great_expectations Apache-2.0 ~11.5k*.

---

## 1. Custom ingestion with dlt [dlt] - ABSORB (Apache-2.0)
Fills the branch the ingestion ladder names but never operationalizes: "custom connector only when no maintained Fivetran/Airbyte connector exists." dlt IS that connector layer - prefer it over hand-rolled scripts.

- **When** no maintained managed connector exists, OR the source is a plain REST API / SQL DB / file drop and a full Fivetran seat is overkill -> reach for dlt before writing bespoke ingest code. Still below CDC/managed on the ladder for high-volume OLTP; above raw custom scripts always.
- **Core model**: a `@dlt.resource` yields records; a `@dlt.source` groups resources; `pipeline.run(source, destination=..., dataset_name=...)` loads to the warehouse/lake. dlt does schema inference, normalization (nested -> child tables), and type coercion on load.
- **Incremental loading** (do not re-implement watermarks by hand): declare a cursor - `dlt.sources.incremental("updated_at", initial_value=...)`; dlt persists state per pipeline so reruns resume, not re-scan. This is the dlt equivalent of the static-bound + max() watermark rule - same intent, managed state.
- **Write dispositions** map onto the materialization doctrine: `append` (provably append-only events), `replace` (small dims / full refresh), `merge` with `primary_key` + optional `merge_key` (the default for updatable data - same "verify the key is unique first" rule applies).
- **Schema evolution**: dlt evolves the destination schema as the source changes; pin `schema_contract` (`evolve`/`freeze`/`discard_row`/`discard_value`) at the boundary so silent drift is a choice, not an accident - this is the on_schema_change discipline at the ingestion tier.
- **Idempotency / observability**: each run is a load package with a load_id; failed loads are resumable and do not half-write. Pairs with the pipeline iron rule (idempotent/atomic/incremental/observable).
- **Where it lands**: dlt loads RAW; dbt still owns staging->marts. dlt = E+L, dbt = T. Do not push business logic into dlt resources.
- **W0 fit**: dlt `replace` is the fast, idempotent path for the prototype lane - one-off pulls without standing up a managed connector.

## 2. Asset-based orchestration with Dagster [dag] - METHODOLOGY (Apache-2.0)
The orchestration rules are 100% Airflow/task-shaped. Dagster is the asset-shaped alternative; know when each wins.

- **Paradigm difference**: Airflow orchestrates TASKS (do this, then that); Dagster orchestrates ASSETS (declare the table/model/dataset that should exist; the graph + lineage are derived). Software-defined assets make the data the unit, not the operation.
- **Orchestrator-choice rule**:
  - Existing Airflow + ops-style/task-centric DAGs, or non-data workloads in the same scheduler -> stay on Airflow (the existing defaults still apply).
  - dbt-centric / asset-centric shop wanting lineage + data-quality + backfills as first-class, or a greenfield data platform -> Dagster is the stronger default. `@dbt_assets` maps each dbt model to a Dagster asset automatically (lineage for free, no parallel DAG to maintain).
  - Lightweight Python-first, few external sensors -> Prefect is the lighter third option.
- **Asset checks** = inline data-quality gated on the asset (blocking or warning), the Dagster-native answer to "fail the run, not a silent warning." Complements, does not replace, dbt tests.
- **Partitions + backfills** are first-class: a partitioned asset backfills per logical partition - same "process your own logical date, never latest" rule, enforced by the framework.
- **Carry-over**: the idempotent/atomic/incremental/observable iron rule is orchestrator-agnostic; freshness policies, retries, and failure alerting all have Dagster equivalents (freshness checks, RetryPolicy, run failure sensors) - apply the same hard numbers.

## 3. Lakehouse table format with Apache Iceberg [ice] - METHODOLOGY (Apache-2.0)
Biggest topical gap: the employee had warehouses but no open table-format / lakehouse-storage layer.

- **When** to reach for a table format (Iceberg/Delta/Hudi) instead of native warehouse tables: data already lives in object storage (S3/GCS/ADLS) and must be queried by MULTIPLE engines (Spark + Trino + Snowflake + Flink) without copies; you want warehouse-grade ACID + schema evolution on a data lake; or you are avoiding warehouse-storage lock-in / cost on very large tables. If everything is single-engine inside one warehouse, native tables are simpler - do not add Iceberg for its own sake.
- **What Iceberg buys**: ACID snapshot isolation, time-travel + rollback (query/restore a prior snapshot), hidden partitioning (partition without leaking partition columns into every query - kills the "forgot the partition filter" full-scan class), in-place schema AND partition evolution without rewriting data, row-level MERGE/upsert on the lake.
- **Catalog decision**: a catalog tracks table metadata pointers - REST catalog (engine-neutral, increasingly the default), AWS Glue, Snowflake-managed, or Polaris. Pick one catalog as the single source of truth; multiple uncoordinated catalogs over the same files corrupt state.
- **Maintenance is real work**: schedule compaction (small-file problem), snapshot expiration, and orphan-file cleanup - an unmaintained Iceberg table degrades read performance and leaks storage. Treat these as pipeline tasks with the same observability bar.
- **Iceberg vs Delta**: both are mature; choose by engine ecosystem (Iceberg = broadest multi-engine + Trino/Flink; Delta = Databricks-first). Conform to the client's existing stack.

## 4. Standalone data-quality gates [soda AGPL / ge Apache] - METHODOLOGY
Operationalizes the asserted-but-unexecutable rule "validate source data BEFORE transformation" - dbt tests only run inside the dbt DAG, so pre-transform and non-dbt assets need an external engine.

- **When** to add an external DQ engine: validate RAW/landed data before it enters dbt; gate non-dbt assets (files, streams, operational DBs); enforce a data contract at a team boundary where the producer is not a dbt project. Inside-dbt checks stay as dbt tests (do not duplicate).
- **Soda Core [soda] - FLAG: AGPL-3.0, methodology + self-host note ONLY**:
  - Checks-as-config in SodaCL (YAML): freshness, schema (required columns/types), row_count thresholds, missing/duplicate counts, distribution + anomaly, and cross-dataset reconciliation. Run as a pipeline step (`soda scan`) that FAILS the run on breach - the gate, not a log line.
  - Now positioned as a "data contracts engine": verify a producer's contract at the boundary before downstream consumes.
  - **License handling**: AGPL-3.0 is copyleft with a network clause. ABSORB the methodology (checks-as-config, pre-transform gating, contract verification) only. Do NOT bundle, vendor, fork, or build a derivative service around the code. If a client runs it, it is SELF-HOSTED by the client / host on their own infra; we design the checks, they operate the engine. If AGPL is a blocker for the client, use the Apache-2.0 alternative below.
- **Great Expectations [ge] - Apache-2.0 alternative**: expectation suites (e.g. `expect_column_values_to_not_be_null`, `_to_be_between`, `_to_match_regex`) + checkpoints that gate the pipeline, plus Data Docs (human-readable validation results as living documentation). Profiling can seed an initial suite from real data. Choose GE over Soda when the AGPL license is unacceptable or when validation-as-documentation (Data Docs) is the priority.
- **Decision**: dbt tests for in-warehouse dbt models (primary); Soda or GE as the EXTERNAL gate for pre-transform/non-dbt/contract-boundary validation; DataHub (already a CONNECT) for cross-estate lineage + assertion surfacing. Three layers, distinct jobs - do not collapse them.

---

## Cross-references
- Ingestion ladder (managed > CDC > dlt > raw custom): rules.md "Decision rules - architecture & ingestion".
- Materialization + incremental strategy that dlt write-dispositions mirror: rules.md "Decision rules - dbt modeling".
- "Fail the run, not a silent warning" + "validate before transformation": rules.md "Decision rules - testing & quality gates".
- Governed agent access to these sources: references/mcp-toolbox-multidb-patterns.md.
