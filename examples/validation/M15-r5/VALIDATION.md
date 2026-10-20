# M15 r5 validation of G15 r5 2a3310b (Grok self-validation, not independent review)

Verdict: **PASS. M15 r4 P3-1 is fixed, and there is no P1 or P2.** Grok checked a Grok build made in the same batch by
the same agent. This is not independent review and accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate 2a3310b711c0035e34bdcac047b30ae4aedd04b7 on review/grok-g15-experiment-readout, re-checked on the remote.
- It is one commit on top of r4 7e7f361 (M15 r4-validated), a fast-forward.
- G15-r5.patch equals the regenerated diff; MANIFEST.sha256 equals the diff set (4 files).

## The finding and the fix
- M15 r4 P3-1: the contract checked the arms of the units in the log, not units missing from it, and the trace said
  "verified for all N cohort units".
- r5 adds an optional `randomization.expected_units` (the assignment system's count), compares it with the cohort units
  in the log, and states the gap when the count is absent.

## Probe written for this pass (oracle/m15r5_probe.py, results/probe-r5-*.txt)
It reuses the M15 r4 generator: 31 days, 60 units a day, arms from my own sha256_bucket implementation. 20 seeds.
| Row | Check | Result |
|---|---|---|
| C1 | r4 B10 data (25% of converting control units dropped, no true effect) with expected_units = 1860: invalid_experiment in 20 of 20, never causal, trace says "missing from the log" | PASS (r4: 9 of 20 causal) |
| C2 | same data without expected_units: every difference_detected trace says missing units were not checked | PASS (9 difference_detected, all disclosed) |
| C3 | A/A with expected_units: verified and missing_units_checked in 20 of 20; causal false positives 1 | PASS |
| C4 | true effect 20% to 30% with expected_units: difference_detected in 20 of 20, and the trace says the log holds all 1860 | PASS |
| C5 | expected_units off by +1, -1, or set to 1: invalid_experiment | PASS |
| C6 | expected_units 0, negative, bool, string, float or null: exit 2 | PASS |
| C7 | r4 B1 burst with expected_units counting the burst: still invalid (arms off the rule) | PASS |

Four Pythons (results/pyversions.txt): M15 r5 probe 7/7; M15 r4 probe 8/8 (regression, unchanged); M15 r3 battery
23/29 core PASS (the same as at r4). The checkout was clean after every run.

## Teeth (scripts/m15r5_teeth.py, results/teeth.txt)
| Mutant | G15 tests | M15 r5 probe |
|---|---|---|
| count not compared | caught | caught (C1, C5) |
| only short logs fail | caught | caught (C5) |
| gap not stated in the trace | caught | caught (C2) |
| bool accepted as a count | caught | caught (C6) |
| units in both arms not counted | survived | survived |

**OBS (P4, test gap):** rule 7 says units in both arms count toward the log total, but no test or probe row has a
two-arm unit together with expected_units, so that wording is not pinned.

## Builder evidence re-run
- Builder oracles (results/builder-oracle.txt): G15 tests OK; readout_oracle 18/18; naive 2/18; no-op 1/18.
- Full suite on fresh clones: 143 OK on all four Pythons (results/full-suite-matrix.txt).
- The new test fails at r4 (results/new-test-at-r4.txt).
- No browser was launched.

## Residual
Without `expected_units`, units missing from the log are still not detected, which is unavoidable from the log alone.
r5 states this in rule 7 and in the trace. Whether the export supplies `expected_units` is an owner or root decision.
