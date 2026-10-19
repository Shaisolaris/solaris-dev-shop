# M03 r3: recheck of the G03 rework r3 "Recovery without data loss"

**Kind:** Grok self-validation (same bot as the G03 builder). Not independent review. An independent reviewer is
still required by the QA2 contract.

**Verdict: PASS** against rework commit `d4d98f2180ed9b92fd058a2350285f60f83b877d` (branch
`review/grok-g03-recovery`, parent `9f2fbbc`, base `02ba9c5`). No P1, P2 or P3 findings; three P4 findings.
- The manifest `grok-output/G03/MANIFEST.sha256` (r3) verified 13/13, and its file set equals the diff file set
  02ba9c5..d4d98f2. `G03-r3.patch` equals the 9f2fbbc..d4d98f2 diff byte for byte (`raw/manifest-verify.txt`).
- All four M03 r2 findings are fixed (R-A to R-D, below).
- The full suite is 132 OK on 3.9.6 (Apple SQLite 3.54.0), 3.11.16, 3.12.14 and 3.13.15 (SQLite 3.53.1). The
  M03 oracle is 12/12 ACCEPT and the builder oracle 18/18 on all four (`raw/pyversions-matrix.txt`,
  `raw/oracle-pyversions.txt`).

Runs were on host macOS (arm64) on 2026-10-18, between 16:15 and 17:05 PT. Run times overlapped with an unrelated
builder job on the same host. The only timing-sensitive check (builder oracle c10) behaved as in r2, see R-C.

## Isolation
- The commit was fetched read-only into the programme repo (`git fetch origin review/grok-g03-recovery`), and
  FETCH_HEAD equals the full SHA. Then `git worktree add --detach /tmp/m03r3-eval d4d98f2...`
  (`raw/fetch.txt`, `raw/worktree-add.txt`). Nothing was cloned onto any other machine.
- The builder's worktree was not written. Branch, HEAD, index hash and status hash are identical before
  (16:15:47 PT) and after (17:05:16 PT), and the status listing is byte-identical.
- Mutants ran in scratch copies. The candidate worktree's `git status` is empty after all runs.
- Interrupted session: the mutation pass was resumed from its own per-subject TSV (resumable runner). No subject
  was run twice into the results, and nothing was published before this commit.

## M03 r2 findings
| r2 finding | r3 result | Evidence |
|---|---|---|
| R-A (P2) health mid-swap creates sidecars, recover refuses, dataset mixed (3.9.6) | **Fixed.** At every kill point 1 to 10, with `health` run between the kill and `recover`, recover ends whole (back for kill@1 and 2, forward after). On 3.9.6, health changed no listing at any point. kill@7 on 3.9.6, the r2 failure, now rolls forward. | `raw/k4-health-every-point-3.9.6.txt`, `-3.12.14.txt` |
| R-B (P4) busy snapshot creates the parent folder | **Fixed.** r2 regression g01 is OK on 3.9.6 and 3.12. The new parent probes: a failed snapshot removes the folder it created and keeps a pre-existing one (empty or not); a successful snapshot leaves only `s1`; two missing levels are refused, with nothing created. | `raw/regressions-*.txt`, `raw/parent-probes-*.txt` |
| R-C (P3) builder oracle accepts `no_dataset_flock` | **Fixed.** Rejected 6 of 6 repeat runs (c16 every time; c10 also in 2 of 3 on 3.12). It is rejected in both teeth runs. | `raw/builder-oracle-no_dataset_flock-repeats.txt` |
| R-D (P4) overstated mutant evidence | **Fixed.** REWORK.md now states the counts, and they reproduce exactly: on the builder's 28 mutants, the tests kill 28/28 on 3.9.6 and 27/28 on 3.12 (r2_f3_copy_keeps_sidecars needs Apple SQLite), the builder oracle kills 25/28 on both, and the M03 oracle 17/28 and 16/28. | `raw/teeth-*.tsv` |

## New evidence for r3
**Mid-swap sweep (`oracle/m03r3_midswap_sweep.py`, `raw/midswap-sweep-*.txt`).** A WAL dataset was restored and
killed at points 2, 3, 5, 7 and 9. Each command below was run against the half-swapped dataset while the journal
exists:
- `health`, `health --snapshot`;
- `snapshot` (new folder and missing parent);
- `restore --dry-run`, `restore --confirm`;
- `verify`, `recover --dry-run`.

Each must change no file name, size, mtime or inode in the dataset (lock file included) and create nothing beside
it. `recover` must then end whole, with both copies kept. **SWEEP OK on 3.9.6 and 3.12** (on 3.12 kill@9 is past
the last rename). This extends the R-A check from health to every command.

**Regression hunt.** r2's g01 to g07 all OK on r3 (3.9.6 and 3.12).

**Fresh caller (`oracle/m03r2_fresh_caller.sh`, unchanged).** env -i, a new HOME, a python3 shim, and the doc's
commands only. On 3.12.14 and 3.9.6 the sequence runs end to end:
- snapshot, verify, health ok, health unhealthy, dry run, refusal without confirm, restore ok, health ok;
- a restore killed with exit 137, health unhealthy, recover ok (forward), health ok against the snapshot.

**Teeth (`oracle/run_teeth_r3.sh`, `raw/teeth-3.9.6.tsv`, `raw/teeth-3.12.14.tsv`).** The 30 mutants are the
builder's 28 (regenerated here with a read-only copy of its generator, `oracle/builder_make_mutants_r3.py`) and two
new M03 r3 mutants that split snapshot's two journal checks. There are four scorers: the M03 oracle (12 core), the
new mid-swap sweep, the builder oracle (18) and the builder tests (48).

| Scorer | 3.9.6 killed | 3.12.14 killed | Survivors |
|---|---|---|---|
| M03 oracle | 17/30 | 16/30 | mostly r2/r3 fix reverts, which it was not written for |
| M03 r3 sweep | 6/30 | 6/30 | (targets mid-swap writes only) |
| Builder oracle | 26/30 | 26/30 | m03r3_no_underlock_journal_check, r2_f3_copy_keeps_sidecars, r2_f3_no_ro_fallback, r3_no_fallback_guard |
| Builder tests | 28/30 | 27/30 | m03r3_no_prelock_journal_check, m03r3_no_underlock_journal_check (+ r2_f3_copy_keeps_sidecars on 3.12) |
| Union | 29/30 | 28/30 | m03r3_no_underlock_journal_check (+ r2_f3_copy_keeps_sidecars on 3.12, an Apple SQLite path) |

Controls: the candidate passes every scorer on both interpreters. The r2 tool (9f2fbbc) is rejected by the
builder oracle (c16, c17, c18), the tests (4 failures) and the sweep (12 writes on 3.9.6, 10 on 3.12). The M03
oracle rejects it only on 3.9.6 (k4, the R-A interpreter).

`r3_no_fallback_guard` is killed only by the in-process tests. From the CLI it is unreachable: both callers of the
fallback are already gated on the journal (health skips opening, and snapshot refuses first). So it is defence in
depth, and equivalent at the CLI level.

## Findings
### S1 (P4, evidence gap): "snapshot is refused before the lock file is touched" is not covered by the tests
`m03r3_no_prelock_journal_check` removes the pre-lock journal check, leaving only the under-lock recheck. A
mid-swap snapshot then still refuses, but it touches `.solaris-recovery.lock` first; the sweep sees the lock file
change at every kill point. The builder tests and the M03 oracle accept the mutant. Only the builder oracle (c17)
and the M03 r3 sweep reject it. The doc and the commit message make this claim explicitly.

### S2 (P4, untested race guard): the under-lock journal recheck in snapshot is not exercised by anything
`m03r3_no_underlock_journal_check` survives all four scorers on both interpreters. Sequentially it is equivalent,
because the pre-lock check refuses first. The recheck matters only if a restore is killed after snapshot's pre-lock
check and before snapshot takes the lock. Without it, snapshot would then read a half-swapped dataset. No test
pauses snapshot in that window. A test that pauses snapshot after its first check (as c16 pauses restore) would
cover it.

### S3 (P4, observation, pre-existing in r1, r2 and r3): snapshot accepts databases that health calls unhealthy
A 0-byte or table-less `app.db` is snapshotted with exit 0 ("snapshot: ok"). A 0-byte file is stored as an empty
4096-byte database with `tables: {}` and integrity ok. `health` on the same dataset reports "empty file (0 bytes),
not a database". Restore still needs `--confirm`, and the plan shows the change, so nothing is lost silently. But
a snapshot taken after a truncation records the damage as a valid restore point. Not a regression, and not
promised either way by the doc.

## Rejected and superseded runs (kept)
- `raw/parent-probes-*-v1-superseded.txt` (`oracle/m03r3_parent_probes_v1_superseded.py`): my v1 assumed 0-byte and
  table-less databases make snapshot fail, so its "failed snapshot" cases never reached the failure path. v2 drives
  that path with a garbage database and reports the 0-byte and table-less behaviour as S3.

## Limitations
- Self-validation by the builder's own bot. The same blind spots are possible.
- One host (macOS arm64, APFS). Linux and other filesystems were not run. Apple SQLite 3.54.0 only for the
  CANTOPEN path.
- Teeth were run on 3.9.6 and 3.12.14 only. The baseline matrix covers 3.11 and 3.13.
- The kill injector is in-process. The race in S2 was reasoned about, not reproduced.
- No proposed fix was written: there is no P1 or P2 finding.

## Files
- `oracle/`: `m03r3_midswap_sweep.py`, `m03r3_parent_probes.py` (v2, plus the v1 copy), `make_mutants_m03r3.py`,
  `run_teeth_r3.sh`, `run_baseline_r3.sh`, `builder_make_mutants_r3.py` (a copy of the builder's generator), and
  copies of `m03_oracle.py`, `tmo.py`, `inject/sitecustomize.py` and `m03r2_fresh_caller.sh` from r2, unchanged.
  The r2 helpers `m03r2_k4_probe.py` and `m03r2_regressions.py` were run from the published r2 folder, unchanged.
- `raw/`: every run listed above.
- `MANIFEST.sha256`: sha256 of every file here except itself.
