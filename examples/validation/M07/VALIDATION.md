# M07: Grok self-validation of G07 0d6a78d (fleet registration without duplicate ownership)

Grok self-validation, not independent review. Written by Grok Bot on 2026-10-19 between 01:32 and 01:45 PT. The candidate was not modified, and no proposed fix is included, because there is no P1 or P2.

## Verdict: PASS with residuals (P4 only)

## Binding and prerequisites (raw/binding-verify.txt)
- Candidate 0d6a78d56cdb4c3b8d87ed25bb41704e99bc5382, resolved through the GitHub API; it is the remote head of review/grok-g07-fleet-registration.
- Its one parent is exactly G04 314b4dbf980437cf14bc32438117e5b5b777f942, as the handback states. G04's parent is exactly G02 bbe682b28e96296723826c1f113e138ccc39c530. Neither has been superseded: both branch heads are unchanged.
- G04 was validated as M04 (PASS with residuals, commit 1628e6d). I did not re-validate G02 here.
- G07.patch equals `git diff --binary 314b4db 0d6a78d` (sha256 0449d373...): 18 files, +1038/-9. All 18 manifest entries match, and the manifest set equals the diff set.

## Findings
- **P4-1, `__pycache__` left in the source tree.** A fleet-bound G04 order loads registry.py with `spec_from_file_location` and `exec_module`. Python 3.11.16, 3.12.14 and 3.13.15 then write `employees/infrastructure/fleet-provisioner/__pycache__/` into the repo; this is oracle row C21 and the fresh caller on 3.13.15.
  - The same run also leaves `employees/product-project/project-onboarding/__pycache__/`. That comes from the G02 activation loader that G04 already had; the G07 diff does not touch it.
  - Apple's /usr/bin/python3 3.9.6 caches bytecode under ~/Library/Caches/com.apple.python (its `sys.pycache_prefix`), so 3.9.6 shows nothing.
  - `__pycache__/` is gitignored. The builder flagged this in the G08 handback, and G08 already uses the fix (bytecode writing disabled during the import).
- **P4-2, case-variant identity.** An identity file with machine_id "MINI-7F3A-0001" registers as a second machine next to "mini-7f3a-0001" (C06b), because machine ids are matched exactly and the pattern accepts upper case. The doc says an identity file is a declaration, not attestation, but it does not say ids are case-sensitive.
- **P4-3, temp file after SIGKILL.** After a SIGKILL during a change, a `.reg-*.tmp` temp file is sometimes left in the fleet root and never cleaned up. Seen in 1 of 4 runs of 30 kills (C11b, 3.12.14). Correctness is unaffected: the registry and claims stayed consistent in every trial.
- **Observations, no finding.**
  - A retired machine can be registered again under a new alias (C16b). This matches the tool's message and the doc.
  - A hand edit of FLEET.md is not detected, but claims never read FLEET.md and the next change re-renders it (C12b).
  - A claim takes the registry lock and so creates `.registry.lock` in an existing root.
  - The second claim check under the worker lock does not hold the registry lock while the order delivers. A transfer during delivery is therefore not blocked. The doc only promises the two checks.

## Oracle (oracle/m07_oracle.py, v3; results/oracle/)
22 core rows, with expectations from fleet-registration.md, handoff-work-orders.md and G07/README.md:
- **Clean control:** C01.
- **Concurrent registration races:**
  - C02: one machine under 8 aliases.
  - C03: 8 machines on one alias.
  - C04: a 6-way retry storm on one request id gives one commit.
  - C05: 8 transfers from one view; exactly one wins and the epoch becomes 2.
  - C18: 40 machines from 4 concurrent registrars, each retrying and trying a duplicate alias.
- **Wrong machine:** C06 covers a same-hostname impostor, another registered machine, and a missing or garbled identity file. All are refused and the files are unchanged.
- **Epoch and stale owner:**
  - C07: old owner, new owner at the old epoch, old owner at the new epoch, a future epoch, three stale transfers, a self-transfer and an old-owner re-register are all refused, files unchanged.
  - C08: after A to B to A, epoch 1 stays stale and epoch 3 is admitted.
- **Crash mid-change:**
  - C09 and C10: the `--fail-at` drills keep the prior owner or settle exactly once.
  - C11: a real SIGKILL at a random point, 30 times, with the invariant checked and a retry after every kill.
- **Hand-edit detection:**
  - C12: an edit to registry.json is refused by claim, status, transfer and register; restoring the bytes works again, and a whitespace-only edit is still detected.
  - C13: deleting ops.jsonl is refused.
  - C14: a garbage ops line stops everything, while a torn tail is cut.
- **Request ids and retire:**
  - C15: reusing a request id for a different change is refused, and an exact repeat is a no-op.
  - C16: a retired machine takes no work, its alias cannot be reused, it cannot be transferred, and a stale retire is refused.
- **Invalid input:** C17 sends 7 invalid inputs, including a missing root, which is not created. Each is refused, then a positive control succeeds.
- **G04 runner gate:** C19 refuses an impostor, a missing identity, a wrong epoch and an order after a transfer, with no files created. The right machine delivers once, and a plain order is unchanged.
- **Registry-path confinement:** C20 refuses `../`, an absolute path, an empty path, a NUL byte, and a symlink inside the order folder that points out (resolved, then refused). A registry folder inside the order folder works.
- **Bytecode leftover:** C21 checks for `__pycache__` without PYTHONDONTWRITEBYTECODE.
- **Static:** C22 finds no subprocess or network import.

| Interpreter | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| My oracle | 22/22 | 21/22 (C21) | 21/22 (C21) | 21/22 (C21) |
| Builder G07 tests | 11 OK | 11 OK | 11 OK | 11 OK |
| Full suite | 155 OK | 155 OK | 155 OK | 155 OK |
| Builder registry_oracle | 17/17 | 17/17 | 17/17 | 17/17 |

- **Controls (3.9.6):** the builder's naive_registry scores 4/21 core (it passes C01, the lucky race C05, C11 and C22). noop_registry scores 1/20 (C22 only). One row crashed each control harmlessly, so it is not counted.
- **Fresh caller** (oracle/m07_fresh_caller.sh: env -i, a new HOME, a python3 shim, then only the README commands plus its work-order sentence): every exit code matched the docs on 3.9.6 and 3.13.15, and the ledger has 1 line. On 3.13.15 the two `__pycache__` folders above were left behind (P4-1).

## Adjudication and harness errors (disclosed)
- **v2 cleanup bug:** the v2 run cleaned up `/tmp/m07o-*` globally, which deleted the folders of my own parallel runs. That caused false FAILs (C06, C11, C18, C19, C20). Those logs are kept in results/kept/v2-shared-tmp-cleanup-bug/. v3 uses a private parent folder for each run, and every result above is from v3.
- **C17 detail:** v1 recorded the C17 "unchanged" detail after the positive control. Fixed in v2; the row result is the same.

## Teeth (results/teeth-*, results/teeth-tally.txt)
- I used the builder's 31 G07 mutants (oracle/builder_mutants_g07.py, copied unchanged) and scored them with my oracle (oracle/teeth_m07.py) on 3.11.16 and 3.13.15.
- My oracle kills 28/31 on both versions, with identical kill sets.
- I count kills excluding the OBS row C11b, because it is timing-dependent. In the raw 3.11.16 run, C11b was the only row that "killed" retired_alias_reuse_ok and mid_any, and that did not repeat on 3.13.15.
- **Survivors:**
  - handoff_fleet_extra_keys_ok: my oracle has no row for unknown keys in a fleet block.
  - retired_alias_reuse_ok: same machine, same alias, same owner after retirement; my oracle did not try it.
  - mid_any: no malformed machine_id row.
  - Each of the three fails the builder's G07 tests on 3.13.15, so none is equivalent; these are gaps in my oracle.

## Hygiene
- The week-grok before and after records are identical (raw/weekgrok-*.txt; listings kept outside this dir).
- The candidate worktree /tmp/m07-eval stayed clean (empty status, no pycache), because my runs set PYTHONDONTWRITEBYTECODE and C21 ran on a copy.
- No installs and no network beyond GitHub API reads.

## Not done
- Teeth ran on 3.11.16 and 3.13.15 only.
- The fresh caller ran on 3.9.6 and 3.13.15 only.
- I did not run a network-folder registry (the doc says it is unsupported) or real machines.
