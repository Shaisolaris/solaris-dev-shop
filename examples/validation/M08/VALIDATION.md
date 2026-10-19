# M08 validation of G08 (Grok self-validation, NOT independent review)

Grok self-validation by the same bot that built G08. This is not independent review and not manager acceptance.

- Candidate: G08 `52cb49db230ac95e28c2e880176335ccb097a2a6` on `review/grok-g08-deploy-preflight`. Parent is exactly G03 r3 `d4d98f2180ed9b92fd058a2350285f60f83b877d`. main stays at 02ba9c5.
- Window: 01:36 to 01:52 PT, 2026-10-19. Interpreters 3.9.6, 3.11.16, 3.12.14, 3.13.15. Candidate at `/tmp/m08-eval`, not modified by this pass.
- Instruments: `oracle/run_all.sh` reached ALL-DONE; race follow-ups and repeat-unhealthy probes kept under `results/race/` and `results/repeat-unhealthy-3.9.6.txt`. First full matrix preserved under `results/kept/v3-run/`.

## Verdict
PASS with residuals. No P1 or P2 against the single-deployer contract the candidate claims. One P3 (concurrent race can leave settled-looking live with damaged data; recover/rollback cannot heal it) and one P4 (repeat deploy of the live artifact is an unconditional noop, including with no approval, even after live health was broken). Concurrent deployers are disclosed as out of scope in the G08 handback.

## Prerequisites (raw/binding-verify.txt)
- Handback: G03 r3 `d4d98f2180ed9b92fd058a2350285f60f83b877d` on `review/grok-g03-recovery`.
- Candidate parent is exactly d4d98f2. G03 branch head still d4d98f2 at verify time.
- `git diff --binary` sha256 matches G08.patch (fd66c679...); MANIFEST 32/32 OK; manifest set equals diff set (32 files, +1144/-3).
- G03 r3: Grok M03 r3 PASS (commit 1020f11 on review/grok-m03r3-validation).

## Disclosures
- Builder and validator are both Grok.
- Oracle `oracle/m08_oracle.py` written after G08 landed from M08.md, local-deploy-preflight.md and G08/README.md. Controls use the builder's naive and noop tools via `--tool`.
- Teeth use the BUILDER's 33 mutants (`oracle/builder_mutants_g08.py`), scored by my oracle. Timing-dependent OBS rows D06 and D10 are excluded from kill scoring (see teeth_m08.py FLAKY).
- Harness notes: earlier oracle shapes kept under `results/kept/oracle-v*.json` and the full v3 matrix under `results/kept/v3-run/`.
- No installs, no network, no paid calls. Race probes deliberately exercise the disclosed no-lock concurrent path.

## Results
| Check | Result |
|---|---|
| Binding | diff sha256 fd66c679... == G08.patch; MANIFEST 32/32; set equality OK |
| Builder suite, 4 interpreters | G08 10 tests OK; full suite 142 OK; builder oracle 16/16 |
| Grok oracle, 4 interpreters | core 9/9 PASS identical on 3.9.6, 3.11.16, 3.12.14, 3.13.15. OBS: D06, D10, D10_timing |
| Controls | noop 3/9 core; naive 4/9 core (fail usefully) |
| Fresh caller (3.9.6, 3.13.15) | deploy/upgrade/fail-at/recover/rollback paths OK; no `__pycache__` left in the repo copy |
| Teeth 3.11.16 / 3.13.15 | 26/33 and 25/33 kills (logs). Survivors mostly fail builder tests (rc 1); `no_snapshot_verify_EQUIV` is EQUIV (rc 0). See results/teeth-tally.txt |
| Race sweep / followup / rollback-after-race (3.9.6) | See adjudication. Concurrent is out of scope per handback |
| Repeat-unhealthy (3.9.6) | See P4 |
| week-grok | head 02ba9c5 before and after; not modified by M08 |

Row map:

| Challenge | Rows |
|---|---|
| Clean deploy, upgrade, rollback | D01 |
| Refusals exit 2, tree identical | D02 |
| Preflight writes nothing | D03 |
| Crash drills then recover and redeploy | D04 |
| SIGKILL during deploy | D05 |
| SIGKILL during rollback (OBS) | D06 |
| Rollback needs matching approval; reusable | D07, D07b |
| Failed deploy restores release and data | D08 |
| Repeat live deploy is noop | D09 |
| Concurrent same target (OBS) | D10 |
| Static no network/cloud/process | D11 |

## Adjudication
- **Concurrent (disclosed out of scope).** `results/race/followup-3.9.6.txt`: CASE A 4/27 trials end with live=r2, pending=false, data not r2 (user_version 3, totals x100). `recover_rc` null (no pending journal). Next preflight of r2 exits 2. `rollback-after-race-3.9.6.txt`: after such damage, recover exits 0 without fixing data; rollback exits 2; redeploy r2 exits 0 as noop and leaves damaged data. Core single-deployer rows still PASS. Severity P3 residual (heal gap after an out-of-scope race), not P1/P2 against claimed behaviour.
- **Repeat-unhealthy.** After r2 is live, breaking live health makes preflight exit 2, but `deploy` of the same artifact repeats as noop (including with no approval). Matches D09 / documented "already live with this artifact". Severity P4: operators cannot use deploy to repair an unhealthy live that still matches the artifact, and the noop path does not re-check approval or health.

## Findings by severity
- P1: none. P2: none.
- **P3-1 (concurrent race heal gap).** Two concurrent deploys of one target (no lock; handback "Not run / cannot do") can leave live pointing at a prior revision while the database holds a failed upgrade's schema and totals. Status looks settled (pending false). Documented recover does not run; explicit rollback may refuse; redeploy of the live artifact is a noop. Suggested direction (not a patch): a deploy lock, or a forced recover/rollback path that restores data when live health or G03 health fails even if pending is clear.
- **P4-1 (repeat noop ignores unhealthy live and missing approval).** Same-artifact repeat is unconditional. Doc should say health and approval are not re-checked on that path.
- Observation: teeth survivors with builder_tests_rc 1 are killed by builder tests; EQUIV mutant survives both.
- Strengths: refusals keep the tree identical; crash drills and failed deploys restore; rollback approvals bind; static check clean; fresh caller transfers; controls fail usefully.

## Not run
- Real hosts, containers, cloud, DNS, traffic switching (candidate is local-fixture only).
- Teeth on 3.9.6 and 3.12.14 (run on 3.11.16 and 3.13.15).
- Manager or independent acceptance of G08.
