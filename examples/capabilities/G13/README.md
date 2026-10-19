# G13: reconciled metrics from dirty CSV

Tool: `employees/data/data-engineer/csv_reconcile.py` (reference: `employees/data/data-engineer/csv-reconciliation.md`).
All data here is synthetic. No owner, client or production data is used.

## Files
| Path | What it is |
|---|---|
| `fixtures/september/` | dirty drop: BOM, CRLF, alias and padded headers, exact copies, an older version, a conflicting tie, a missing amount, a malformed amount, a short row, late loads, a test row, an out-of-window row, an orphan and an ambiguous customer, naive local timestamps, a source control total |
| `fixtures/clean/` | clean control: naive and reconciled totals agree, exit 0 |
| `reconcile_oracle.py` | own oracle: builds ground truth first, then injects dirt with known effects; 14 checks including scale (about 248k rows) and 4 parallel runs; o12 (r2) window and as_of boundaries, null-aware count/min, controls with a rejected row and replace-not-rewrite output; o13 (r2) the M13 findings: missing loaded_at under as_of, one time grammar, re-delivery, both-or-neither outputs, deep JSON, DST, ASCII digits and order-independent spelling; o14 (r3) the M13 r2 findings: PostgreSQL `+00`/`-07`, 7 and 9 digit fractions, `-0700`, SQL Server spellings read to the exact microsecond (window end one microsecond either side), truncation not rounding, and date-only days on a midnight DST change in Santiago and Havana |
| `noop_stub.py` | claims success without reading anything; must fail the oracle |
| `naive_stub.py` | sums every row, 0-fills missing amounts, fan-out inner join, writes before validating; must fail the oracle |

## Run
```
python3 employees/data/data-engineer/csv_reconcile.py reconcile examples/capabilities/G13/fixtures/september/contract.json
python3 examples/capabilities/G13/reconcile_oracle.py --tool "python3 employees/data/data-engineer/csv_reconcile.py"
python3 -m unittest tests.test_g13_capability
```

## September fixture, worked by hand
Window is September 2026 in America/Los_Angeles (07:00Z Sep 1 to 07:00Z Oct 1); as-of 2026-10-02T00:00Z.
Line numbers count the header as line 1.

| Line | Row | Bucket | Why |
|---|---|---|---|
| 2 | O1 C1 100.00 usd | included | |
| 3 | O2 C2 "1,250.00" USD, naive 09:00 local | included | thousands separator; naive time read as local |
| 4 | O3 C3 80.00 EUR, updated Sep 10 | superseded | line 5 is newer |
| 5 | O3 C3 85.00 EUR, updated Sep 11 | included | |
| 6 | copy of line 2 | exact copy | |
| 7 | O4 C1 empty amount | missing required | not 0-filled |
| 8 | O5 C2 12.3x | rejected bad_decimal | |
| 9 | O6 C1 40.00 test | excluded status | |
| 10 | O7 C2 60.00 at 03:00Z Sep 1 | outside window | that is Aug 31 locally |
| 11 | O8 C9 30.00 USD | included, unmatched | C9 not in customers |
| 12 | O9 C4 70.00 EUR | included, ambiguous | C4 is north and south |
| 13 | O10 C1 500.00, loaded Oct 3 | late | |
| 14 | O2 999.00, loaded Oct 2 13:00Z | late | newer version, but after as-of |
| 15 | O11 with 3 fields | rejected field_count | |
| 16 | O12 C2 20.00, naive 22:00 Sep 30 local | included | 05:00Z Oct 1, still September locally |
| 17 | O13 no customer 15.00 usd | included, key missing | segment (unmatched) |
| 18 | O14 C3 45.50 EUR, updated 10:00Z | unresolved | same updated_at as line 19 |
| 19 | O14 C3 46.00 EUR, updated 10:00Z | unresolved | |
| 20 | O15 C1 10.5 usd | included | |
| 21 | O15 C1 10.50 USD | exact copy | same value after normalizing case and decimals |

Accounting: 2 rejected + 1 missing + 2 late + 1 status + 1 window + 2 exact + 1 superseded + 2 unresolved + 8 included = 20.

- Revenue USD = 100.00 + 1250.00 + 30.00 + 20.00 + 15.00 + 10.5 = **1425.50**; EUR = 85.00 + 70.00 = **155.00**; orders = **8**.
- By region: east USD 1250.00 + 20.00 = 1270.00; west USD 100.00 + 10.5 = 110.50; west EUR 85.00; (unmatched) USD 30.00 + 15.00 = 45.00; (ambiguous) EUR 70.00. Sum 1580.50 = 1425.50 + 155.00.
- Naive sum over every parsed row (17 rows with an amount): USD 3135.00, EUR 326.50.
- Naive inner join (C3 twice, C4 twice, C9 and empty key dropped): USD 3090.00, EUR 653.00.
- Control file says 20 rows and 3483.80 (it includes the 12.30 and 10.00 the source meant). Parsed sum is 3461.50 with 2 unparsed rows, so the control does not match and the run is `reconciled_with_gaps` (exit 1).
