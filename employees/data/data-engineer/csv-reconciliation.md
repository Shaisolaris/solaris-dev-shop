# CSV reconciliation (W6): exact metrics from a dirty file drop

`csv_reconcile.py` turns CSV files plus a contract into a metric you can defend: every row is
accounted for in exactly one bucket, nothing is imputed, nothing is counted twice, and the
report says it ran locally on files. Python 3.9+ standard library only; no network, no database.

## Contract (`solaris.csv-reconcile/1`)
```json
{
  "schema": "solaris.csv-reconcile/1",
  "timezone": "America/Los_Angeles",
  "facts": {
    "file": "orders.csv",
    "grain": ["order_id"],
    "columns": {"order_id": "str", "customer_id": "str", "amount": "decimal", "currency": "str",
                "status": "str", "event_time": "timestamp", "loaded_at": "timestamp", "updated_at": "timestamp"},
    "header_aliases": {"Order ID": "order_id"},
    "required": ["amount", "currency", "event_time"],
    "uppercase": ["currency"],
    "thousands_separator": ",",
    "duplicate_policy": "latest:updated_at",
    "status_column": "status", "exclude_status": ["test", "void"],
    "loaded_at_column": "loaded_at"
  },
  "dimension": {"file": "customers.csv", "key": "customer_id", "attributes": ["region"],
                "columns": {"customer_id": "str", "region": "str"}, "duplicate_policy": "reject"},
  "window": {"column": "event_time", "start": "2026-09-01T00:00:00-07:00", "end": "2026-10-01T00:00:00-07:00"},
  "as_of": "2026-10-02T00:00:00Z",
  "metrics": [{"name": "revenue", "agg": "sum", "column": "amount", "by": ["currency"]},
              {"name": "orders", "agg": "count_distinct", "column": "order_id"}],
  "controls": {"file": "control.csv", "sum_column": "amount"}
}
```
- Files are names relative to the contract's folder. Absolute paths, `..` escapes and symlinks are refused.
- `timezone` is required: it is the zone used for timestamps without an offset, and the report says how many there were.
- Types: `str`, `decimal` (exact, at most 20 integer and 10 fractional digits, strict thousands grouping), `int`, `timestamp` (ISO 8601).
- Null tokens default to empty, `NULL`, `null`. Header names match case-insensitively, plus any `header_aliases`.
- `duplicate_policy`: `latest:<column>` keeps the version with the highest value; a tie or a missing value in that column leaves the key unresolved. `reject` (the default) leaves every key with differing versions unresolved. Exact copies are always collapsed.
- `controls` is a CSV with `file,rows,sum` from the source system. It matches only if the rows agree, the sum of parsed values agrees and no row was rejected.

## Commands
Put the contract next to the CSV files and run, from the repository root:
```bash
T=employees/data/data-engineer/csv_reconcile.py
python3 $T reconcile contract.json
python3 $T reconcile contract.json --json --out report.json --rejects rejects.csv
```
The first prints the readable summary; the second writes the JSON report and one line per excluded row.
A composite grain (for example `["invoice_id", "line_no"]`) and `latest:<int column>` work the same way.

## Order of operations (each row lands in exactly one bucket)
1. Parse: `rejected` (`field_count`, `bad_decimal`, `bad_int`, `bad_timestamp`, `malformed_csv`, `field_too_long`) or a grain column missing.
2. `late_after_as_of`: loaded after the as-of cutoff, so not part of this view (a later run with a later as-of picks it up).
3. Duplicates on the grain: `exact_copies`, `superseded_versions`, `rows_unresolved` / `keys_unresolved`. This runs before status and window, so a newer `void` version cancels the order and a newer version with a missing amount is not papered over by an older one.
4. The surviving version: `missing_required`, `excluded_status`, `outside_window`.
5. Join: `matched`, `unmatched` (orphan key), `ambiguous` (the dimension has conflicting rows for the key), `fact_key_missing`. Unmatched and ambiguous rows keep their amount under the segment `(unmatched)` / `(ambiguous)`, so segment totals always add up to the headline total. A join never multiplies a row.
6. Metrics: a null in the metric column is skipped and counted in `null_values_skipped`, never treated as 0.

## Output
- Exit 0 `reconciled`; exit 1 `reconciled_with_gaps` with each gap named (`rejected_rows`, `missing_required`, `unresolved_duplicates`, `late_rows`, `unmatched_or_missing_join_key`, `ambiguous_dimension_key`, `control_mismatch`, `null_metric_values`); exit 2 `invalid` (bad contract, schema drift, unsafe path), and nothing is written.
- `coverage`: rows read, included, every bucket, `accounted == rows_read`, and `quality_coverage` (included / rows that were wanted but could not be used for quality reasons).
- `naive_comparison`: the sum over every parsed row and after a plain inner join, labelled as not a result, so the inflation is visible.
- `inputs` with sha256 of every file, `execution` and `imputation` statements.
- `--out` and `--rejects` are written atomically after every target is checked; they may not point at an input. Same files and contract give the same bytes.

## Worked example
`examples/capabilities/G13/fixtures/september/` (synthetic): 20 data rows. Reconciled revenue
USD 1425.50 and EUR 155.00 over 8 orders; naive sum USD 3135.00 and EUR 326.50; naive inner join
USD 3090.00 and EUR 653.00. The arithmetic is in `examples/capabilities/G13/README.md`.

## Limits
- One fact file and at most one dimension per contract; up to 5 million rows and 512 MiB per file, held in memory.
- It does not fix data. Rejected and unresolved rows go back to the source owner with their line numbers (`--rejects`).
- Currency conversion, imputation and allocation of unmatched amounts are business decisions for the analyst, made visibly downstream.
