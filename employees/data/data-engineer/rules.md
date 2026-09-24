# Data Engineer - Rules

Last rebuilt: 2026-06-10 from file-level source extraction (artifacts: sources/_analysis/data-engineer/01-05).
Citation keys: [dbt-labs] dbt-labs/dbt-agent-skills · [wsh] wshobson/agents plugins/data-engineering · [alt] AltimateAI/data-engineering-skills · [arz] alirezarezvani/the coding agent-skills senior-data-engineer · [volt] VoltAgent 05-data-ai/data-engineer. Deepen 2026-06-13: [dlt] dlt-hub/dlt · [dag] dagster-io/dagster · [ice] apache/iceberg · [soda] sodadata/soda-core (AGPL, methodology-only) · [ge] great-expectations - see ingestion-orchestration-lakehouse-quality.md.

## Iron rules (non-negotiable)
- **Never modify a test to make it pass without understanding why it's failing.** A failing test is evidence of a problem; changing it hides the problem. "Board meeting in 2 hours", "we've spent 2 days on this", and "probably flaky" are documented STOP rationalizations - flaky means there's an underlying issue. [dbt-labs troubleshooting-dbt-job-errors]
- **Look at the data before modeling it.** `dbt show` to preview inputs, preview the model's output, and profile counts/min/max/nulls on both, every time. No SQL against columns never actually seen. [dbt-labs using-dbt-for-analytics-engineering]
- **Full discovery on every table you build on.** Grain, dup/null PK check, range sanity, orphan counts - documented. "No time for full discovery" → no time for wrong models. Many tables = scope ruthlessly, then full methodology on the in-scope set; never half-discover everything. [dbt-labs discovering-data]
- **Never refactor blind.** `dbt ls --select model_name+` plus `grep -r "ref('model_name')" models/`; report the downstream count before touching anything; check which *columns* downstream uses, not just which models. [alt refactoring-dbt-models; dbt-labs evaluating-impact]
- **Query optimization preserves semantics exactly** - same columns, rows, order, limit - or return the original unchanged. [alt optimizing-query-text]
- **Pipelines are idempotent, atomic, incremental, observable.** Re-run = same result; tasks succeed or fail completely; process only new/changed data; logs+metrics+alerts at every step. [wsh airflow-dag-patterns]

## Decision rules - architecture & ingestion
- **When** batch vs streaming → real-time insight required?
  - No → batch. Then: >1TB/day → Spark/Databricks; else dbt + warehouse compute.
  - Yes → streaming. Exactly-once needed → Kafka + Flink/Spark Structured Streaming; else Kafka + consumer groups.
  - Streaming costs more and reprocesses worse; batch is the default until a latency SLA forces the move. [arz decision tree]
- **When** naming layers → raw → staging → intermediate → marts (dbt shops); bronze/silver/gold is the same idea for Databricks-shop vocabulary. Conform to the project's existing convention. [arz medallion; dbt-labs; wsh]
- **When** ingesting from an OLTP database → CDC via Debezium (pgoutput plugin, publication + replication slot, ExtractNewRecordState unwrap, keep tombstones; handle op codes c=insert / u=update / d=delete / r=snapshot). Managed: Fivetran. Middle ground: Airbyte. Coordinate slot/publication with the DBA - orphaned slots bloat the source DB. [arz data_pipeline_architecture CDC]
- **When** bulk-loading a warehouse → files → object storage as Parquet → external stage → `COPY INTO`. Never row-by-row INSERTs. [arz]
- **When** late/streaming data → watermarks DROP events later than the threshold; late data needs a DLQ or a batch reconciliation path, never silence. [arz workflows]
- **When** SaaS sources (Shopify/Stripe class) → managed connector first (Fivetran/Airbyte), land raw with the loader's sync timestamp (`_fivetran_synced`-style) as `loaded_at_field`, transform in warehouse (ELT). Custom connectors only when no maintained connector exists. [wsh dbt-transformation-patterns sources]
- **When** no maintained connector exists, OR a plain REST API / SQL DB / file source where a Fivetran seat is overkill → **dlt** [dlt-hub/dlt, Apache-2.0 - ABSORB] before hand-rolled scripts: `@dlt.resource`/`@dlt.source` + `pipeline.run(...)`, schema inference on load, `dlt.sources.incremental(cursor)` for managed-state incrementals, write_disposition `append|replace|merge(primary_key)` mirroring the materialization doctrine, `schema_contract` to make drift a choice. dlt loads RAW (E+L); dbt still owns staging→marts. Full pattern: ingestion-orchestration-lakehouse-quality.md. [dlt]

## Decision rules - dbt modeling
- **When** building a new model → plan backwards [dbt-labs planning-dbt-models]:
  1. Mock the final output table - PK/surrogate key, grain, sample rows, materialization choice.
  2. Mock the SQL that would produce it (placeholders fine). Can't write the query → the output design is wrong.
  3. Identify gaps; mock required upstream models.
  4. Match against real project assets: exact match > extend existing > new model, recursively.
  5. Write FAILING unit tests for edge cases (same-day multiple transactions, gap days, nulls) before implementing.
  6. Implement; reuse existing models wherever possible; placeholder columns (`null::integer as x -- TODO`) to pin interfaces.
- **When** asked for a new model → ask "why new vs extending existing?" Prefer one column added to an existing intermediate over a whole new model. Legitimate: different grain, precalc for performance. Habit is not a reason. [dbt-labs]
- **When** writing staging models → `source` CTE → `renamed` CTE only: rename, cast, group columns (ids/strings/timestamps/metadata), unit conversions (cents→dollars), `_loaded_at`. Business logic lives in intermediate, never staging. [wsh Pattern 2]
- **When** referencing → always `{{ ref() }}` / `{{ source() }}`, never hardcoded tables; CTEs over subqueries; read the model's YAML descriptions before building on it - column names don't reveal business meaning. [dbt-labs]
- **When** materializing → source <10M rows: `table`, full stop. >10M: incremental. [alt developing-incremental-models]
- **When** picking incremental strategy [alt; conflict-resolved over wsh]:
  | Strategy | Use when |
  |---|---|
  | `merge` | default - data gets updated; requires verified unique_key |
  | `append` | provably append-only (logs, events); no key needed |
  | `delete+insert` | merge hits duplicate keys, or batch reprocessing |
  | `insert_overwrite` | partitioned BigQuery/Spark tables; replaces partitions |
- **When** creating any incremental model → in order [alt]:
  1. Verify unique_key truly unique (`group by key having count(*) > 1`) BEFORE writing the model.
  2. First build `--full-refresh`, verify counts; then run incremental and verify again.
  3. `on_schema_change='append_new_columns'` (default `ignore` silently drops new columns).
  4. Lookback window for late data: static `>= dateadd(day, -3, current_timestamp)` paired with the `max()` subquery - the static bound is also what restores partition pruning.
  5. Schedule periodic full refresh against drift.
  - Merge failing 3+ times = duplicate keys. Dedup fix: `row_number() over (partition by key order by updated_at desc) = 1`.
- **When** a CTE exceeds ~50 lines → extract to intermediate model; repeated logic across models → macro. [alt refactoring]
- **When** changing an existing model → impact tiers: 1-5 downstream = proceed `state:modified+`; 6-15 = consider depth limit; 16+ = ask operator about `state:modified+N`. Never unselected `dbt build` on a large project. Column removal needs column-level lineage (`get_column_lineage` via dbt MCP, grep fallback), not just model-level. [dbt-labs evaluating-impact]
- **When** building metrics → dbt Semantic Layer, not BI tools. Spec detect: `semantic_model:` nested under a model = latest spec (Core 1.12+/Fusion); top-level `semantic_models:` = legacy (1.6-1.11). Match what the project already uses. [dbt-labs building-dbt-semantic-layer]
- **When** crossing teams/domains → dbt Mesh: read `dependencies.yml` first; cross-project = two-arg `ref('project','model')`; only `access: public` models are reachable; requires dbt Cloud Enterprise - confirm plan before setup, else intra-project groups/access/contracts. [dbt-labs working-with-dbt-mesh]

## Decision rules - testing & quality gates
- **When** placing schema tests by layer [dbt-labs writing-data-tests]:
  - Staging: `unique` + `not_null` on PK; `relationships` on FKs; `accepted_values` on enums verified during discovery.
  - Intermediate: only where grain changes or joins create new keys (composite-key `unique` + `not_null`).
  - Marts: a few critical business invariants (`expression_is_true: "total = subtotal + tax + shipping"`), with debug steps documented in the test description.
  - Don't re-test pass-through columns at every layer.
- **When** judging test value → Tier 1 always: PK unique+not_null, FK relationships. Tier 2 when discovery warrants: accepted_values; not_null on verified-0%-null columns. Tier 3 selective: expression_is_true, accepted_range. Tier 4 avoid: not_null everywhere, unique on non-PK, stacks of expression tests. Discovery says "Y% nulls expected" → do NOT add not_null. [dbt-labs]
- **When** SQL contains regex, date math, window functions, many-WHEN CASE, truncation, complex joins - or fixed a reported bug, or precedes a big refactor → add a dbt unit test (mock inputs → expected output; mock only needed columns). Not for warehouse built-ins like `min()`. Unit tests catch logic bugs; schema tests catch data bugs; a failing unit test blocks materialization. [dbt-labs adding-dbt-unit-test]
- **When** unit-testing with missing upstream parents → `dbt run --select +my_model --exclude my_model --empty` to scaffold schemas. **`--empty` overwrites with zero-row versions - never on tables holding data you need.** [dbt-labs]
- **When** testing large tables → scope test cost with config `where: "created_at >= current_date - interval '7 days'"`. [dbt-labs]
- **When** defining source freshness → `loaded_at_field` + freshness block on EVERY source; daily-batch default `warn_after: 12h`, `error_after: 24h`. Sub-hour freshness requires the streaming/micro-batch cost case made explicitly - freshness SLA is a per-pipeline contract, not a slogan. [wsh sources; volt <1h target; conflict-resolved]
  - Declaration shape (dbt `sources.yml`): `freshness: {warn_after: {count: 12, period: hour}, error_after: {count: 24, period: hour}}` + `loaded_at_field: _loaded_at` on the source/table; verify with `dbt source freshness`. SLA target = period from source-system event time to mart availability; set `error_after` at the point a stale dashboard does real harm, `warn_after` at roughly half that, then tune from observed landing times - not from a round number.
- **When** teams hand data across a boundary → data contract file: owner + schema (types, required, pii flags) + quality checks (row_count > 0, missing/duplicate counts, freshness < SLA) + SLA block (availability, freshness, latency). Inside dbt, Mesh contracts/access serve this role. Schema evolution stays additive; breaking change = new version + migration window. [wsh data-quality-frameworks Pattern 5]
- **When** quality gates fail in pipeline → fail the pipeline run, not a silent warning log. Validate source data BEFORE transformation, not only marts after. [wsh]

## Decision rules - orchestration (Airflow patterns)
- **When** choosing an orchestrator → existing Airflow / task-centric / mixed non-data workloads = stay Airflow (defaults below). dbt-centric or asset-centric shop wanting lineage + DQ + backfills first-class, or greenfield = **Dagster** [dagster-io/dagster, Apache-2.0 - METHODOLOGY]: software-defined ASSETS not tasks, `@dbt_assets` auto-maps dbt models (lineage free), asset checks = inline blocking DQ, partitioned backfills enforce "process your own logical date." Prefect = lighter Python-first third option. The idempotent/atomic/incremental/observable iron rule + hard numbers are orchestrator-agnostic. Full pattern: ingestion-orchestration-lakehouse-quality.md. [dag]
- **When** writing a DAG → defaults [wsh airflow-dag-patterns]:
  - `retries: 3`, `retry_delay: 5min`, `retry_exponential_backoff: True`, `max_retry_delay: 1h`
  - `catchup=False` unless backfill intended; `max_active_runs=1`; explicit `tags`
  - TaskFlow API; no heavy logic in the DAG file (import from modules); no global state
  - never `depends_on_past=True` (bottleneck); never hardcoded dates - use `{{ ds }}` / `{{ prev_ds }}`
- **When** waiting on external things → sensors with `mode='reschedule'` (frees the worker): S3KeySensor (poke 5min, timeout 2h) for files; ExternalTaskSensor for cross-DAG dependencies; `@task.sensor` for API health. [wsh details Pattern 4]
- **When** wiring alerts → per-task `on_failure_callback` carrying dag_id / task_id / ds / error / log_url to Slack/PagerDuty; cleanup tasks `trigger_rule=ALL_DONE` so they run even on failure. Silent failure is a red flag. [wsh details Pattern 5]
- **When** backfilling → idempotency verify first; resource-reserve so production queries aren't starved; quality check post-run. Tasks always process their own logical date (`{{ ds }}`), never "latest". [wsh; arz; carried v0.5]

## Decision rules - warehouse cost & performance
- **When** hunting Snowflake cost → `QUERY_ATTRIBUTION_HISTORY` ranked by `credits_attributed_compute` (last 7d), then `QUERY_HISTORY` for the top IDs: bytes_scanned, spill local/remote, partitions_scanned vs partitions_total. Read: scanned=total → no pruning; repeated query_hash → caching/materialization opportunity; spill → memory pressure. Deliver ranked list + patterns + top 3-5 fixes. [alt finding-expensive-queries]
- **When** optimizing a query → priority: (1) date/time functions on filter columns → range predicates (`DATE(ts) = 'd'` → `ts >= 'd' and ts < 'd'+1`) to restore pruning; (2) implicit comma joins → explicit JOIN (always safe); (3) `NOT IN` → `NOT EXISTS` only when subquery column provably NOT NULL. NEVER: UNION→UNION ALL, touching window functions, renaming columns/aliases, adding limits. [alt optimizing-query-text]
- **When** developing → `--select` always; `--defer --state path/to/prod` to reuse prod objects; `dbt clone` for zero-copy dev copies; LIMIT pushed early into CTEs; no unpartitioned BigQuery scans. [dbt-labs cost section]
- **When** wiring dbt CI (GitHub Actions) → run `dbt build --select state:modified+` against a CI/PR schema with `--defer --state` to the prod manifest, never an unselected build. SHA-pin every third-party action (`uses: actions/checkout@<full-40-char-sha>  # v4`), never a floating `@v4`/`@main` tag - a moved tag is supply-chain risk. Store warehouse creds as repo/org secrets, never inline. [fleet doctrine; dbt-labs cost section]
- **When** an agent needs dbt access → dbt MCP server over CLI shell-outs. Tool groups (current README): SQL / Semantic Layer / Discovery / dbt CLI / Admin API / Codegen / LSP / Product Docs / metadata. Auth: OAuth for per-user audit contexts; service token (DBT_TOKEN) for solo-dev/CI. [dbt-labs/dbt-mcp README; carried v0.5]
- **When** client is on Snowflake and wants agentic access → the **official Snowflake MCP Server** (docs.snowflake.com, Cortex Agents MCP). Snowflake-Labs/mcp is deprecated upstream (verified 2026-06-10) - do not install it.

## Decision rules - governed data access + catalog (DB MCP layer, added 2026-06-13)
- **When** an agent/client needs governed access to operational DBs or the warehouse → **MCP Toolbox for Databases** [googleapis/mcp-toolbox, Apache-2.0 - ABSORB]: full pattern in mcp-toolbox-multidb-patterns.md. NEVER hand a production agent generic `execute_sql`. Define purpose-built, parameterized, least-privilege tools in `tools.yaml` (sources = connections, secrets in secret-manager not inline; tools = typed-param + parameterized `statement`, injection-safe by construction; toolsets = per-agent scoping). Prebuilt `--prebuilt=<db>` (`list_tables`/`execute_sql`) is for ad-hoc EXPLORATION only, never prod. One grammar across ~20 engines (AlloyDB/BigQuery/Cloud SQL/Spanner/Postgres/MySQL/SQL Server/Oracle/MongoDB/Snowflake/Trino/ClickHouse/...). Built-in pooling + IAM + OpenTelemetry. Toolbox governs data ACCESS; dbt MCP governs TRANSFORMATION - keep the two layers distinct.
- **When** data lives in object storage and must be queried by MULTIPLE engines (Spark/Trino/Snowflake/Flink) with warehouse-grade ACID + schema evolution, or you are avoiding warehouse-storage lock-in on huge tables → open table format, default **Apache Iceberg** [apache/iceberg, Apache-2.0 - METHODOLOGY]: snapshot isolation + time-travel, hidden partitioning (kills forgot-the-filter full scans), in-place schema AND partition evolution, MERGE on the lake. Pick ONE catalog as source of truth (REST/Glue/Polaris); schedule compaction + snapshot-expiry + orphan cleanup as real tasks. Single-engine-in-one-warehouse = native tables, do not add Iceberg for its own sake. Iceberg vs Delta by engine ecosystem. Full pattern: ingestion-orchestration-lakehouse-quality.md. [ice]
- **When** validating RAW/pre-transform data, non-dbt assets, or a producer's contract at a team boundary (dbt tests only run inside the dbt DAG) → external DQ engine as a pipeline gate that FAILS the run: **Soda Core** [sodadata/soda-core - AGPL-3.0, METHODOLOGY + SELF-HOST ONLY] checks-as-config in SodaCL (freshness/schema/row_count/dup/anomaly/reconciliation), now a data-contracts engine - absorb the method, never bundle/fork/derive the AGPL code; client/host self-runs the engine, we design the checks. AGPL a blocker → **Great Expectations** [great-expectations, Apache-2.0] expectation suites + checkpoints + Data Docs. dbt tests stay primary for in-warehouse models; do not collapse the three layers. Full pattern: ingestion-orchestration-lakehouse-quality.md. [soda][ge]
- **When** the org needs metadata lineage / data-quality / discovery across the estate → **DataHub** [acryldata/mcp-server-datahub, Apache-2.0 - CONNECT]: connect the DataHub MCP rather than absorbing it - search the catalog, read end-to-end lineage, surface dataset ownership/quality/assertions to inform impact analysis (complements dbt column-level lineage with cross-platform, non-dbt assets). Use when answering "what's downstream of this table across the whole stack" or "who owns / how fresh is this dataset". Host installs the DataHub MCP; scoped DataHub token, points at the DataHub instance.

- **When** the project needs RAG / vector embeddings populated and kept fresh in **pgvector** [pgvector/pgvector, PostgreSQL License/OSI-permissive - METHODOLOGY] -> treat embeddings as a derived materialization and own the embedding-ELT: chunk = grain (verify (source_id, chunk_index) before load), pin embedding model+dim, batch+hash-idempotent embedding calls, bulk load + ON CONFLICT upsert, hash-incremental re-embed + delete/tombstone reconciliation, versioned (expand-and-contract) model upgrades, and an offline gold-set recall@k gate plus vector DQ checks (no null/zero vec, dim match, no orphans/dups) before deploy. The distance operator <-> index opclass <-> normalization is a 3-owner CONTRACT: agree it with DBA (owns extension + IVFFlat/HNSW index choice) and backend-developer (owns the serving API); we own the pipeline. Full pattern: vector-embedding-pipelines-pgvector.md. [pgv]

## Failure triage (dbt jobs and pipelines)
1. Gather: Admin API `list_jobs_runs` → `get_job_run_error` (or ask for debug logs + `run_results.json` from `/api/v2/accounts/<id>/runs/<id>/artifacts/run_results.json?step=N`). [dbt-labs troubleshooting]
2. Classify: **Infrastructure** (timeouts, connections, permissions) | **Code/Compilation** (undefined macro, parse error) | **Data/Test failure** (test failed with N rows).
3. Investigate per class:
   - Infra: job config timeouts; concurrent jobs competing; failures correlated with time-of-day or volume.
   - Code: `git log --oneline -20`; `git diff HEAD~5..HEAD -- models/ macros/`; `dbt parse`; `dbt compile --select failing_model`; check renamed/deleted files.
   - Data: run the test's own SQL, then discovery on the failing rows - are new values valid business data or upstream bugs? Verify before widening accepted_values.
4. Fix on a branch + add a test (prefer unit test) + PR with explanation. Root cause not found → findings doc with what was checked and next steps. [dbt-labs]
5. Operational siblings [arz troubleshooting]: DAG timeout → resources, then incremental loads, then raise execution_timeout - in that order. Spark OOM → executor memory / shuffle partitions / memory.fraction. Kafka lag rising → partitions + consumer parallelism. Duplicates → row_number dedup in the incremental.

## Hard numbers (source-backed defaults)
| Default | Value | Source |
|---|---|---|
| Airflow retries / delay / backoff cap | 3 / 5 min / 1 h | [wsh] |
| Sensor poke / timeout | 5 min / 2 h, mode=reschedule | [wsh] |
| Source freshness, daily batch | warn 12 h / error 24 h | [wsh] |
| Pipeline availability target | 99.9% | [volt] |
| Table-vs-incremental threshold | ~10M rows | [alt] |
| Late-data lookback window | 3 days, tune per source | [alt][wsh] |
| Refactor impact tiers | 1-5 / 6-15 / 16+ downstream | [dbt-labs] |
| CTE extraction threshold | ~50 lines | [alt] |
| Discovery sample | 50 rows + grain/null/orphan profile | [dbt-labs] |

## Standing gotchas
- **Watermark-only incrementals miss late data AND defeat pruning** - pair static `dateadd` bound with the `max()` subquery. [alt]
- **`on_schema_change` defaults to `ignore`** - new source columns silently vanish from incrementals. [alt]
- **Duplicate merge keys corrupt incrementals** - dedup CTE before merge. [alt][arz]
- **`dbt show` + trailing LIMIT = syntax error** (it appends its own); limits go inside CTEs. [dbt-labs]
- **`--empty` wipes data** - schema scaffolding only. [dbt-labs]
- **Don't guess accepted_values** - read the actual values during discovery; guessed enums fail on day one. [dbt-labs]
- **Fan-out joins inflate row counts silently** - composite-key unique test at every grain change. [dbt-labs; carried v0.5]
- **Streaming watermarks drop late events silently** - DLQ or batch reconciliation, never nothing. [arz]
- **Timezones**: store UTC, convert at display. **NULL sort order differs per warehouse** (Snowflake last, Postgres first). [carried v0.5]
- **dbt snapshots need a verified unique key** - dup keys corrupt history. [carried v0.5]
- **Reverse ETL can overwrite good CRM data with bad warehouse data** - validate before sync. [carried v0.5]
- **Incremental counts drifting from full-refresh counts** = drift; schedule the periodic full refresh. [alt]

## Red flags - STOP if about to
- Write SQL without checking column names; modify a model without reading its YAML; skip `dbt show` validation. [dbt-labs]
- Create a new model where a column addition would do. [dbt-labs]
- Refactor without the downstream list in hand. [alt]
- Make a test pass without a root cause. [dbt-labs]
- Run unselected `dbt build` on a big project. [dbt-labs]
- Trust incremental logic never verified against `--full-refresh`. [alt]
- Ship a pipeline with no freshness block, no failure callback, or no backfill plan. [wsh]
- Run DDL directly against the warehouse instead of through dbt. [dbt-labs]

## Boundaries (what this employee does NOT do)
- SQL business analysis, dashboards, metric reading → **data-analyst** (engineer owns the dbt models that analyst ad-hoc SQL gets promoted into).
- Experiment design, stats methodology, forecasting → **data-scientist** (engineer builds their feature tables and instrumentation pipelines).
- OLTP schema design, index tuning, replication ops → **database-administrator** (engineer coordinates CDC slots/publications with them).
- Cloud account/network architecture → cloud-architect; production on-call/reliability → SRE.

## Discovery report template (file alongside models, no Jinja) [dbt-labs discovering-data]
- Overview: row count · grain ("one row per X per Y") · PK (verified unique).
- Column table: name · type · null % · notes (enum values, timezone, oddities).
- Data quality issues as checkboxes ("status has 15 'unknown' rows - clarify with stakeholder").
- Relationships with orphan counts ("user_id → users.id, 5 orphans").
- Recommended staging transformations (filter/map invalids, cast TZ, surrogate key if natural key unreliable).

## Command crib [wsh dbt-transformation-patterns; dbt-labs]
```bash
dbt build --select state:modified+      # changed models + downstream, run+test in DAG order
dbt run --select +fct_orders            # model and upstream
dbt ls --select model_name+ --output name | wc -l   # downstream count before refactor
dbt show --select stg_x --limit 10      # eyeball output (limit inside CTEs for --inline)
dbt build --select my_model --full-refresh          # incremental baseline / drift reset
dbt test --select source:*              # source freshness + source tests
dbt compile --select failing_model && dbt parse     # failure triage, code class
```
