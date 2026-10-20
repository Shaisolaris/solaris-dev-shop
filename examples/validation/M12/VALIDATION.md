# M12 first pass: G12 day 2 daily integration, with r2 repair (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G12. This is self-validation, not independent review.

- Candidate: G12 r1 `2718b1ff3831696ad9630982ebb5225a8a3719c9` on review/grok-g12-daily-integration.
- Repair: G12 r2 `e187297432e1bfb1dc53c8f52568a7969b9e5147`, a fast-forward of four commits, for the P2 below.

## Verdict
PASS after repair. r1 had one P2. r2 fixes it. One P4 in the shared tool and one disclosed probe miss remain.

## Method
Same as M06: `oracle/mdaily_probe.py` (H1 plan heads current, H2 plan commits in HEAD, H3 clean merges, T0 to T4
tool teeth on a clone, X1 cross-checks), `oracle/m42_union.py` on the new merges, fresh-clone `--run all` with
root's acceptance files on Python 3.9.6, G12 tests, integration oracle and controls and cross-checks on four
Pythons, and the full suite on fresh clones on four Pythons.

## Results
- **Probe:** 8/9 on r1 (H1 fails: G04 155fc33 vs e9fa278, G05 3056378 vs 04b3cf2). 8/9 on r2: H3 flags merge
  4582f4e, which has one hand-resolved conflict (below). All tool teeth rows pass on both.
- **Union:** 99b6654 changes no file on both sides. 4582f4e: handoff.py union OK; handoff-work-orders.md reports
  three lost lines, which are the two versions of the exit 2 line rewrapped into one. A whitespace-normalised
  phrase check finds all eight reasons from both sides (results/union-check.txt).
- **Live --run all at r2:** VERDICT INTEGRATED, rc 0, every run rc 0, clone clean after.
- **Four Pythons at r2:** G12 tests OK, integration oracle 13/13, naive 1/13, no-op 0/13, cross-checks clean.
- **Full suite:** 261 OK on four Pythons (1 skipped on 3.11+). Browser 0.
- **Binding:** remote head equals e187297; patch equals a regenerated diff; manifest matches (raw/binding-verify.txt).

## Findings
- **P2-1 (fixed in r2): the day 2 stack carried G04 r2 and G05 r2, both with known P2s** (M04 r2: an owner change
  on a delivered revision delivered it twice; M05 r2: an expired waiver kept a closure current). r2 merges G04 r3
  and G05 r3. The tool cannot see this, because it checks the plan against HEAD, not against current heads.
- **The restack exposed a cross-goal interface change, now handled.** With G04 r3 merged and the r1 cross-checks,
  x1 and x2 failed (results/cross-checks-at-0f436c6.txt): they re-ran revision 1 under the new owner after a G07
  transfer, which G04 r3 correctly refuses. r2 moves them to the documented flow (reissue as revision 2) and adds a
  test that x1 catches a G04 that would deliver the same revision twice. This is not a defect in G04 or G07.
- **P4-1 (tool): a resolved_overlaps reason over 300 characters is refused as "expected a non-empty string".**
  Fails closed, but the message does not say the reason is too long.
- **OBS:** H3 is a strict check; the one non-clean merge is reviewed above.

## Files
- oracle/: mdaily_probe.py, m42_union.py
- results/: probes on r1 and r2, union check, cross-checks at 0f436c6, live run, four-Python table, suite matrix
- raw/binding-verify.txt
