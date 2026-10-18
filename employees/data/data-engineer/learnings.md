# Data Engineer - Learnings (Pending)

## Pending observations
- **2026-04-24 - Clean build**: Idempotency + SLA + tests are non-negotiable trio for any pipeline. Codified.
- **2026-04-24 - Clean build**: dbt is the modern default for transformation; all sources converge. Airflow/Dagster/Prefect for orchestration, dbt for transforms.
- **2026-10-18 - G13 CSV reconciliation**: on a 20-row synthetic drop the naive SUM over every row was 3135.00 USD against a reconciled 1425.50, and an inner join on a customer file with one duplicated and one conflicting key gave 3090.00 USD and 653.00 EUR against 155.00. Lesson: version on the grain before filtering on status or window (a newer void version must cancel the order), and give orphan and ambiguous keys their own segment instead of dropping or multiplying them.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
## Sources

- Upstream: dlt-hub/dlt (Apache-2.0 (permissive, clean)); dagster-io/dagster (Apache-2.0 (permissive)); apache/iceberg (Apache-2.0 (permissive)); sodadata/soda-core (AGPL-3.0 - FLAGGED (copyleft network license; methodology + self-host note only, never); great-expectations/great_expectations (Apache-2.0 (permissive))
- What was used: methodology absorbed: dlt-hub/dlt; methodology only: dagster-io/dagster, apache/iceberg, sodadata/soda-core, great-expectations/great_expectations; connected as external reference: great-expectations/great_expectations
- License notes: sodadata/soda-core: AGPL-3.0 - FLAGGED (copyleft network license; methodology + self-host note only, never
