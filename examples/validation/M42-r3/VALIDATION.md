# M42 r3: validation of G42 r3 9d844d2, final integration (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G42. This is self-validation, not independent review.

- Candidate: G42 r3 `9d844d22099cbf5c385963578c67c789951e8263` on review/grok-g42-daily-integration, a
  fast-forward of r2 `956792e` (M42 r2: PASS, two P4 observations).

## Verdict
**PASS after repair.** One P2 and one stale-stack gap were found and fixed in this round. No P1, P2 or P3 is open.
The two M42 P4 observations stand.

## Findings
- **P2-1 (closed): stale stack.** On r2, the probe scored 7/9 (results/probe-956792e.txt):
  - H1 failed: the plan pinned G02 8fdae9c, G04 155fc33 and G05 3056378, while the remote heads had moved on.
  - Most build goals were not stacked at all.
  r3 stacks all 31 build goals at their current remote heads. H1 passes, with every plan commit equal to its goal's
  remote head at the time of the run (results/remote-heads-at-start.txt).
- **P2-2 (closed): G01/G05 fixture interface defect.** The first r3 tree, 4ef54ff, was NOT_INTEGRATED. G05 oracle
  o13, tests.test_g05_capability and the suite failed on all four Pythons (results/first-tree-live-run-4ef54ff.txt).
  - Cause: G01's fixture runner rejected G05 r3's closure fixture keys.
  - Fix on the G05 side: G05 r4 1b840cd (validated by M05 r3, PASS).
  - Fix on the G01 side: 9d844d2 adds subject_revision and verified_revision to the closure kind's keys. The two new
    Interfaces tests fail before the fix and pass after it (results/interfaces-before.txt, interfaces-after.txt).
    Unknown keys are still rejected.
- **OBS: hand-resolved merges.** H3 lists five merges that are not clean:
  - 3ed5aec, carried from r1;
  - 050f026, ecd7dad, f97a0bf and 13cf2bb, new in r3.
  The union check (results/union-check.txt) shows every line from both parents kept, with two explained exceptions:
  - handoff-work-orders.md: the exit 2 line is rewrapped, and each reason is still present (checked by phrase).
  - examples/capabilities/G19/boundary_oracle.py at 3b5435c: the G19 h1 copy, which is newer, replaces two except
    lines from the accepted copy.
- **OBS:** G22 h2's history includes ac2b2d0, whose test lines named the owner. It is fixed at 29cd7fc and the tree
  is clean. ac2b2d0 is now reachable from this branch too. This is disclosed in the G42 r3 handback.
- **P4-1, P4-2 (unchanged from M42):**
  - x3 requires the security-auditor script list to be exactly boundary_probe.py and provenance_check.py.
  - x4 checks that the legal-advisor contract text contains the two test paths, not the wiring.

## Results at 9d844d2
- **Probe:** 8/9. H1, H2, T0 to T4 and X1 pass. H3 is the OBS above.
- **Live --run all:** fresh clone, root's acceptance files, Python 3.9.6. VERDICT INTEGRATED, rc 0, clone clean after.
- **Four Pythons (3.9.6, 3.11.16, 3.12.14, 3.13.15):** G42 tests OK, integration oracle 13/13, naive 1/13, no-op
  0/13, cross-checks clean.
- **Full suite on fresh clones:** 811 OK on all four (6 skipped on 3.9.6, 2 skipped on the others). Browser launches: 0.
- **Binding (raw/binding-verify.txt):**
  - The remote head equals 9d844d2.
  - G42-r3.patch equals a regenerated diff of 956792e..9d844d2.
  - The 496-file manifest matches. It was regenerated with unquoted paths so that the G34 non-ASCII fixture name is
    counted.

## Files
- oracle/: mdaily_probe.py, m42_union.py
- results/: probes on r2 and r3, first-tree live run, live run, four-Python table, suite matrix, union check,
  interface tests before and after, remote heads listing
- raw/binding-verify.txt
