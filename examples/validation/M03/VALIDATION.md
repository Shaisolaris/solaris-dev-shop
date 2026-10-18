# M03 validation of G03 "Recovery without data loss"

**Kind:** Grok self-validation (same bot as the G03 builder). Not independent review. Done adversarially with an oracle written for M03 and not derived from the builder's oracle or tests. An independent reviewer is still required by the QA2 contract.

**Verdict: FAIL** against candidate commit `7c63297d626ab2ac5929080e57c9ae66e7c905bc` (branch `review/grok-g03-recovery`, parent and base `02ba9c5`), manifest `grok-output/G03/MANIFEST.sha256`. The manifest verified 13/13, and its file set equals the diff file set (`raw/manifest-verify.txt`).

The acceptance item "Actual values restored" fails for a reproducible class of input. User tables whose names match the SQL pattern `sqlite_%` are invisible. Here `_` is a LIKE wildcard and LIKE ignores ASCII case, so `sqlitedata`, `SQLiteLog`, `sqlite1` and similar are all hidden. When only such tables change, `health --snapshot` says ok, and `restore --confirm` says "every database already matches; nothing changed" with exit 0. The values are not restored (F1). Header pragmas behave the same way (F2).

On the default `python3` of a stock Mac (Apple's system SQLite 3.54.0), WAL databases cannot be snapshotted usably (F3). This is the G03 test failure the builder sees on Python 3.9.

Every other acceptance item passed with evidence. A two-line proposed fix (`oracle/proposed-fix.patch`, not applied to the candidate) passes this oracle 12/12, the builder's oracle 11/11 and the builder's 30 tests.

Run on host macOS (arm64) on 2026-10-18 between 11:47 and 12:30 PT. Python 3.12.14 with bundled SQLite 3.53.1 unless stated.

## Isolation
- `git fetch origin review/grok-g03-recovery` (read-only) from the programme worktree, then `git worktree add --detach <candidate> 7c63297` (`raw/fetch.txt`, `raw/worktree-add.txt`). Nothing was cloned onto any other machine.
- The builder's worktree was not written. Its branch, HEAD and index hash are the same before and after (`raw/weekgrok-before.txt`, `raw/weekgrok-after.txt`). Its status changed during the run, and every changed path is attributable to the active builder (paths and mtimes are in `raw/weekgrok-after.txt`).
- All runs used disposable temp directories. The candidate worktree's `git status` stayed empty (`raw/pyversions-matrix.txt`, `raw/full-suite.txt`).

## Prior evidence: Muse ACCEPT
`MUSE-FINAL-PARK-HANDBACK.json` relays an ACCEPT for this SHA ("Real crash drills both directions byte-correct; tamper/confirm/symlink refusal; 30/30, 114/114, oracle 11/11"). Its own evidence level is "Native handback read; remote full verdict/log artifacts not yet retained/adjudicated". I treated it as a claim with no retained logs.
- The "oracle 11/11" it cites is the builder's `recovery_oracle.py`. That oracle **accepts 6 of my 15 mutants** (below).
- None of its checks covers F1, F2 or F3.

## Acceptance items

| Item | Result | Evidence |
|---|---|---|
| Actual values restored | **FAIL** (F1, F2) | k1 PASS: three change types, repeat restore, missing DB recreated. k11 PASS: equal row counts, values only. **k10 FAIL**: `sqlitedata`/`SQLiteLog` changes not restored, health ok, restore rc 0. a01/a02 in `raw/adversarial-candidate.txt`. Values are read by the oracle from private copies including `-wal`, never from tool output. |
| Good target survives invalid backup | PASS | k2: 13 invalid snapshots refused with the dataset byte-identical: byte flip, truncation, swapped DB, forged hash, extra member, symlink member, hard-link member, garbage manifest, missing manifest, `../` name, missing member, wrong confirm, no confirm. a06: missing `tables` key refused by verify and restore. |
| Dry run byte-identical | PASS | k3: `restore --dry-run` (with and without `--confirm`), `recover --dry-run` and `verify` leave the dataset (including real `-wal`/`-shm`), snapshot and outside byte-identical with unchanged mtimes. `health` is a normal reader and may refresh `-shm` only (see the note on health and -shm). |
| Both rename gaps recover | PASS | k4: SIGKILL (fault injection inside the process) before each of 7 rename/unlink events. Gap "DB set aside, not installed" hit 2 times and "installed, not finished" 1 time. Health fails mid-swap. Recover went forward 5 times and back 2 times, with no mixed state and old live values kept. Forced roll-back with a damaged staged copy (x2) restored the originals exactly, and `recover --dry-run` previews `roll_back`. k5: recover itself killed at 7 points. a17: kill at all 4 write-opens. |
| No outside writes | PASS | k6, a07, a09 (forged journal steps with `../` refused, `needs_human`), a10 (symlinked live DB), a11 (lock path symlinked outside), a16 (snapshot into dataset refused). |
| Finite timeout | PASS | k7: holder `BEGIN EXCLUSIVE`; restore and snapshot with `--lock-timeout 1` end in 1.1 s, non-zero and unchanged; health 5.2 s (fixed 5 s, no flag). k12: external flock holder refuses restore. a13: open read transaction refuses restore in 1.1 s. |
| Exact missing-DB check | PASS with F4 | k8: missing, renamed, directory, symlink, empty-vs-snapshot and garbage expected DBs all fail by name, and positive controls pass. Without `--snapshot`, a 0-byte or emptied DB is called healthy (F4). |
| Known good data and recoverable copies | PASS | k1, k4, k9: every replaced file is kept as `NAME.pre-restore-<sid>-<run>`, and a repeat restore keeps both earlier copies. |
| Lock all recovery branches / concurrency | PASS | k9: 6 rounds x 8 concurrent restores (and 5 x 6 rounds in `raw/k9-race-stability.txt`) with exact values, live values kept and no debris. k12 external flock. |
| Clean control, unseen case, safe recovery | PASS | Fixtures include WITHOUT ROWID, BLOB, NULL, unicode, 1e300, index, trigger and WAL. Unseen cases: `raw/adversarial-candidate.txt` (17). |
| Original 84 tests preserved | PASS | `discover -p 'test_[!g]*.py'`: 84 OK. G03: 30 OK. Full: 114 OK on 3.12 (`raw/full-suite.txt`). |

## Operational depth (`raw/operational-candidate.txt`)
- The documented drill `--simulate-crash-after N` was run at every N (1 to 4; at N=5 the restore completes). Health fails before recover and is ok after, values are the snapshot's, the live copy is kept and there is no debris.
- External `kill -9` of restore at random times, 60 rounds (window measured against a 0.034 s restore): 36 killed mid-run (28 recovered to live, 8 to snapshot) and 24 finished. 0 problems.
- External `kill -9` of `recover` after a drilled crash, 60 rounds: 38 killed mid-recover. A second recover always converged and health was ok. 0 problems.
- Scale, 8 DBs x 50,000 rows: snapshot 0.6 s, verify 0.3 s, restore 3.4 s, values exact.
- Superseded run with too wide a kill window (only 4 of 40 kills landed): `raw/operational-candidate-run1-wide-window.txt`.

## Fresh caller (`raw/fresh-caller.txt`)
`env -i` with a new HOME (7 env vars), a copy of the tree without `.git`, and `python3` shimmed to 3.12.14. Only the commands in `sqlite-recovery.md` were used.
- The first documented command fails because `snapshots/` must already exist (F6, `raw/fresh-caller-run1-doc-gap.txt`). With the single deviation `mkdir -p snapshots`, the rest of the flow works:
  - verify and health pass.
  - After an edit, health fails and the dry run plans exactly the 2 live-only rows (one updated, one inserted).
  - Restore without `--confirm` refuses and prints the id. With `--confirm` it restores exact values and keeps the old file.
  - The drill fails health, and `recover` completes with both earlier copies kept.

## Python and SQLite matrix (requested addition)
At the exact commit 7c63297 in the isolated worktree (`raw/pyversions-matrix.txt`):

| Interpreter | SQLite | G03 tests | Full suite |
|---|---|---|---|
| /usr/bin/python3 3.9.6 (Xcode CLT) | 3.54.0 (Apple /usr/lib/libsqlite3) | 29/30, FAIL `test_wal_source_and_sidecars_are_handled` | 113/114, same single failure |
| uv 3.11.16 | 3.53.1 bundled | 30/30 | 114/114 |
| 3.12.14 (install-env and uv) | 3.53.1 bundled | 30/30 | 114/114 |
| uv 3.13.15 | 3.53.1 bundled | 30/30 | 114/114 |

**Conclusion:** this is a G03 portability defect tied to the SQLite library build, not to Python 3.9 APIs, and not an interaction with other candidates. It reproduces in a clean worktree of the candidate alone, and on 3.9.6 the full suite fails only this one test. Evidence in `raw/sqlite-library-probes.txt`, from stdlib-only probes with no candidate code:
- `src.backup(dst)` followed by `PRAGMA journal_mode=DELETE` on the copy leaves `copy.db-shm` behind on SQLite 3.54.0, with both `isolation_level` settings. No `-shm` is left on 3.53.1.
- A `?mode=ro` open of a WAL database with no `-shm` on disk fails with `SQLITE_CANTOPEN` (rc 14, "unable to open database file") on 3.54.0. 3.53.1 instead creates `-wal`/`-shm` and reads fine.
- Both 3.54.0 behaviours are identical when Python **3.12** drives `/usr/lib/libsqlite3.dylib` through ctypes. That rules out the Python version.

## Findings

**F1 (P1): user tables named `sqlite?*` are excluded from all value comparison.** `_digest` uses `name NOT LIKE 'sqlite_%'`, which hides legal user table names such as `sqlitedata`, `SQLiteLog` and `sqlite1` (the `_` wildcard plus LIKE's ASCII case folding; true `sqlite_` names cannot be created by users). If only such tables changed, `health --snapshot` reports ok and `restore --confirm` reports "nothing changed" with exit 0, leaving the changed values in place. This is a silent false success on the core acceptance item. Snapshot integrity is unaffected, because the whole file is hashed. The repro is `oracle/m03_finding_repros.sh` F1 and the observed output is in `raw/finding-repros.txt`:
```
health: ok / healthy: app.db match snapshot ...            [exit 0]
restore: ok / every database already matches snapshot ...; nothing changed   [exit 0]
sqlitedata after restore: [('plan', 'LIVE-CHANGED')]   SQLiteLog rows: [(0,)]   (snapshot had GOOD / 1)
```
Fix direction: `NOT LIKE 'sqlite\_%' ESCAPE '\'` (SQLite reserves the `sqlite_` prefix case-insensitively, so the case folding is correct once `_` is escaped). See `oracle/proposed-fix.patch`.

**F2 (P2): `PRAGMA user_version` and `application_id` are not compared.** A header-only change (as made by migration tools) gives health ok and restore "nothing changed", and the values stay at 9/77 instead of the snapshot's 0/0. The docs promise a skip only when "values, schema and integrity already match". The fix folds both pragmas into the schema digest (same patch).

**F3 (P2): on stock macOS `python3` (3.9.6, Apple SQLite 3.54.0), WAL databases cannot be snapshotted usably.** It fails safe: there is no data loss and refusals happen before writes. But the recovery path for WAL databases is unusable, and health gives false negatives. The docs say "Stdlib Python 3.12" but every example runs `python3`, there is no version or library check, and on a stock Mac `python3` is 3.9.6. The repro is `oracle/m03_finding_repros.sh` F3, run with `/usr/bin/python3`:
- (a) Quiescent WAL DB, with no sidecars: `snapshot` gives "refused: app.db could not be read as SQLite: unable to open database file", exit 2. `health` reports "app.db: unreadable as SQLite", exit 1.
- (b) WAL DB with a live writer (the failing G03 test): the snapshot directory holds `app.db app.db-shm manifest.json`. `verify` then fails with "snapshot contains entries not in its manifest: app.db-shm" (exit 1), and restore refuses.
- Control: the same command on 3.12 gives a snapshot with exit 0.

Fix direction:
- After `dst.close()` in `_snapshot_locked`, remove `-wal`/`-shm` that belong to the freshly made copy inside the private `.partial` directory, before hashing.
- For read-only source opens, fall back when `SQLITE_CANTOPEN` is raised on a WAL DB without `-shm` (for example, a private copy opened immutable, or a non-`ro` open under the dataset lock).
- Or refuse at start-up with a clear message when the runtime is outside the supported Python/SQLite.
- Either way, add this matrix to CI.

**F4 (P3): health without `--snapshot` calls a 0-byte or emptied expected DB healthy.** `: > ds/app.db; health ds --expect app.db` gives "health: ok", exit 0, and so does dropping every table. Only `--snapshot` checks content. Either document that, or require at least one user table or a non-empty file.

**F5 (P3): `health --snapshot` raises a traceback on a manifest entry with no `tables` key** (KeyError at sqlite_recovery.py line 467, exit 1). `verify` and `restore` refuse the same snapshot cleanly. Health should validate the manifest like verify does.

**F6 (P3, docs): the first documented command fails on a fresh checkout.** `snapshot data/ --out snapshots/2026-10-18` is refused with "snapshot destination parent must be an existing real directory" (exit 2). Add `mkdir -p snapshots` to the doc, or create the parent.

**F7 (P4, cosmetic):**
- `--lock-timeout nan` is accepted and acts as 0. The validation `<= 0 or > 600` lets NaN through, and the message prints "nans".
- Health on an exclusively locked DB waits a fixed 5 s, with no `--lock-timeout`, then says "unreadable as SQLite (database is locked)" instead of "busy".

**Note (not a finding):** health is a normal SQLite reader, so on a WAL database it can create or refresh `-shm` (and `-wal`) in the dataset. The docs list sidecar creation only for snapshot and restore. My first k3 held health to the dry-run byte-identical rule. That was an oracle over-reach, kept in `raw/oracle-candidate-run1-k3-overreach.txt`. The database and other files stay byte-identical. Consider adding health to the docs' sidecar sentence.

**Note:** on a case-insensitive filesystem, `--expect App.db` matches `app.db` (a05). This is acceptable but worth stating if "exact" is meant literally.

## Oracle teeth (`raw/oracle-teeth.txt`, final oracle v3, 12 checks)

| Subject | Result | Caught by (beyond k10, which the candidate also fails) |
|---|---|---|
| candidate | 11/12 REJECT | k10 only (F1) |
| positive control: candidate plus `proposed-fix.patch` | **12/12 ACCEPT** | (shows the oracle is satisfiable) |
| stub no-op (claims ok, writes nothing) | 0/12 REJECT | all |
| stub naive copier | 1/12 REJECT | k1, k2, k4, k5, k6, k7, k8, k9, k11, k12 |
| 15 mutants of sqlite_recovery.py | **14/15 caught** on a check the candidate passes | delete_recoverable_copies k1/k4/k5/k9/k11; dry_run_restores_when_confirmed k3; follow_symlinks k8; health_ignores_journal k4; health_missing_ok k8; no_confirm_needed k2; no_dataset_flock k9; no_dataset_lock_at_all k9/k12; no_extra_member_check k2; recover_always_forward k4; recover_noop k4/k5; skip_snapshot_verify k2; skip_when_counts_match k11; unbounded_lock_wait k7 |
| survivor `no_staging_journal` | survives | Equivalent under the docs: journaling a fully staged restore as "swapping" leads to roll-forward, which the docs allow. The builder's oracle and tests also miss it. |

Rejected and superseded oracle evidence is kept:
- `raw/oracle-teeth-v1-superseded.txt`: 4 mutants were caught only by k10. That led to k11, k12 and the recover dry-run decision check in k4.
- `raw/oracle-teeth-v2-superseded.txt` and `raw/k9-race-stability.txt`: the single-round k9 missed a racy mutant, which led to 6 rounds plus a debris check. The candidate is clean across 30 rounds.
- `recover_always_forward` gives correct data because `_finish` re-hashes and rolls back. It is caught by its wrong `recover --dry-run` preview.

## Builder's evidence against the same teeth
- **Builder oracle** `examples/capabilities/G03/recovery_oracle.py` (`raw/builder-oracle-vs-teeth.txt`): candidate 11/11, positive control 11/11. It rejects all four stubs (its own two and mine), but **accepts 6 of 15 mutants**: follow_symlinks, health_ignores_journal, no_dataset_lock_at_all, no_extra_member_check, no_staging_journal and recover_always_forward. It has no check for F1, F2 or F3.
- **Builder tests** `tests/test_g03_capability.py` (`raw/builder-tests-vs-mutants.txt`): candidate 30/30, positive control 30/30. They **miss 2 of 15**: `dry_run_restores_when_confirmed` (a real dry-run safety bug: `--dry-run --confirm` performs the restore) and `no_staging_journal`.

## Limitations
- Self-validation by the same bot; an independent reviewer is still required.
- Single host: macOS arm64 on APFS, which is case-insensitive. No Linux, no case-sensitive FS and no network FS. In-process SIGKILL injection patches the stdlib in the candidate process. External kill rounds are random with fixed seeds.
- No power-loss or fsync durability test (`kill -9` does not drop the page cache).
- The SQLite 3.54.0 behaviour was characterised only through Apple's build. Whether upstream 3.54.0 behaves the same was not tested.
- The proposed patch is a demonstration that passes all three evidence sets. It was not reviewed for F3 and was not applied to the candidate.

## Files
- `oracle/`:
  - `m03_oracle.py`, `inject/sitecustomize.py`, `stubs/`, `make_mutants.py`, `run_teeth.sh`, `run_builder_tests_vs_mutants.sh`
  - `m03_adversarial.py`, `m03_operational.py`, `m03_fresh_caller.sh`, `m03_finding_repros.sh`
  - `m03_py39_wal_repro.sh`, `m03_wal_backup_probe.py`, `m03_wal_ro_steps_probe.py`, `m03_libsqlite_probe.py`, `m03_libsqlite_ro_probe.py`
  - `tmo.py`, `proposed-fix.patch`
- `raw/`: every run log, including the rejected and superseded runs named above.
- `MANIFEST.sha256`: sha256 of every file in this directory except itself.
