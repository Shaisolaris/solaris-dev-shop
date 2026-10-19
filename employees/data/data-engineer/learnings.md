# Data Engineer - Learnings (Pending)

## Pending observations
- **2026-04-24 - Clean build**: Idempotency + SLA + tests are non-negotiable trio for any pipeline. Codified.
- **2026-04-24 - Clean build**: dbt is the modern default for transformation; all sources converge. Airflow/Dagster/Prefect for orchestration, dbt for transforms.
- **2026-10-18 - G13 CSV reconciliation**: on a 20-row synthetic drop the naive SUM over every row was 3135.00 USD against a reconciled 1425.50, and an inner join on a customer file with one duplicated and one conflicting key gave 3090.00 USD and 653.00 EUR against 155.00. Lesson: version on the grain before filtering on status or window (a newer void version must cancel the order), and give orphan and ambiguous keys their own segment instead of dropping or multiplying them.
- **2026-10-18 - G13 r2 (M13 Grok self-validation on 7da20d4)**: with an as_of cutoff a row with no loaded_at was silently treated as on time (and a newer such version could change the headline with exit 0); fromisoformat accepted different timestamps on 3.9 and 3.11+; a re-delivery differing only in loaded_at was treated as a conflicting version; --rejects could be written when --out failed; DST wall times were guessed; \d accepted non-ASCII digits; peak memory was about 18x the file. Lesson: an unknown needed for a rule is a named gap, never a default; own the parser grammar instead of the runtime's; load metadata is not record content; stage every output before renaming any; measure memory and set the limit from the measurement.
- **2026-10-18 - G13 r3 (M13 r2 Grok self-validation on 75a4e2b)**: making one timestamp grammar for every Python by taking 3.9's strict subset refused PostgreSQL's default `timestamptz` text (`+00`), 7-digit SQL Server fractions, `-0700` and nanoseconds, so a standard export lost every timed row; and refusing nonexistent local times also refused date-only days in zones that change clocks at midnight. Lesson: when unifying parsers, unify on the widest safe grammar written out by hand, test it with real export spellings to the microsecond, and treat a date as a day, not as a midnight wall time.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
## Sources

- Upstream: dlt-hub/dlt (Apache-2.0 (permissive, clean)); dagster-io/dagster (Apache-2.0 (permissive)); apache/iceberg (Apache-2.0 (permissive)); sodadata/soda-core (AGPL-3.0 - FLAGGED (copyleft network license; methodology + self-host note only, never); great-expectations/great_expectations (Apache-2.0 (permissive))
- What was used: methodology absorbed: dlt-hub/dlt; methodology only: dagster-io/dagster, apache/iceberg, sodadata/soda-core, great-expectations/great_expectations; connected as external reference: great-expectations/great_expectations
- License notes: sodadata/soda-core: AGPL-3.0 - FLAGGED (copyleft network license; methodology + self-host note only, never
