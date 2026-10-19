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
- Types: `str`, `decimal` (exact, at most 20 integer and 10 fractional digits, strict thousands grouping), `int`, `timestamp`. Numbers use ASCII digits 0-9 only; other scripts' digits are rejected.
- `timestamp` has one grammar on every Python from 3.9 up, parsed by the tool itself: `YYYY-MM-DD`, or `YYYY-MM-DD` then `T` or a space, `HH:MM`, optional `:SS` and up to 9 fractional digits, and an optional `Z` or offset `+HH:MM`, `+HHMM` or `+HH` (or `-`), which may follow one space. That covers PostgreSQL `timestamptz` text (`2026-09-12 12:00:00+00`, `-07`), SQL Server `datetime2(7)` and `datetimeoffset(7)` (`.1234567 +00:00`), ISO basic offsets (`-0700`) and Go/Kubernetes nanoseconds (`.123456789Z`). Fraction digits past the sixth are dropped, never rounded (Python keeps microseconds). Forms such as `20260910T120000Z`, week dates, 10+ fractional digits, `+0` or `+000`, offset minutes over 59, offsets of 24 hours or more and a space before `Z` are rejected (`bad_timestamp`) on every version. Contract times (`window`, `as_of`) use the same grammar.
- A time without an offset is read in `timezone`. If that wall time happens twice (DST fall-back) or never (spring-forward) in the zone, the row is rejected as `ambiguous_local_time` or `nonexistent_local_time` and a note says so; a contract time like that is invalid. The tool never guesses which instant was meant.
- A date-only value (`2026-09-06`) names a calendar day and is read as that day's first instant, even in zones whose clocks change at midnight: after a midnight spring-forward that is the end of the gap (01:00 local in `America/Santiago` on 2026-09-06), after a midnight fall-back the first of the two midnights (`America/Havana` on 2026-11-01). A clock time inside the gap or the repeat (`2026-09-06 00:30`) is still refused.
- Null tokens default to empty, `NULL`, `null`. Header names match case-insensitively, plus any `header_aliases`.
- `duplicate_policy`: `latest:<column>` keeps the version with the highest value; a tie or a missing value in that column leaves the key unresolved. `reject` (the default) leaves every key with differing versions unresolved. Exact copies are always collapsed.
- `loaded_at_column` is not part of a record's content: a re-delivery that differs only in its load time is an exact copy (at-least-once loads), and the earliest load is kept. Which copy is kept never depends on row order, so totals are spelled the same however the file is sorted.
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
1. Parse: `rejected` (`field_count`, `bad_decimal`, `bad_int`, `bad_timestamp`, `ambiguous_local_time`, `nonexistent_local_time`, `malformed_csv`, `field_too_long`) or a grain column missing.
2. With `as_of`: `loaded_at_unknown` (no load time, so it cannot be judged on time; excluded and named as a gap, never assumed on time, and it cannot win a duplicate resolution), then `late_after_as_of`: loaded after the cutoff, so not part of this view (a later run with a later as-of picks it up).
3. Duplicates on the grain: `exact_copies`, `superseded_versions`, `rows_unresolved` / `keys_unresolved`. This runs before status and window, so a newer `void` version cancels the order and a newer version with a missing amount is not papered over by an older one.
4. The surviving version: `missing_required`, `excluded_status`, `outside_window`.
5. Join: `matched`, `unmatched` (orphan key), `ambiguous` (the dimension has conflicting rows for the key), `fact_key_missing`. Unmatched and ambiguous rows keep their amount under the segment `(unmatched)` / `(ambiguous)`, so segment totals always add up to the headline total. A join never multiplies a row.
6. Metrics: a null in the metric column is skipped and counted in `null_values_skipped`, never treated as 0.

## Output
- Exit 0 `reconciled`; exit 1 `reconciled_with_gaps` with each gap named (`rejected_rows`, `missing_required`, `unresolved_duplicates`, `loaded_at_unknown`, `late_rows`, `unmatched_or_missing_join_key`, `ambiguous_dimension_key`, `control_mismatch`, `null_metric_values`); exit 2 `invalid` (bad contract, JSON nested too deeply, schema drift, unsafe path, an output that cannot be written), and nothing is written.
- `coverage`: rows read, included, every bucket, `accounted == rows_read`, and `quality_coverage` (included / rows that were wanted but could not be used for quality reasons).
- `naive_comparison`: the sum over every parsed row and after a plain inner join, labelled as not a result, so the inflation is visible.
- `inputs` with sha256 of every file, `execution` and `imputation` statements.
- `--out` and `--rejects` are written together or not at all: every target is checked, both are staged as temp files, then renamed; if a rename fails, a target already replaced is put back. A replaced file is a new file, so a reader never sees a partial report. They may not point at an input. Same files and contract give the same bytes on every supported Python.

## Worked example
`examples/capabilities/G13/fixtures/september/` (synthetic): 20 data rows. Reconciled revenue
USD 1425.50 and EUR 155.00 over 8 orders; naive sum USD 3135.00 and EUR 326.50; naive inner join
USD 3090.00 and EUR 653.00. The arithmetic is in `examples/capabilities/G13/README.md`.

## Limits
- Times keep microseconds: two times that differ only past the sixth fraction digit compare as equal.
- One fact file and at most one dimension per contract; up to 2,000,000 rows and 256 MiB per file. Rows are held in memory because duplicates need every version of a grain. Measured on Python 3.12 (macOS arm64): 1,139,602 rows (108 MB) took 22 s and peaked at 1.16 GB RSS, about 1 KB per row or 11x the file size. Plan for about 2-3 GB at the limits; larger drops should be split by date first.
- It does not fix data. Rejected and unresolved rows go back to the source owner with their line numbers (`--rejects`).
- Currency conversion, imputation and allocation of unmatched amounts are business decisions for the analyst, made visibly downstream.
