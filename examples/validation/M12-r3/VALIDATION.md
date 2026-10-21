# M12 r3 validation of G12 r4 60932f5

- Verdict: PASS. The day 2 stack now pins the newest heads of G04, G05, G07 and G09 (M12 r2 H1 closed). The overlap reasons match the new blobs, and the four new merges are clean. No P1 to P4. One OBS is carried and cannot be closed by a fast-forward.
- This is Grok checking a Grok build, built in the same run by the same agent. Grok self-validation, not independent review. It accepts nothing.

## What is being checked
- M12 r2 validated G12 r3 a245f1f. It left H1 open: the plan pinned G04 e9fa278, G05 04b3cf2, G07 0d6a78d and G09 edfa64d after newer heads existed.
- Since then on review/grok-g12-daily-integration there are four merge commits, one per new head, and 60932f5. The branch moved forward from a245f1f as a plain fast-forward (raw/binding-verify.txt).
- 60932f5 repins plan.json to G04 r4 7ed5f70, G05 r4 1b840cd, G07 r2 f4776bd and G09 h1 1cab0f8. It rewrites the six resolved_overlaps reasons with the new blobs and updates the README. The tool, the tests and the cross-checks are unchanged.

## Probe (oracle/m12r3_probe.py)
Adapted for G12 from the M36 r2 probe written today. It reads git objects and the remote.
- R01: every pin is the current remote head of its goal's branch.
- R02: every pin is an ancestor of HEAD.
- R03: each r3 pin is an ancestor of its r4 pin.
- R04: the r3 head is an ancestor of HEAD.
- R05: every blob a reason names is real, and HEAD's blob is named or accounted for.
- R06: HEAD keeps each candidate's files.
- R07: no file that two unrelated candidates change differently is missing from resolved_overlaps.
- R08: the M12 P4-1 length message still works.
- R09: the tool is unchanged from r3.
- R10: `check --plan` gives INTEGRATED.
- R11: each r4 merge is clean, meaning its tree equals `git merge-tree` of its parents.
- R12 is an OBS (see Residuals).

## Results
- **G12 r3 a245f1f on 3.9.6: 8/11.** Three rows fail there:
  - R01: four stale pins.
  - R05: the old handoff.py and handoff-work-orders.md reasons do not name the HEAD blob.
  - R11: r3 has no r4 merges yet.
  - (results/probe-at-a245f1f-3.9.6.txt)
- **G12 r4 60932f5: 11/11** on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r4-*.txt).
- **Existing reproducer, the M12 daily probe (mdaily_probe.py), with remote heads taken at the start of this pass: 8/9 on all four Pythons.**
  - H1 now PASSES.
  - H3 still fails on 4582f4e only (see Residuals).
  - T0 to T4 and X1 pass.
  - (results/m12-reproducer-mdaily-probe-r4.txt)
- **Builder checks on all four Pythons:**
  - daily_integration_oracle ACCEPTED 13/13.
  - The no-op control is REJECTED 0/13.
  - cross_checks are clean.
  - `check --plan` gives VERDICT INTEGRATED.
- **Full check run (`check --plan --run all`) on 3.9.6:** every prerequisite test and command, the cross-checks and all gates return rc 0, and the verdict is INTEGRATED.
- **Targeted tests on all four Pythons:** G12, G04, G05, closure_hardening, G07, G08 and G09, 128 OK.
  - (results/reproducers-oracle-crosschecks-runall-targeted.txt)
- **Full suite on fresh clones:** 267 OK on all four Pythons. Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **OBS (carried from M12, not closable here): mdaily H3.**
  - 4582f4e is the G12 r2 merge of G04 r3. It was resolved by hand: one exit-2 line in handoff-work-orders.md keeps both reasons.
  - M12 reviewed that merge. Making H3 pass would mean rewriting published history, which needs a force-push and is out of scope.
  - All four r4 merges are clean (R11).
- G09 h1 1cab0f8 and the other pins are candidates, not accepted revisions. This stack accepts nothing.

Browser launches for this pass: 0.
