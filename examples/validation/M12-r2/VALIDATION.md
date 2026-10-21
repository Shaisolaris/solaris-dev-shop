# M12 r2 validation of G12 r3 a245f1f

- Verdict: PASS for the change. M12 P4-1 is closed. No P1, P2, P3 or P4 in r3 itself.
- Open, not a defect in r3: the G12 plan pins heads that have since moved (H1), so the day 2 stack is stale and needs a refresh before anyone relies on it.
- This is Grok checking a Grok build. Grok self-validation, not independent review. It accepts nothing.

## What is being checked
- M12 validated G12 r2 e187297 and left P4-1: a resolved_overlaps reason over 300 characters was refused as "expected a non-empty string".
- Since then on review/grok-g12-daily-integration: a245f1f G12 r3 (raw/binding-verify.txt). A plan text over the limit is now refused with its length and the limit; blank and non-string values keep the old message.

## Probe (oracle/m12r2_probe.py)
Black-box `daily_integration.py check` runs on plans changed here. Inputs chosen here, not copied from the G12 r3 test.
- R01: over-long texts in three fields (reason 301 and 5000, a 400-character overlap path, a 350-character cross-check argument).
- R02: empty, number, null and list reasons still say "expected a non-empty string".
- R03: an over-long refusal keeps a previous `--out` report.
- R04: boundary, a 300-character reason is not refused as invalid input.

## Results
- G12 r2 e187297: 3/4. R01 fails: every over-long text says "expected a non-empty string" (results/probe-r2-e187297-3.9.6.txt).
- G12 r3 a245f1f: 4/4 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r3-four-python.txt).
- New builder test fails on e187297 (results/new-test-at-e187297.txt).
- Existing reproducer, the M12 daily probe (mdaily_probe.py) with remote heads taken at the start of this pass: 7/9 (results/m12-reproducer-mdaily-probe-r3.txt).
  - H1 FAIL: the plan pins G04 e9fa278, G05 04b3cf2, G07 0d6a78d and G09 edfa64d; the remote heads are now G04 r4 7ed5f70, G05 r4 1b840cd, G07 r2 f4776bd and G09 1cab0f8. G04 and G07 moved today with their P4 fixes; G05 r4 was a known follow-up.
  - H3 FAIL: merge 4582f4e is not a clean merge. M12 reviewed this merge and recorded it; it is unchanged.
  - T0 to T4 and X1 PASS: the tool still has its teeth on the r3 tree.
- Full suite on fresh clones: 262 OK on all four Pythons (one skip on 3.11+). Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **OPEN (integration, not a defect in r3):** the day 2 stack needs to be refreshed onto G04 r4 7ed5f70 and G07 r2 f4776bd (and G05 r4 1b840cd) before it is current again.
- **OBS (from M12, unchanged):** H3 is a strict check; the one non-clean merge was reviewed in M12.
- **OBS:** the same daily_integration.py is on the G06, G18, G24, G30, G36 and G42 integration branches. This pass covers only G12.

Browser launches for this pass: 0.
