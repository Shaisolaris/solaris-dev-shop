# M08 r2: Grok self-validation of G08 r2 (local deploy, per-target lock and gated repeat deploy)

This is Grok self-validation, not independent review. The same agent family built and validated it.

- Candidate: G08 r2 `ddebe98707219aa2638cd424777b1255413d9ceb` on `review/grok-g08-deploy-preflight`, a fast-forward
  from r1 `52cb49db230ac95e28c2e880176335ccb097a2a6` (scored by M08 v4 `dfc25e5`: P3-1 concurrent deploys, P3-2
  repeat deploy success receipt, P4-1 reusable rollback approval).
- Prerequisites unchanged: G03 r3 `d4d98f2`, main `02ba9c5`. Nothing superseded. Patch sha256 equals
  `git diff 52cb49d ddebe98`; manifest 7/7, 0 mismatches (`raw/binding-verify.txt`).
- The candidate was never modified; every run used an rsync copy in a private temp dir. week-grok before/after
  records are identical. Pass window 03:05 to about 03:35 PT, 2026-10-19.
- The fix is the builder's design, not from a Grok patch (M08 v4 had no P1/P2 and supplied no patch).
- /tmp/m08-pub belongs to the other writer and was not touched.

## Verdict: PASS with one carried residual. P3-1 and P3-2 are fixed; P4-1 (approval reuse) remains.

| Instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| G08 tests / full suite | 12 OK / 144 OK | same | same | same |
| builder oracle | 18/18 | 18/18 | 18/18 | 18/18 |
| M08 oracle (v4 instrument, regression) | 10/10 | 10/10 | 10/10 | 10/10 |
| controls on the M08 oracle: naive / noop | 4/10 / 3/10 | | | |
| new lock and repeat probe `m08r2_lock.py` | 8/8 | | | 8/8 |

## Concurrency drill (rerun of my M08 instruments, 3.9.6 and 3.13.15)

- `m08_race_sweep.py`: 124 synchronized pairs per interpreter (r2 twice from r1, r3-broken twice from r2, 0 to 60
  ms offsets). 0 inconsistent, 0 tracebacks, r2 live every time. Exit pairs (0,0) when serialized (the second
  run is a gated repeat that is approved and healthy), (0,2) and (1,2) when the lock refuses, (1,1) when
  serialized r3 failures. On r1 the same harness found damaged data and double deploys.
- `m08_race_followup.py`: case A 27 trials, case B 14, 0 inconsistent after the documented recovery.
- `m08_race_rollback.py`: no damaged case in 40 trials (r1 found one).
- `m08_repeat_unhealthy.sh` (the v4 P3-2 probe): with live data moved to schema 3, a repeat deploy of r2 now exits 2
  both with approval ("refused: r2 is already live but health failed; nothing changed") and without. On r1 both
  exited 0.

## New lock and repeat probe (`oracle/m08r2_lock.py`, expectations from local-deploy doc and G08 README)

- L01 deploy vs rollback race (12): every pair consistent, the loser refused by the lock or serialized.
- L02 recover vs recover (6): one recovers, the other is refused, all (1,2) as the journal is gone.
- L03 an outside process holds the target lock: deploy, repeat deploy, rollback and recover exit 2 in about 0.03 s
  with the lock message and an identical tree; `preflight` and `status` still run (the doc: "take no lock and
  write nothing").
- L04 the same target reached through a symlink alias: serialized, exactly one deployed event.
- L05 SIGKILL of a lock holder: no stale lock; `recover` runs and restores r2.
- L06 a SIGSTOPped holder inside the lock: a second deploy is refused at once (non-blocking), one r2 event in total.
- L07 repeat gate: no approval, the r1 approval, or a rollback approval used as a deploy approval are all refused
  with exit 2 and an identical tree; approved and healthy gives 0 and changes nothing.
- L08 repeat after an outside schema change: exit 2 with and without approval, tree identical.
- Harness errors (disclosed, v1 kept as `oracle/m08r2_lock_v1.py`, `results/kept/lock-v1-3.9.6.json`): v1 L03 ran
  `preflight` of the already-live r2, which fails its rollback check by design (rc 2 without the lock too; checked
  directly); v2 preflights r3-broken. v1 L06 sent SIGSTOP after a fixed 0.12 s, before the first deploy had taken the
  lock; v2 stops it once its journal exists. Both were fixed before scoring.

## Teeth (41 builder mutants, unchanged, scored by M08 oracle + lock probe; lock rows by core result only)

- 3.13.15: 39/41. 3.9.6: 39/41. Identical kill sets.
- All 8 r2 mutants (deploy_unlocked, rollback_unlocked, recover_unlocked, lock_failure_ignored, lock_released_early,
  repeat_unchecked, repeat_ignores_health, repeat_ignores_authority) are killed, and only by the new r2 probe rows.
- Survivors: `no_snapshot_verify_EQUIV` (builder labels it equivalent; builder tests pass on it) and
  `required_files_empty_ok` (non-equivalent: the builder tests fail on it; as in v4, my empty-file case is refused
  earlier by the digest check).

## Fresh caller

env -i, new HOME, README commands only, on 3.9.6 and 3.13.15: identical, all exit codes as the README states, final
live r1 with schema 1 and the original totals, no bytecode left. Harness fix (disclosed): the copied v4 script wrote its
demo world at a fixed `/tmp/m08-fresh/g08-demo`; r2 uses its own temp dir (the stray dir from my first r2 run was mine
and was removed; nothing of the other writer's was touched).

## Findings

- P3-1 (v4, concurrent deploys): fixed. Sweep, follow-ups and L01 to L06.
- P3-2 (v4, repeat deploy success receipt without health or approval): fixed. Repeat probe and L07, L08.
- P4-1 (v4, rollback approval reusable): carried, not addressed by r2 (D07b: the same rollback approval is accepted
  again after a redeploy). The handback lists it as not done.
- OBS: the lock refuses rather than waits, so a second operator gets exit 2 and must retry; this matches the doc.

## Layout

`oracle/` (M08 instruments, lock probe and v1, teeth, builder mutants copy), `scripts/` (runners), `results/`
(builder, oracle, controls, lock, race, fresh, teeth, kept), `raw/` (binding verify, week-grok before/after).
