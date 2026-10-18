# M13 r2: re-validation of G13 r2 "Reconciled metrics from dirty CSV"

**Kind:** Grok self-validation (same bot as the G13 builder). Not independent review. It reruns the M13 method on the reworked candidate:
- the M13 oracle, adversarial suite and finding repros, unchanged from M13 (copied to `oracle/m13/`);
- a new r2 regression script (`oracle/m13r2_regressions.py`) comparing r2 with r1;
- 31 mutants: the 23 M13 mutants plus 8 fix-revert mutants (`oracle/make_mutants_r2.py`);
- a new fresh caller with its own data and a hand answer written before the run.

An independent reviewer is still required by the QA2 contract. Muse's direct ACCEPT applied to 7da20d4 only.

**Verdict: PASS** against candidate commit `75a4e2bd05b66a9455b074879966e46f960f4d4b` (branch `review/grok-g13-csv-reconciliation`, subject "G13 rework r2: M13 findings N1-N10 (review only)", parent `7da20d4`, base `02ba9c571b10ad1dba792d2ac5534bcad3171e67`). The candidate manifest (`<D>/grok-output/G13/MANIFEST.sha256`, r2) verified 21/21, and its file set equals the diff `02ba9c5..75a4e2b` (`raw/manifest-verify.txt`).

What the rework got right:
- N1 to N8 are fixed. Every M13 finding repro passes (`raw/finding-repros.txt`), and the M13 adversarial suite is 12/12 OK.
- N9 is addressed by measured, documented and lowered limits (10.7x the file). Rows are still held in memory, which the doc now says.
- N10 is fixed. On every non-equivalent mutant, the builder oracle kills 29/29 and the builder tests 29/29.
- The M13 oracle passes 15/15 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15.
- The suite passes (35 G13, 84 original, 119 total) on all four interpreters.
- Bytes are identical across interpreters.
- A fresh caller matches its hand answer on 3.9.6 and 3.12.14.

There is no P1 or P2 finding, so no proposed-fix patch is included. The other findings:
- 1 P3 regression: the new single timestamp grammar refuses PostgreSQL's default `timestamptz` text and other common export spellings that r1 accepted on 3.11+. The refusal is loud.
- 1 P4: date-only values on a midnight DST change are refused.

Runs were on host macOS (arm64) on 2026-10-18 between 15:43 and 16:00 PT. Python 3.12.14 was used unless stated.

## Isolation
- The candidate was fetched with `git fetch origin review/grok-g13-csv-reconciliation` (FETCH_HEAD `75a4e2bd...`, parent `7da20d4`, `raw/fetch.txt`). It was checked out detached at `/tmp/m13r2-eval` (`raw/worktree-add.txt`). The r1 tool was extracted to `/tmp/m13r2-old/csv_reconcile.py` with `git show`, for comparison only.
- Mutants were written to `/tmp/m13r2-mutants`. Builder-test runs used `/tmp` copies, and the fresh caller ran in a `/tmp` copy.
- The candidate worktree had 0 status lines before and after the suite runs (`raw/pyversions-matrix.txt`).
- Nothing was written to the week-grok working tree. Its branch, HEAD, index hash and status hash were recorded before (`raw/weekgrok-before.txt`) and after (`raw/weekgrok-after.txt`).
- No candidate file was modified.
- Every candidate run goes through the M13 offline guard (`oracle/m13/inject/sitecustomize.py`). It logged 0 network attempts.

## M13 findings, rechecked
| M13 finding | r2 status | Evidence |
|---|---|---|
| N1 (P2) missing `loaded_at` under as_of treated as on time | **Fixed** | Repro N1 and oracle k5b. Blank and `NULL` give exit 1 with gap `loaded_at_unknown`, USD 150.00. A newer version with no `loaded_at` no longer replaces the on-time one (`raw/regressions-*.txt` RN: r1 USD 175.00 exit 0, r2 USD 150.00 exit 1). Without as_of nothing changes. |
| N2 (P3) metrics differ on 3.9 vs 3.11+ | **Fixed** (consistency) | b02: 0 forms disagree across 4 interpreters. b01: identical bytes. The price is RT below. |
| N3 (P3) re-delivery identical but `loaded_at` dropped as a tie | **Fixed** | Repro N3 and b09: USD 150.00, 1 exact copy, exit 0. RN: the earliest load is kept; a late first copy plus an on-time second gives `late_rows` and the right metric. |
| N4 (P3) partial write while reporting invalid | **Fixed** | Repro N4 and b11: `--out` in a read-only folder gives exit 2, `rejects.csv` not written, no temp or `.keep` files. RW: r1 wrote `rejects.csv`, r2 does not. b06: 16 writers plus a reader, 21533 reads, 0 partial. |
| N5 (P3) deep contract traceback | **Fixed** | Repro N5 and b10: exit 2, no traceback. |
| N6 (P4) ambiguous or nonexistent local times guessed | **Fixed** | Repro N6 and b03: rejected as `ambiguous_local_time` or `nonexistent_local_time` with a note. b03's printed text "(counted as the first occurrence...)" is fixed M13 wording, not the result. See RD for the strictness side. |
| N7 (P4) Unicode digits in `int` | **Fixed** | Repro N7 and b04: `bad_int`, USD 150.00. |
| N8 (P4) total spelling depends on row order | **Fixed** | Repro N8 and oracle k6b: `150.00` in both orders. |
| N9 (P3) memory about 18x the file | **Addressed by documentation** | b05: 1,139,602 rows (108 MB) exact in 23.1 s, peak RSS 1156 MB (10.7x), down from 1926 MB. Limits lowered to 2,000,000 rows and 256 MiB. At 10.7x, 256 MiB is about 2.7 GB, which matches the doc's "2-3 GB". b05's printed extrapolation uses the old 512 MiB limit (fixed M13 wording). |
| N10 (P3) builder oracle and tests let mutants through | **Fixed** | Builder oracle 29/29 and builder tests 29/29 on non-equivalent mutants (teeth below). |

## Findings
### RT (P3, regression): common export timestamp spellings are now refused on every Python
Repro: `PY oracle/m13r2_regressions.py PY T/employees/data/data-engineer/csv_reconcile.py OLD/csv_reconcile.py`, section RT (`raw/regressions-3.12.14.txt`). Base: O1 USD 100.00 and O2 USD 50.00, plus O3 USD 4.00 with the spelling below. UTC contract, September window.

| Source and spelling | r1 on 3.12 | r2 (every Python) |
|---|---|---|
| PostgreSQL `timestamptz` text `2026-09-12 12:00:00+00` | exit 0, USD 154.00 | exit 1, USD 150.00, `bad_timestamp` |
| PostgreSQL with fraction `...12:00:00.123456+00` | exit 0, 154.00 | exit 1, 150.00, rejected |
| PostgreSQL `-07` hour offset | exit 0, 154.00 | exit 1, 150.00, rejected |
| SQL Server `datetime2(7)` `...12:00:00.1234567` | exit 0, 154.00 | exit 1, 150.00, rejected |
| SQL Server `datetimeoffset(7)` `....1234567 +00:00` | exit 0, 154.00 | exit 1, 150.00, rejected |
| ISO basic offset `-0700` | exit 0, 154.00 | exit 1, 150.00, rejected |
| Go `RFC3339Nano` `....123456789Z` | exit 0, 154.00 | exit 1, 150.00, rejected |
| control: `+05:30`, MySQL naive, JavaScript `.000Z` | exit 0, 154.00 | exit 0, 154.00 (same) |

On 3.9.6, r1 already rejected 7 of these 10 (`raw/regressions-3.9.6.txt`). So N2's cross-interpreter consistency was reached by adopting the strict 3.9 subset on every Python. The doc states this grammar, and the refusal is loud: rejected rows, gap `rejected_rows`, exit 1, `--rejects` lines.

It is still P3, not P4. PostgreSQL's default text output for every `timestamptz` column uses an hour-only offset (`+00`). A drop exported that way has every timestamped row rejected, so the tool produces no metric from a standard export without preprocessing.

Suggested fix, not a patch, since no P1 or P2 needs one:
- also accept `+HH`, `+HHMM` and one optional space before the offset;
- accept 7 to 9 fraction digits when the extra digits can be truncated safely, or with a note;
- keep one regex, so all Pythons still agree.

### RD (P4): date-only values on a midnight DST change are refused
In `America/Santiago`, clocks jump from 00:00 to 01:00 on 2026-09-06. A fact row with the date-only value `2026-09-06` is now rejected as `nonexistent_local_time`; r1 accepted it. A contract window starting `2026-09-06` makes the whole run invalid (exit 2).

This follows the doc ("never guesses"). But a date-only value names a calendar day, whose first instant (01:00 local) exists. Reading a date as the start of its day would avoid refusing a whole daily-grain export or contract in zones with midnight transitions, such as Santiago, Havana and Beirut. America/Los_Angeles is unaffected (control).

### Notes
- The r2 write path keeps a hard link (`.<name>.<hex>.keep`) to any file being replaced and removes it at the end. A crash between those steps would leave a hidden `.keep` file. This was not exercised: no kill -9 mid-write was run for r2. b06 and the fresh caller left no temp or `.keep` files.
- Rows that differ only in `loaded_at` are exact copies even without as_of, and the earliest load is kept. That matches the doc and changes r1 results on such files (RN).

## Oracle teeth (3.12.14; `raw/oracle-teeth.txt`, `raw/builder-oracle-vs-teeth.txt`, `raw/builder-tests-vs-mutants.txt`, `raw/repro-teeth.txt`, `raw/rv-n5-equivalence.txt`)
`oracle/make_mutants_r2.py` makes 31 mutants. Each edit must apply exactly once.
- **The 23 M13 mutants.** 20 have unchanged anchors. Three were ported to the r2 code with the same meaning:
  - `late_ignored`: the late check disabled;
  - `naive_as_utc`: naive times read as UTC;
  - `uppercase_ignored`.
- **8 fix-revert mutants, one per fix:**
  - `rv_n1_unknown_on_time`: r1's loaded_at rule;
  - `rv_n2_fromisoformat_fallback`;
  - `rv_n3_loaded_at_in_content`;
  - `rv_n4_write_each_now`;
  - `rv_n5_recursion_uncaught`;
  - `rv_n6_dst_guess`;
  - `rv_n7_unicode_int`: `\d` back;
  - `rv_n8_line_order`.

The runner is M13's `run_teeth.sh` without the positive-control subject (`oracle/run_teeth_r2.sh`).

| Subject | M13 oracle (15) | Builder oracle (13) | Builder tests (35) | M13 finding repros |
|---|---|---|---|---|
| candidate 75a4e2b | 15/15 ACCEPT | 13/13 accept | OK | reference |
| M13 stubs noop_fake_clean, naive_sum | REJECT (3, 3 pass) | reject (0, 0) | n/a | n/a |
| builder noop_stub, naive_stub | REJECT (2, 2 pass) | reject (0, 0) | n/a | n/a |
| 23 M13 mutants killed | **22/23** | **22/23** | **23/23** | not run |
| 8 fix-revert mutants killed | 2/8 (rv_n1, rv_n8) | **7/8** | **7/8** | **7/8**, each in its own N section |
| **non-equivalent mutants killed (29)** | 24/29 | **29/29** | **29/29** | |

Equivalent mutants:
- **`symlink_allowed`**, as in M13. A second regular-file check and `O_NOFOLLOW` still refuse the symlink. The builder tests catch it only through the message.
- **`rv_n5_recursion_uncaught`**. `main` has a defensive `except RecursionError` that still exits 2 with no traceback; only the message changes from "c.json: JSON nested too deeply" to "input nested too deeply". This was checked on 3.12.14 and 3.9.6 (`raw/rv-n5-equivalence.txt`).

The M13 oracle's core predates N1 to N8, so it does not target most fix-revert mutants; the finding repros cover them.

The rework note claims tests 35/35 and builder oracle 34/35 on its own 35 mutants. That set was not rerun. On this independent set, both kill every non-equivalent mutant.

## Fresh caller (`oracle/m13r2_fresh_caller.sh`; `raw/fresh-caller.txt` on 3.12.14, `raw/fresh-caller-py39.txt` on 3.9.6)
The fresh caller uses `env -i`, a new HOME, a `python3` shim, the M13 offline guard and a `/tmp` copy of the tree. The contract is the doc's JSON block, extracted verbatim. It runs only the two documented commands.

The data is new: 10 rows exercising r2 behaviour:
- a thousands separator and lower-case currency;
- a re-delivery differing only in `loaded_at`;
- a blank `loaded_at` under as_of;
- a superseded version;
- an orphan key;
- a void row;
- the window end in local time;
- a `+0000` offset, which the doc's grammar refuses.

The hand answer is written before the run (in the log): USD 1275.00 and EUR 80.00, 4 orders, exit 1, gaps `rejected_rows`, `loaded_at_unknown`, `unmatched_or_missing_join_key` and `control_mismatch`.

The report matches the hand answer exactly on both interpreters. `rejects.csv` names lines 4, 5, 6, 9, 10 and 11 with the expected reasons. There were 0 network attempts, 0 temp or `.keep` files left and an empty HOME.

## Interpreter matrix (`raw/pyversions-matrix.txt`, `raw/oracle-cross-interpreter.txt`, `raw/adversarial-candidate.txt`)
| Python | M13 oracle | G13 tests | Original tests | Full suite |
|---|---|---|---|---|
| 3.9.6 (/usr/bin/python3, SQLite 3.54.0) | 15/15 | 35 OK | 84 OK | 119 OK |
| 3.11.16 | 15/15 | 35 OK | 84 OK | 119 OK |
| 3.12.14 | 15/15 | 35 OK | 84 OK | 119 OK |
| 3.13.15 | 15/15 | 35 OK | 84 OK | 119 OK |

- b01: identical exit code and bytes on 4 interpreters.
- b02: 0 timestamp forms disagree.
- Adversarial summary: OK 12/12.
- The regression script, finding repros and fresh caller were run on 3.12.14 and 3.9.6. The r2 answers are identical on both (`raw/regressions-*.txt`).

## Rejected and superseded runs
None were rejected. A first run of the regression script had a harness error, from a missing window and the wrong metrics shape, and printed no comparison. The script was fixed before any result was used. Only the rerun outputs are kept.

## Limitations
- Mutant teeth ran on 3.12.14 only.
- The builder's own 35 r2 mutants were not rerun.
- The scale run went to 1.14 M rows. The 2 M row and 256 MiB limits were not run.
- Crash-during-write (kill -9 between staging, linking and renaming) was not exercised for the new write path.
- DST cases cover America/Los_Angeles and America/Santiago only.
- The offline guard blocks Python socket and DNS calls in the candidate process. It is not a sandbox.
- All data is synthetic.

## Files
- `VALIDATION.md`: this report.
- `MANIFEST.sha256`: SHA-256 of every other file in this folder.
- `oracle/m13r2_regressions.py`: the r2 vs r1 comparison (RT, RD, RN, RW).
- `oracle/make_mutants_r2.py`: the 31 mutants.
- `oracle/run_teeth_r2.sh`, `oracle/run_matrix_r2.sh`: the teeth and cross-interpreter runners.
- `oracle/m13r2_fresh_caller.sh`: the fresh caller.
- `oracle/m13/`: the M13 tools used unchanged:
  - `m13_oracle.py`, `m13_adversarial.py`, `m13_finding_repros.*`;
  - `make_mutants.py`, `run_teeth.sh`;
  - `stubs/`, `inject/`;
  - M13's `proposed-fix.patch`, for reference.
- `raw/`: every run output named above, plus the fetch, worktree, manifest, diffstat and week-grok before and after records.

## Publication notes
- The publish copy replaces local paths with placeholders (`<D>`, `<PY312>`, `<UV>`, `<TMPDIR>` and so on) and drops the week-grok status listings. The before and after hashes stay in `raw/weekgrok-before.txt` and `raw/weekgrok-after.txt`.
