# M15 r6 validation of G15 r6 142cc2e (Grok self-validation, not independent review)

Verdict: **PASS.** M15 r5 OBS P4 (units in both arms counting toward expected_units was not pinned by a test) is
closed by a pinning test. No behaviour changed and no new finding. This is Grok checking a Grok build made in the same
batch by the same agent. It is not independent review and accepts nothing. Causal-claim policy (root finding on M15 r3)
is stronger-lane work and was not touched.

## Binding (raw/binding-verify.txt)
- Candidate 142cc2eaa3ab695cee8b3d51e25118d59f0e8fc7 on review/grok-g15-experiment-readout (remote re-checked), one
  fast-forward commit from r5 2a3310b. Diff: tests/test_g15_capability.py only (+27 lines).
- Evaluated in the build worktree; `git status --porcelain --ignored` empty after every run.

## What was checked
- The builder test `test_units_in_both_arms_count_toward_expected_units` adds a second-arm row for an existing cohort
  unit (count unchanged, verified) and a new unit seen only in both arms (n+1 verified, n is "units added to the log").
- It is a pinning test, so it passes at 2a3310b by design. Teeth: the M15 r5 survived mutant (two-arm units not
  counted toward units_in_log) now fails exactly this test (results/builder-test-mutant.txt).
- New probe written for this pass (oracle/m15r6_probe.py), using the six two-arm units already in the retention-lift
  fixture rather than added rows: R01 expected_units 1206 verified; R02 1200 is invalid with "units are added";
  R03 more rows for a two-arm unit do not add to the count; R04 two-arm units stay out of the effect (600 + 600).
  4/4 on Python 3.9.6, 3.11.16, 3.12.14 and 3.13.15; 1/4 on the mutant (R04 is not about the count).

## Builder evidence re-run
- M15 r5 probe 7/7 on four Pythons; readout_oracle ACCEPTED 18/18 and no-op REJECTED 1/18 on four Pythons
  (results/builder-oracle-and-m15r5-probe.txt).
- Full suite 144 tests OK on four Pythons (results/full-suite-matrix.txt).
- No browser was launched.

## Residual
- Whether exports supply expected_units is an owner decision (unchanged).
- Root finding on M15 r3 (causal output needs a validated experimental contract or abstains) stays stronger lane.
