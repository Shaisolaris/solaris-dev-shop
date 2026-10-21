# M36 r2 validation of G36 r3 5296440

- Verdict: PASS. The day 6 stack now pins the newest heads of G04, G31, G32, G33 and G34, the overlap reasons match the new blobs, and the M12 P4-1 tool fix is carried. No P1 to P4. No open OBS (OBS-1 corrected below).
- This is Grok checking a Grok build, built in the same run by the same agent. Grok self-validation, not independent review. It accepts nothing.

## What is being checked
- M36 r1 validated G36 r2 92ca6c3 (PASS after repair). Since then G04 r4 7ed5f70, G31 r4 e809a4f, G32 r5 807f1eb and G33 r5 25c0075 were built and validated (M04 r3, M31 r3, M32 r5, M33 r4), and G34 has a post-acceptance h1 6ad99da. G36 r2 pinned the older heads. The tool carried blob 2a40a9d (M12 P4-1).
- Since then on review/grok-g36-daily-integration: five merge commits (one per new head) and 5296440, a plain fast-forward over 92ca6c3 (raw/binding-verify.txt). 5296440 updates plan.json pins and notes, rewrites the four G04/G32 overlap reasons with the G04 r4 blobs, names G33 r5 and G31 r4 in the other four (their blobs are unchanged), updates the README, and carries the G12 r3 tool fix with a G36 test.

## Probe (oracle/m36r2_probe.py)
Written for this pass. It reads git objects and the remote, not the builder's notes.
- R01: every pin is the current remote head of that goal's review branch.
- R02: every pin is an ancestor of HEAD.
- R03: each r2 pin is an ancestor of its r3 pin.
- R04: the r2 head is an ancestor of HEAD (history kept).
- R05: every blob a resolved_overlaps reason names is a real blob of that path at a pin, HEAD or the base.
- R06: outside the writable paths and the listed overlaps, HEAD keeps each candidate's file (or a descendant candidate's).
- R07: every file two unrelated candidates change differently is listed in resolved_overlaps.
- R08: a 333-character reason exits 2 named as too long.
- R09: the tool blob equals G12 r3's.
- R10: `check --plan` on the shipped plan is INTEGRATED.
- R11 (OBS): see Residuals.

Harness repair during this pass, disclosed: v1 read `git diff --name-only` with quoted non-ASCII names and flagged the G34 fixture `unseen/site/café.html` in R06; v2 uses core.quotepath=false. Scores below are v2.

## Results
- G36 r2 92ca6c3 on 3.9.6: 7/10 (R01 five stale pins; R08, R09 old tool) (results/probe-at-92ca6c3-3.9.6.txt).
- G36 r3 5296440: 10/10 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r3-*.txt).
- Existing reproducers on all four Pythons: daily_integration_oracle ACCEPTED 13/13, no-op REJECTED 0/13, cross_checks CLEAN, `check --plan` VERDICT INTEGRATED. `check --plan --run all` on 3.9.6: every prerequisite test and command, the cross-checks and all gates rc 0, VERDICT INTEGRATED (results/reproducers-oracle-crosschecks-runall.txt).
- New builder test fails on the r2 tool (results/new-test-at-92ca6c3-tool.txt).
- Full suite on fresh clones: 326 OK on all four Pythons. Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **OBS-1 (corrected in a follow-up commit):** the first version of this line said G34 h1 6ad99da had no M pass of its own. That was wrong: M34 h1 5d4d01f on review/grok-m34-h1-validation validates exactly 6ad99da (PASS, Linux and macOS recheck). This pass adds only that 6ad99da is the branch head, is carried, and its tests and oracle pass in the stack.
- **Not in this pass:** the G12 day 2 stack still pins G04 e9fa278, G05 04b3cf2, G07 0d6a78d and G09 edfa64d (superseded by 7ed5f70, 1b840cd, f4776bd and 1cab0f8). G06, G18, G24 and G42 still carry the old tool blob; G06, G18, G24 and G42 are in the stronger lane or off limits.

Browser launches for this pass: 0.
