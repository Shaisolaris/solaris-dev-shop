# M13 validation of G13 "Reconciled metrics from dirty CSV"

**Verdict: FAIL** (1 x P2, 5 x P3, 3 x P4, plus 1 test-strength finding).

The core engine holds on every check here: exact metrics and coverage on 20 single-dirt cases, 3 unseen seeded datasets, the join cases, composite grain, controls, invalid-input recovery, offline operation, 8-way concurrency with a concurrent reader, 1.14 M rows, the fresh caller and the full suite on four interpreters. This agrees with Muse's direct ACCEPT, which is prior evidence only.

The verdict is FAIL on one P2, in the area Muse could not run. With an `as_of` cutoff, a row whose `loaded_at` is missing is silently treated as on time. The run still exits 0 `reconciled` with no gap. A newer version that has no `loaded_at` can replace an on-time version and change the headline (USD 175.00 against 150.00), still with exit 0. That is an unflagged imputation of `loaded_at <= as_of`, which the acceptance ("no silent imputation") and the tool's own exit-0 meaning rule out. The fix is one line: name a gap. The positive control `oracle/proposed-fix.patch` passes 15/15.

**Self-validation note:** this is Grok self-validation of a Grok-built candidate, not independent review. The oracle was written for M13 from the contract and the doc; it does not read the builder's oracle, tests, or Muse's oracle. The final independent review stays pending.

## Subject (isolation)

| item | value |
|---|---|
| candidate | `7da20d4f315f27cc0c9ca6fd9221cc182ae8b4da` (parent `02ba9c5`), branch `review/grok-g13-csv-reconciliation` |
| isolation | read-only `git fetch origin <branch>`, then `git worktree add --detach <tmp> 7da20d4`. No clone, and no writes to week-grok's tree, index or branch (`raw/weekgrok-before.txt`, `raw/weekgrok-after.txt`) |
| manifest | `<D>/grok-output/G13/MANIFEST.sha256`: 21/21 OK, and the manifest file set equals the diff file set against 02ba9c5 (`raw/manifest-verify.txt`). Diffstat: 21 files, +2001/-4. This closes the open point in MUSE-REVIEW-direct.md, which noted Muse's checkout was not shown to match 7da20d4 |
| contracts | `<D>/G13.md`, `<D>/M13.md`; `employees/data/data-engineer/csv-reconciliation.md` |
| interpreters | 3.9.6, 3.11.16, 3.12.14 (main), 3.13.15 |
| network | every oracle run uses the socket/DNS guard `oracle/inject/sitecustomize.py`: 0 attempts. All data is synthetic |

## Acceptance items

| acceptance (G13/M13) | result | evidence |
|---|---|---|
| Correct exact metric | PASS | k2: 20 single-dirt cases plus a nullable-amount case; k4: 3 seeded unseen datasets with truth built before the dirt; k10: composite grain with `latest:int`; fresh caller matches a hand answer written before the run |
| Correct coverage | PASS | every bucket checked per case; `all_rows_accounted` in all cases; k7: `--rejects` names every excluded fact row with the right line numbers |
| Deterministic rerun | PASS within an interpreter; P3 across interpreters (N2); P4 on value spelling (N8) | k6: reruns under PYTHONHASHSEED, TZ and LC_ALL are byte-identical, and shuffled rows and dimension give numerically equal metrics and identical coverage; b01: 2000-row dataset gives identical bytes on 4 interpreters; b02: 6 timestamp spellings differ |
| No silent imputation | **FAIL** (N1) | k5b, b07 |
| No duplicate count | PASS (N3 is undercounting, not double counting) | exact copies (`100.0` vs `100.00`, `usd` vs `USD`), superseded versions, ties unresolved, a newer void cancels, a newer missing amount is not papered over |
| No join fan-out | PASS | k3: orphan, ambiguous, exact-copy, triple-copy and missing-key cases; segments always add back to the headline |
| No fictional warehouse execution | PASS | `execution` statement present; 0 network attempts (k11) |
| Clean control | PASS | k1: exit 0, naive equals reconciled |
| Unseen failure and safe recovery | PASS, with N4 and N5 as edge exceptions | k8: schema drift, duplicate key, NaN, unknown zone, `..`, absolute path, symlink, `--out` on an input and identical targets all exit 2, write nothing and keep the previous report; the fixed input rewrites the report |
| Controls | PASS | k9: match, sum mismatch, and a rejected row makes the control a mismatch |
| Scale (not run by Muse) | PASS functionally; P3 memory (N9) | k13: 22,826 rows exact in 0.3 s; b05: **1,139,602 rows (108 MB) exact in 17.0 s, peak RSS 1926 MB** |
| Concurrency (not run by Muse) | PASS | k12: 8 concurrent writers into one `--out` give the sequential bytes, a concurrent reader saw only whole reports (about 5000 reads), and no temp files are left; b06: 16 writers with 2 different inputs plus a reader, 18,188 reads, 0 torn |
| as_of with missing loaded_at (not run by Muse) | **FAIL** (N1) | k5b, b07 |
| Original 84 tests preserved | PASS | `raw/pyversions-matrix.txt`: G13 26 OK, original 84 OK and full 110 OK on 3.9.6, 3.11, 3.12 and 3.13 |
| Fresh caller | PASS | `raw/fresh-caller.txt`: `env -i`, new HOME, a `python3` shim, the doc's contract JSON used verbatim and only the 2 documented commands. The result matches the hand answer (USD 2049.00, EUR 15.25, 4 orders, exit 1, control mismatch, 6 rejects) |

## Findings

All repros are in `oracle/m13_finding_repros.sh`, with output in `raw/finding-repros.txt`. The base data is O1 USD 100.00, O2 USD 50.00 and O3 EUR 30.00, with as_of 2026-10-02T00:00Z.

**N1 (P2): with as_of, a missing `loaded_at` is treated as on time and the run reports clean.**
- O4 USD 4.00 with blank `loaded_at` gives `exit 0, status reconciled, gaps []`, USD 154.00. The only signal is the note "1 included rows have no loaded_at; lateness could not be judged for them".
- The `NULL` token gives the same result.
- When every row lacks `loaded_at`, the run exits 0 `reconciled`, so the as-of view is entirely unjudged.
- A newer version of O2 (USD 75.00) with blank `loaded_at` replaces the on-time version. Result: exit 0, USD 175.00, against 150.00 if that version arrived after the cutoff.

A caller that reads the exit code or `gaps` sees a clean as-of view. Fix: add a gap such as `loaded_at_unknown`, so the run exits 1, or exclude and count those rows. Positive control: `oracle/proposed-fix.patch` adds the gap; it passes the M13 oracle 15/15, the builder oracle 11/11 and the builder tests 26/26.

**N2 (P3): the same CSV gives different metrics on 3.9.6 and on 3.11+.** The doc says "Python 3.9+". Six `event_time` spellings are accepted on 3.11, 3.12 and 3.13 but rejected as `bad_timestamp` on 3.9.6: `.5Z`, `.1234567Z`, `+0000`, `+00`, `20260910T120000Z` and `2026-W37-4T12:00:00Z`. The result is exit 0 / USD 154.00 against exit 1 / USD 150.00. It is visible as a rejected row on 3.9, but the headline still depends on the runtime. Fix: accept one explicit grammar on every version, for example RFC 3339 only, or document 3.11+.

**N3 (P3): a re-delivered record that is identical except for `loaded_at` is treated as a conflicting tie and dropped.** O2 is delivered twice by two load batches with the same `updated_at`, which is a normal at-least-once load. Observed: USD 100.00 against a true 150.00, orders 2, `rows_unresolved 2`, exit 1 `unresolved_duplicates`. The gap is named, but the metric undercounts on the most common duplicate in real loads, because `loaded_at` is part of the exact-copy signature. Fix: leave `loaded_at_column` out of the content signature, and keep the earliest load.

**N4 (P3): a write failure after the checks leaves a partial output while reporting "invalid".** With `--rejects` in a writable folder and `--out` in a read-only folder, the result is exit 2 `{"error": "file error: Permission denied", "status": "invalid"}`, but `rejects.csv` has already been written. The doc says exit 2 means "nothing written". Fix: stage both files and then rename both, or remove the first file on failure.

**N5 (P3): a deeply nested contract crashes.** A contract nested 100,000 levels deep gives an uncaught `RecursionError` traceback and exit 1, which is the "reconciled_with_gaps" code, not 2 for invalid. A script that branches on exit codes would read a crash as a reconcile with gaps. Fix: catch `RecursionError` with the JSON errors.

**N6 (P4): ambiguous or nonexistent local times are resolved silently.** With `timezone: America/Los_Angeles`, the naive `2026-11-01 01:30:00` happens twice. It is taken as the first occurrence (08:30Z), so it falls inside a window ending at 09:00Z; the second occurrence (09:30Z) would fall outside. The nonexistent `2026-03-08 02:30:00` is accepted. Both get only the generic "timestamps without an offset" note. Fix: reject the time or flag it as ambiguous.

**N7 (P4): Unicode digits are accepted in `int` columns.** The pattern `\d` matches non-ASCII digits. `\u0663` (ARABIC-INDIC DIGIT THREE) in a `latest:rev` column parses as 3 and wins the version: USD 170.00, nothing rejected. Fix: use `[0-9]`, as the decimal pattern already does.

**N8 (P4): the spelling of a total depends on row order.** For exact copies `100.00` and `100.000`, the first one by line is kept, and its decimal places carry into the sum: `150.00` in one order and `150.000` in the other. The values are numerically equal. This contradicts the handback's claim that shuffled rows give the same metrics, as a string compare sees it. Fix: choose the representative independently of order (done in the positive control), or quantize totals.

**N9 (P3, operational): memory is about 18 times the file size.** 1,139,602 rows (108 MB) peak at 1926 MB RSS (17.9x) in 17.0 s. The documented limit is "5 million rows and 512 MiB per file, held in memory". At the same ratio that is roughly 9 GB, which is an extrapolation, not a measurement (deliberately not run on the owner's Mac). Fix: document a memory figure, or lower the limit to something that fits a typical runner.

**N10 (test strength, P3): the builder's oracle lets 12 of 23 mutants through, and the builder's tests let 7 through.**
- Survive both: `control_ignores_rejects` (contrary to the handback's "control always matches killed"), `count_distinct_as_count`, `late_boundary_inclusive`, `no_atomic_tmp`, `null_as_zero`, `window_end_inclusive` and `window_start_exclusive`.
- `symlink_allowed` is an equivalent mutant: a second regular-file check and `O_NOFOLLOW` still refuse the symlink.
- `raw/builder-oracle-vs-teeth.txt`, `raw/builder-tests-vs-mutants.txt`.

Behaviours checked and confirmed correct (not findings):
- A naive `loaded_at` is read in the contract zone against as_of (b08).
- A date-only window is read in the contract zone (b12).
- A row loaded exactly at as_of is included, and lateness uses `loaded_at` as an instant (k5a).
- A late newer version leaves the older one in place.
- The header alias `Order ID` from the doc example is honoured (fresh caller).
- `--out` and `--rejects` are checked before any write in the normal case.

## Oracle teeth (`oracle/m13_oracle.py` v2, checks k1 to k13 with k5a/k5b and k6/k6b)

| subject | M13 oracle | builder oracle | builder tests |
|---|---|---|---|
| candidate 7da20d4 | 13/15 (k5b = N1, k6b = N8) | 11/11 | 26 OK |
| positive control (proposed-fix.patch) | **15/15** | 11/11 | 26 OK |
| stub no-op (fake clean report) | 3/15 REJECT | 0/11 REJECT | n/a |
| stub naive sum | 3/15 REJECT | 0/11 REJECT | n/a |
| builder noop_stub | 2/15 REJECT | 0/11 REJECT | n/a |
| builder naive_stub | 2/15 REJECT | 0/11 REJECT | n/a |
| 23 mutants | **22/23 caught by a check the candidate passes**; 1 equivalent (symlink_allowed) | 11/23 caught | 16/23 caught |

Per-mutant check that catches it in the M13 oracle:

| check | mutants caught |
|---|---|
| k2 | count_distinct_as_count, dedup_after_status, digits_unbounded, naive_as_utc, null_as_zero, null_gap_dropped, thousands_loose, tie_picks_first, window_end_inclusive, window_start_exclusive, late_boundary_inclusive, oldest_wins, status_ignored, uppercase_ignored, no_exact_collapse, decimal_not_normalized, late_ignored |
| k3 | ambiguous_as_unmatched, dim_dupes_fan_out |
| k5a | late_boundary_inclusive, late_ignored |
| k8 | out_over_input |
| k9 | control_ignores_rejects |
| k12 | no_atomic_tmp |

The M13 oracle gives the same result under 3.9.6, 3.11, 3.12 and 3.13 (`raw/oracle-cross-interpreter.txt`).

## Rejected and superseded runs (kept)

- `raw/oracle-candidate-run1.txt`: k6 compared value strings after a shuffle. The difference is real but only in spelling, so v2 splits it into k6 (numeric) and k6b (spelling), and the spelling issue is reported as N8.
- `raw/*-v1-superseded.txt` (teeth v1):
  - Mutant `out_over_input` had a paren error and failed everything, so it was not a fair mutant.
  - `null_as_zero` and `no_atomic_tmp` survived because there was no count over a nullable column and no concurrent reader. v2 fixes the mutant and adds both checks.
- `raw/pyversions-matrix-run1-harness-error.txt`: the original tests were invoked as `tests.<module>`, which breaks their sibling imports. The rerun uses `discover -s tests`.

## Prior evidence: Muse direct ACCEPT

Muse reported 26/26 on its own oracle, 110/110 on the suite, and could not run scale, concurrency or as_of with a missing loaded_at. This run confirms its core results at the exact manifest-verified SHA, runs all three missing areas, and finds N1 in the third. Muse's oracle and logs live in Muse's workspace and were not re-executed.

## Limitations

- The data is synthetic. Real exports (Excel CSVs, other encodings, very wide files) were not tried beyond UTF-8 with a BOM and CRLF in the builder fixture.
- The scale run went to 1.14 M rows; the 5 M row limit is extrapolated and was not run.
- Concurrency was tested within one host on APFS. Network filesystems were not tested.
- The DST cases cover America/Los_Angeles only.

## Layout

`oracle/` holds m13_oracle.py, m13_adversarial.py, m13_finding_repros.{py,sh}, make_mutants.py, run_teeth.sh, proposed-fix.patch, stubs/ and inject/sitecustomize.py. `raw/` holds every log, including the rejected runs. `MANIFEST.sha256` covers every file. Private paths appear as `<D>` and `<W>`.
