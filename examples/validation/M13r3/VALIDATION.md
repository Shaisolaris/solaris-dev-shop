# M13 r3: recheck of the G13 rework r3 "Reconciled metrics from dirty CSV"

**Kind:** Grok self-validation (same bot as the G13 builder). Not independent review. An independent reviewer is
still required by the QA2 contract.

**Verdict: PASS** against rework commit `5666e7beb161d1252ddd5dcc0a166aca83255370` (branch
`review/grok-g13-csv-reconciliation`, parent `75a4e2b`, base `02ba9c5`). There are no P1, P2 or P3 findings, and one
P4 finding (T1). Both M13 r2 findings are fixed: RT (P3, timestamp spellings) and RD (P4, date-only values on a
midnight DST change).
- The manifest (`<D>/grok-output/G13/MANIFEST.sha256`, r3) verified 21/21. Its file set equals the diff
  02ba9c5..5666e7b, and `G13-r3.patch` equals the 75a4e2b..5666e7b diff byte for byte (`raw/manifest-verify.txt`).
- The full suite is 124 OK (40 G13 + 84 other) on 3.9.6 (Apple SQLite 3.54.0), 3.11.16, 3.12.14 and 3.13.15
  (`raw/pyversions-matrix.txt`). The candidate worktree's status was empty before and after.
- The M13 oracle is 15/15 ACCEPT on all four (`raw/oracle-cross-interpreter.txt`). The M13 adversarial suite is
  OK 12/12, with 0 timestamp forms that differ by interpreter (`raw/adversarial-candidate.txt`). The builder oracle
  is 14/14.
- The M13 finding repros N1 to N8 still pass. The only change from r2 is in the N2 listing, where `+0000`, `+00` and
  a 7-digit fraction are now accepted on every interpreter, as RT intends (`raw/finding-repros.txt`).

Runs were on host macOS (arm64) on 2026-10-18, between 17:29 and 18:01 PT. An unrelated builder job ran on the same
host at the same time.

## Isolation
- The commit was fetched read-only into the programme repo, and FETCH_HEAD equals the full SHA (`raw/fetch.txt`).
  Then `git worktree add --detach /tmp/m13r3-eval 5666e7b...` (`raw/worktree-add.txt`). The r2 tool was extracted
  with `git show` to `/tmp/m13r3-old`, for comparison only. Nothing was cloned onto another machine.
- The builder's worktree was not written. Branch, HEAD, index hash and status hash are identical before (17:29:41
  PT) and after (18:01:30 PT), and the status listing is byte-identical. The checks are read-only and use
  `git --no-optional-locks status`.
- Mutants ran in `/tmp` copies. No candidate file was modified, and every candidate run went through the M13
  offline guard.

## M13 r2 findings
| r2 finding | r3 result | Evidence |
|---|---|---|
| RT (P3) common export spellings refused | **Fixed.** All 10 RT spellings exit 0 with USD 154.00 on 3.9.6 and 3.12.14 (r2: exit 1, USD 150.00). See p01 for exact instants, p02 for refused forms, and below for the r2 tool | `raw/regressions-r3-vs-r2-*.txt`, `raw/probes-r3-*.txt` |
| RD (P4) date-only on a midnight DST change refused | **Fixed.** The fact row and the contract window are accepted. The first instant is correct in four zones (p04), and clock times in the gap or the repeat are still refused (p05, N6 kept) | same |

The RN (loaded_at) and RW (write path) regression cases are unchanged from r2 (`(same)` in the regression output).

## New probes (`oracle/m13r3_probes.py`; `raw/probes-r3-3.12.14.txt` and `-3.9.6.txt`, identical)
Every expected instant is written by hand. An accepted spelling is checked to the microsecond: a window ending
exactly at its instant must exclude the row, and one ending 1 microsecond later must include it. The result is 61
PASS, 0 FAIL on both interpreters.
- **p01, 17 accepted spellings, each exact.** They include:
  - PostgreSQL `+00`, `-07` and `-00`, also with a fraction;
  - `+05:30` and `+0530`, and `-0700`;
  - SQL Server `.1234567 +00:00` and `.9999999 -07:00`;
  - Go `.123456789Z` and `.000000999Z`;
  - lower-case `t` and `z`;
  - `HH:MM -07`;
  - the extreme offsets `+23:59` and `-23:59`.

  The r2 tool gets 4 of the 17 right.
- **p02, 25 malformed forms refused** as `bad_timestamp`:
  - 10 fraction digits;
  - `+0`, `+000`, `+5` and `+05:3`;
  - offset minutes over 59, and offsets of `+24` or more;
  - a space before `Z`, two spaces, and `.Z`;
  - Arabic-Indic and full-width digits;
  - `+00:00Z`, basic and week dates;
  - `24:00` and `:60`;
  - ` UTC`, and `T12Z`.
- **p04, date-only first instants:**
  - America/Santiago 2026-09-06 is 04:00Z (midnight spring-forward);
  - America/Havana 2026-11-01 is 04:00Z (the first of two midnights);
  - Asia/Beirut 2026-03-29 is 2026-03-28T22:00Z (spring-forward) and 2026-10-25 is 2026-10-24T22:00Z;
  - Santiago 2026-04-05 is 04:00Z (fall-back at 03:00 UTC);
  - the two Los Angeles controls are correct.

  Each is checked both as a fact row and as a contract window start.
- **p05:** `00:30` and `00:00` in the Santiago gap and `00:30` in the Havana repeat are still refused with the
  right reason. So is `23:30` in the Beirut repeat. A contract window start inside the gap is invalid (exit 2).

### T1 (P4): contract times with sub-microsecond digits are silently shifted
The tool drops digits past the sixth (documented: "two times that differ only past the sixth fraction digit compare
as equal"). The contract grammar also accepts 9 digits for `window` and `as_of`, so a contract bound carrying
non-zero 7th to 9th digits is silently truncated, and rows within 1 microsecond of it land on the wrong side (p03):
- window end `.0000005Z` with a row at `.0000001Z`, which is truly inside: the row is excluded, giving USD 150.00
  instead of 154.00, exit 0;
- window start `.0000005Z` with a row at `.0000001Z`, which is truly before the window: the row is counted, giving
  USD 5.00 instead of 1.00;
- `as_of` `.0000001Z` with `loaded_at` `.0000009Z`, which is truly late: the row is counted as on time, with no
  `late_rows`.

For fact rows against microsecond bounds, truncation is order-preserving, so the result is exact; p01 shows this.
Only bounds with sub-microsecond digits misbehave, which is rare, hence P4. A suggested fix (not a patch, since no
P1 or P2 needs one) is to refuse a contract time with non-zero digits past the sixth, so the shift is loud (exit 2).
The same limit applies to the G10 r4 parser (M10 r3).

### Notes (not counted)
- p03d: two versions whose `updated_at` differ only in the 7th digit tie loudly (`unresolved_duplicates`), as the
  doc says.
- p06: in `Pacific/Apia` the calendar day 2011-12-30 never existed (the zone skipped it). The date-only value
  `2011-12-30` is read as 2011-12-30T10:00Z, the first instant of 2011-12-31 local, with no note. This is a
  historical tzdb edge and outside the doc's examples.
- The builder oracle does not catch `rt_offset_minutes_unchecked`, which accepts `+05:60` as a 6-hour offset; the
  builder tests do.

## Mutation teeth (`raw/teeth-3.12.14.tsv`, `raw/teeth-3.9.6.tsv`; `oracle/m13r3_teeth.sh`, `oracle/tally_m13r3.py`)
There are 41 mutants:
- **M13 r2's 31** (`oracle/make_mutants_r2.py`, unchanged). Every anchor still applied exactly once in r3.
- **10 new r3 mutants** (`oracle/make_mutants_r3.py`):
  - `rv_rt_colon_offset_only`, `rv_rt_six_fraction_digits`, `rv_rt_no_space_before_offset`;
  - `rt_fraction_rounded`, `rt_space_not_stripped`, `rt_offset_minutes_unchecked`, `rt_hour_offset_minutes_misread`;
  - `rv_rd_date_only_refused`, `rd_date_only_second_fold`, `rd_any_clock_time`.

Builder oracle runs used default sizes.

| Scorer | 3.12.14 all 41 | 3.12.14 r3 mutants (10) | 3.9.6 all 41 | 3.9.6 r3 mutants (10) |
|---|---|---|---|---|
| M13 oracle (15, predates r3) | 24 | 0 | 24 | 0 |
| Builder oracle (14) | 38 | 9 | 38 | 9 |
| Builder tests (40) | **40** | **10** | **40** | **10** |
| M13 r3 probes | 15 | 10 | 15 | 10 |
| Union | **40** | 10 | **40** | 10 |

- The candidate passes all four scorers. The r2 tool fails builder oracle o14, 18 builder tests (plus 1 error) and
  19 r3 probes, while the M13 oracle accepts it, since its checks predate r3.
- All M13 and builder stubs are rejected.
- The only union survivor is `rv_n5_recursion_uncaught`, already shown equivalent in M13 r2: `main`'s defensive
  `except RecursionError` still exits 2 with no traceback.
- `symlink_allowed` is equivalent (`O_NOFOLLOW`), but the builder tests catch it through its message.

## Fresh caller (`oracle/m13r3_fresh_caller.sh`; `raw/fresh-caller-3.12.14.txt` and `-3.9.6.txt`, identical except for the interpreter line)
The run uses `env -i`, a new HOME, a `python3` shim, the M13 offline guard, a `/tmp` copy of the tree and the doc's
contract JSON verbatim, and only the two documented commands.

The data is new: 10 rows in r3 spellings:
- PostgreSQL `+00`;
- `datetimeoffset(7)` with a space;
- `.9999999-07` just before the window end;
- `.0000001-0700` just after it;
- a date-only row;
- `+05:60`;
- a load 1 s after as_of;
- an orphan key with a re-delivery whose `loaded_at` is spelled `-07`;
- a `test` row.

The hand answer, written before the run, is USD 2038.00 and EUR 40.00 over 5 orders, exit 1, with gaps
`rejected_rows`, `late_rows`, `unmatched_or_missing_join_key` and `control_mismatch`. The report matches it exactly
on both interpreters. `rejects.csv` names lines 5 (outside_window), 7 (bad_timestamp), 8 (late_after_as_of),
10 (duplicate_exact) and 11 (excluded_status). There were 0 network attempts, 0 temp or `.keep` files and an empty
HOME.

## Rejected and superseded runs (kept in `raw/superseded/`)
The first probe run (`probes-r3-*-v1-harness-errors.txt`) had two harness errors, not tool errors:
- it compared `rejected` to an integer instead of the per-reason map, so 29 refused spellings were wrongly
  printed as FAIL although the tool refused each one for the right reason;
- my hand value for Santiago 2026-04-05 was 03:00Z. zoneinfo shows the fall-back is at 03:00 UTC, so 00:00 local
  happens once, at 04:00Z, which is what the tool reports.

Both were fixed before any result was used, and only the v2 run is cited.

## Limitations
- No Linux or Windows runs, and Python 3.10 is not on the host.
- DST cases cover America/Santiago, America/Havana, Asia/Beirut, America/Los_Angeles and one Pacific/Apia note.
- The builder's own 51 r3 mutants were not rerun. My 41 are an independent set.
- The scale limits (2 M rows, 256 MiB) were not rerun; r3 does not touch that path.
- The offline guard blocks Python socket and DNS calls only. It is not a sandbox.
- All data is synthetic.

## Files
- `VALIDATION.md`: this report.
- `oracle/m13r3_probes.py`: the r3 probes (p01 to p06).
- `oracle/make_mutants_r3.py`: the 10 r3 mutants.
- `oracle/make_mutants_r2.py`: the 31 r2 mutants.
- `oracle/m13r3_teeth.sh`, `oracle/tally_m13r3.py`: the teeth runner and tally.
- `oracle/m13r3_fresh_caller.sh` and `oracle/m13r2_fresh_caller.sh` (for reference).
- `oracle/m13r2_regressions.py`.
- `oracle/run_matrix_r3.sh`.
- `oracle/m13/`: the M13 tools, unchanged.
- `raw/`: every run output named above, plus the fetch, worktree, manifest and week-grok before and after records.
