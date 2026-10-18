# M03 r2: recheck of the G03 rework "Recovery without data loss"

**Kind:** Grok self-validation (same bot as the G03 builder). Not independent review. Done adversarially with the M03 oracle (written for M03, not derived from the builder's oracle or tests), the 15 M03 mutants and new regression probes. An independent reviewer is still required by the QA2 contract.

**Verdict: FAIL** against rework commit `9f2fbbc77c953b80efd66e5a712cb6159fdc4dab` (branch `review/grok-g03-recovery`, parent `7c63297`, base `02ba9c5`), manifest `grok-output/G03/MANIFEST.sha256` (r2). The manifest verified 13/13, and its file set equals the diff file set (`raw/manifest-verify.txt`).

All seven r1 findings (F1 to F7) are fixed, each re-run with its exact r1 repro (`raw/finding-repros.txt`). The full suite is 128 OK on 3.9.6 (Apple SQLite 3.54.0), 3.11.16, 3.12.14 and 3.13.15. The WAL test passes on 3.9 (`raw/pyversions-matrix.txt`).

The fail is one regression introduced by the F3 fix (**R-A, P2**). It shows only on the stated stock-Mac interpreter (/usr/bin/python3 3.9.6), and only once the M03 injector works on 3.9 (it did not in r1).
- A restore is killed after a WAL database's `-wal`/`-shm` were set aside but before the database itself.
- `health` is then run, as the doc's drill says ("run `health` (fails) and `recover`").
- The new read fallback creates a fresh `-wal`/`-shm` next to the half-swapped database.
- `recover` then refuses with `needs_human` and changes nothing. The dataset stays mixed: app.db holds the snapshot values, audit.db the old live values.

Nothing is lost, and every copy is kept. Deleting the two files health created lets `recover` finish. A two-line positive-control fix (`oracle/proposed-fix-r2.patch`, not applied to the candidate) makes the M03 oracle 12/12 on 3.9.6 and 3.12, the builder oracle 15/15 and the suite 128 OK (`raw/positive-control-r2.txt`).

Run on host macOS (arm64) on 2026-10-18 between 13:16 and 13:45 PT. Python 3.12.14 with bundled SQLite 3.53.1 unless stated.

## Isolation
- `git fetch origin review/grok-g03-recovery` (read-only) from the programme worktree; FETCH_HEAD equals the full SHA. Then `git worktree add --detach /tmp/m03r2-eval 9f2fbbc...` (`raw/fetch.txt`, `raw/worktree-add.txt`). Nothing was cloned onto any other machine.
- The builder's worktree was not written. Branch, HEAD, index hash and status hash are identical before (13:16:25 PT) and after (13:44:44 PT) (`raw/weekgrok-before.txt`, `raw/weekgrok-after.txt`).
- All runs used disposable temp directories. Mutants, the r1 tool and the positive control ran in scratch copies, never in the candidate worktree.

## Harness correction (M03 injector on 3.9)
The builder reported that the M03 injector records 0 rename events on 3.9. Confirmed (`raw/injector-py39-check.txt`).
- The cause: Python 3.9 `pathlib._NormalAccessor` stores `os.open`, `os.rename`, `os.replace` and `os.unlink` as class attributes, so the injector's plain-function wrappers become bound methods and raise TypeError.
- The r2 copy (`oracle/inject/sitecustomize.py`) wraps them with `functools.partial`, which is not a descriptor. It now gives 5 events in the probe on both 3.9.6 and 3.12, and 9 kill points for a k4 restore on 3.9.6.
- The r1 M03 files were not edited.
- So **r1's k4 never ran on 3.9**. R-A was reachable only after this correction.

## Acceptance items
| Item | Result | Evidence |
|---|---|---|
| Actual values restored | PASS (F1, F2 fixed) | k1, k10 (sqlitedata, SQLiteLog, user_version) and k11 pass on 3.9.6, 3.11, 3.12 and 3.13. F1 and F2 repros: health unhealthy, restore brings the values back. |
| Good target survives invalid backup | PASS | k2: 13 invalid snapshots refused, dataset byte-identical (all 4 interpreters). F5 repro: a malformed manifest entry is refused cleanly by verify (1) and health (2). |
| Dry run byte-identical | PASS | k3, including `--dry-run --confirm`. The dry-run-with-confirm mutant is killed by k3, by builder oracle c3 and by the builder tests (1 failure, 1 error). |
| Both rename gaps recover | **FAIL on 3.9.6 (R-A)**, PASS on 3.11/3.12/3.13 | k4 on 3.9.6: 6 of 6 runs fail at kill@7 (`raw/k4-py39-health-mixed.txt`, `raw/operational-3.9.6.txt` drill N=4 MIXED). Without the intervening health, kill@7 rolls forward (control in the same file). k5 (recover killed at 7 points) passes everywhere. External kill -9: 40 restore and 40 recover rounds OK on 3.9.6 and 3.12. |
| No outside writes | PASS | k6. g02: a symlinked grandparent `--out` is refused and nothing is created at the target. |
| Finite timeout | PASS (F7 fixed) | k7. g04: `health --lock-timeout 1` gives busy in 1.1 s; nan, inf, -1, 0 and 601 exit 2. a15: health on a locked DB now says "busy ... retry". |
| Exact missing-DB check | PASS (F4 fixed) | k8. F4 repro: 0-byte and table-less DBs are unhealthy without `--snapshot`. |
| Lock all branches / concurrency | PASS | k9, k12. g03: 8 health and 4 snapshots at once on a sidecar-less WAL DB, main file unchanged. g06: 10 restores raced by recover, each either restored or refused busy with live values untouched. |
| WAL on stock Mac Python (F3) | PASS for snapshot/verify/restore, with R-A | F3a/F3b repros exit 0 on 3.9.6. `test_wal_source_and_sidecars_are_handled` OK on 3.9.6. R1 probe (`raw/r1-wal-checkpoint-probe.txt`): the fallback does not checkpoint into the main file, and the snapshot includes WAL-only rows. |
| Original 84 tests preserved | PASS | `test_[!g]*.py`: 84 OK on all four interpreters. G03 tests: 44 OK. Full: 128 OK. |
| Fresh caller | PASS | `raw/fresh-caller.txt` (3.12) and `raw/fresh-caller-py39.txt`: `env -i`, doc commands only. The literal first command now works without creating `snapshots/` first (F6 fixed), and the crash drill gives health fail, then recover ok, then health ok. The rejected run is kept (below). |

## Findings
### R-A (P2, regression from the F3 fix): `health` during an interrupted restore creates WAL sidecars that make `recover` refuse, leaving a mixed dataset (3.9.6, Apple SQLite)
Repro: `/usr/bin/python3 oracle/m03r2_k4_probe.py /usr/bin/python3 <TREE>/employees/infrastructure/database-administrator/sqlite_recovery.py 7 --health --clean-new-sidecars`. The fixture has app.db plus audit.db in WAL mode with `-wal`/`-shm` present. Apple's build keeps them after close.

Observed (`raw/k4-py39-health-mixed.txt`):
```
after kill: app.db (snapshot values), audit.db (live), audit.db-shm.pre-restore-..., audit.db-wal.pre-restore-..., .audit.db.restore-....staged, .solaris-recovery.json
health rc=1: .solaris-recovery.json: a restore is in progress or was interrupted; run `recover`
after health: ... audit.db-shm, audit.db-wal (new; 32768 and 0 bytes) ...
recover rc=1: recover: needs_human | cannot tell how far the swap got from the files present; nothing changed.
state: mixed (app.db = snapshot, audit.db = live)
after removing the two new files: recover rc=0, interrupted after 4 of 6 renames ... completing the restore; state forward
```
- Cause: `health` still opens each expected DB while the journal is open. The kill left `-shm` missing and the WAL header present, so `_open_live` takes the new fallback (normal connection, `query_only=ON`), which creates `-wal`/`-shm`. `recover` then sees files that are not in its plan.
- Only kill@7 of 9 is affected. On 3.12 the bundled SQLite removes sidecars on close, so the gap does not exist (4 renames).
- It is not reachable on r1, because r1 refused the restore on 3.9 (F3).
- The builder's 3.9 crash-point test does not run health between kill and recover.
- Fix direction (positive control, `oracle/proposed-fix-r2.patch`): health reports the open journal and does not open databases while it exists. Alternatives: recover tolerates an empty `-wal` plus `-shm` next to a set-aside pair, or the fallback is never used while a journal exists.

### R-B (P4): a snapshot refused as busy still creates the missing parent folder
g01 in `raw/regressions.txt` (3.9.6 and 3.12). With the dataset flock held, `snapshot data --out snapshots/x` exits 1 "busy", but `snapshots/` now exists. The cause is that the F6 `os.mkdir(out.parent)` runs before `_locked`. It is harmless (empty folder, inside the caller's chosen path), but it is a write by a refused command.

### R-C (P3, evidence claim): the builder oracle does not kill `no_dataset_flock`
REWORK.md says all 15 M03 mutants "are killed by the G03 tests and by the builder oracle". The tests do kill all 15 (`raw/builder-tests-vs-mutants.txt`). The builder oracle accepts `no_dataset_flock`:
- 15/15 in the teeth run;
- 5 of 5 repeat runs on 3.12;
- 2 of 5 repeat runs on 3.9.6. The other 3 were caught by c10 "leftovers", which is timing-dependent (`raw/builder-oracle-no_dataset_flock-repeats.txt`).

### R-D (P4, evidence claim): F4/F5/F7 mutants are not caught by the M03 oracle
REWORK.md says F4, F5, F7 and F3 mutants "are caught by the tests and the M03 oracle". The M03 oracle (12 checks) accepts `r2_f4_empty_db_healthy`, `r2_f5_no_entry_check`, `r2_f7_nan_accepted` and `r2_journal_temps_kept` 12/12. It also accepts `r2_f3_no_ro_fallback` on 3.9.6. Only the M03 finding-repro script exposes F4, F5 and F7, and that is not an oracle. The builder's tests do kill all 8 r2 mutants (the F3 two only on 3.9.6, `raw/f3-mutants-py39.txt`), as claimed.

## Oracle teeth (`raw/oracle-teeth.txt`, 3.12)
| Subject | M03 oracle (12) | Builder oracle (15) | Builder tests (44) |
|---|---|---|---|
| candidate 9f2fbbc | 12/12 ACCEPT (11/12 on 3.9.6: R-A) | 15/15 | OK |
| r1 7c63297 | 11/12 (k10) | 13/15 (c14, c15) | 7 failures |
| M03 no-op stub / naive copier | 0/12, 1/12 | 0/15, 3/15 | n/a |
| builder noop_stub / naive_stub | 0/12, 1/12 | 0/15, 3/15 | n/a |
| 15 M03 mutants | 14/15 caught on checks the candidate passes; `no_staging_journal` survives (equivalent under the docs, as in r1) | 14/15; `no_dataset_flock` accepted (R-C) | 15/15 killed |
| `dry_run_restores_when_confirmed` | caught (k3) | caught (c3) | killed (1 failure, 1 error) |
| 8 builder r2 mutants | 2/8 on 3.12 (r2_f1, r2_f2 by k10). On 3.9.6 also r2_f3_copy_keeps_sidecars (4/12) | 3/8 (f1, f2, journal_temps) | 6/8 on 3.12; 8/8 with the F3 two on 3.9.6 |
| positive control (candidate + proposed-fix-r2.patch) | 12/12 on 3.9.6 and 3.12 | 15/15 | 128 OK |

## Regression hunt (`raw/regressions.txt`, `oracle/m03r2_regressions.py`)
These ran on 3.9.6 and 3.12 with the same results.
- g01: R-B.
- g02: a symlinked grandparent is refused.
- g03: concurrent health/snapshot on a sidecar-less WAL DB is fine; the main file is unchanged.
- g04: timeouts.
- g05: the new journal-temp cleanup removes only matching regular files. A directory, a symlink and an outside file are kept, and a dry run removes nothing.
- g06: restore vs recover race.
- g07: a restore over fallback-created sidecars installs exact values.

Rename gaps under SIGKILL: k4 (in-process, every rename/unlink) and the operational drill (`raw/operational-*.txt`, 40 + 40 external kill -9 rounds). Adversarial pass: `raw/adversarial-3.12.14.txt` and `raw/adversarial-3.9.6.txt` (17 cases, OK 12, NOTE 5, identical on both).

## Rejected and superseded runs (kept)
- `raw/regressions-run1-harness.txt`: harness defects. Case-colliding names on case-insensitive APFS, and first-line-only JSON parsing.
- `raw/regressions-run2-g06-expectation.txt`: my wrong expectation that every raced restore succeeds. A busy refusal is correct.
- `raw/fresh-caller-run1-r1-harness.txt`: the r1 fresh-caller script still applied its F6 mkdir workaround and re-ran the snapshot, which then existed (exit 2), so the snapshot id was empty. The literal doc command had exited 0.
- The first 3.9.6 oracle run showing k4 FAIL (`raw/oracle-pyversions.txt`) is not rejected. It is the R-A evidence, reproduced 6 of 6 times.

## Limitations
- Self-validation by the builder's own bot. The same blind spots are possible.
- One host (macOS arm64, APFS). Linux and other filesystems were not run.
- The F3/R-A behaviour depends on Apple's SQLite build. Only 3.54.0 was available.
- The kill injector is in-process (the standard library is patched). External kill -9 rounds cover timing but not exact points.
- Mutants are single edits chosen by me and by the builder. Teeth are evidence, not proof.
- The positive-control patch is a sketch to show the oracle can be satisfied. It is not reviewed as a fix.

## Files
- `oracle/`: M03 oracle and helpers copied from r1. r2 additions are `inject/sitecustomize.py` (partial fix), `run_teeth_r2.sh`, `run_pyversions_r2.sh`, `m03r2_regressions.py`, `m03r2_k4_probe.py`, `m03r2_wal_checkpoint_probe.sh`, `m03r2_fresh_caller.sh`, `builder_make_mutants_r2.py` (copy of the builder's script) and `proposed-fix-r2.patch`.
- `raw/`: every run listed above.
- `MANIFEST.sha256`: sha256 of every file here except itself.
