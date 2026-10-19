# G15 evidence: experiment and retention readout

Tool: `employees/data/data-scientist/experiment_readout.py` (reference
`employees/data/data-scientist/experiment-readout.md`). All data here is synthetic.

## Fixtures

Generated once with `readout_oracle.experiment` (seeds 11, 12, 13); counts below are the generator's
ground truth and the tool's output.

| Fixture | Content | Units (control, treatment) | Converted | Outcome |
|---|---|---|---|---|
| `clean-aa` | A/A: every fourth unit converts in both arms | 400, 400 | 100, 100 | no_detectable_difference |
| `retention-lift` | 20% vs 35% retention; declared `sha256_bucket` randomization, all 1,200 cohort units verified (unit ids carry an `rN` suffix chosen so the rule gives each unit its arm); 20 units outside the cohort, 6 in both arms, 6 unassigned, pre-assignment and post-horizon events | 600, 600 | 123, 231 | difference_detected |
| `sample-ratio-mismatch` | 300 vs 420 against a planned 50/50 | 300, 420 | 56, 130 | invalid_experiment (no effect read) |

## Oracle

`python3 readout_oracle.py [--seed N] [--quick] -- PYTHON TOOL` generates packages with known truth and
checks 18 properties (17 with `--quick`):

| Check | What it proves |
|---|---|
| o1 | deterministic A/A: exact counts, interval includes 0, no claim |
| o2 | real lift with a verified randomization contract: exact counts, interval matches an independent computation, causal claim |
| o3 | 12 sessions per unit still count each unit once |
| o4 | units outside the cohort and immature units excluded, not counted as failures |
| o5 | units in both arms excluded and named; unassigned events ignored |
| o6 | sample-ratio mismatch: invalid_experiment, no claim |
| o7 | below min sample: insufficient_information even with a large gap |
| o8 | observational data: association_only, never causal |
| o9 | row order and repeated runs give the same report |
| o10 | invalid packages refused with exit 2, previous report kept |
| o11 | 120 000 units (skipped by `--quick`) |
| o12 | no bytecode or files written next to the inputs; local only |
| o13 | allocation drift (Simpson): three ramps and one gradual drift with a balanced pooled split are invalid_experiment with no claim; a steady planned 30/70 split with a verified contract and a falling base rate reads the true positive difference |
| o14 | one-day allocation burst: nine one-day all-variant bursts (40, 60, 90 units; day-aligned, across midnight, across a 7-day block boundary) inside healthy weeks with zero true effect are invalid_experiment with no claim |
| o15 | alignment independence: the same burst with the cohort start moved by 0, 30, 75 and 150 hours gives the same invalid verdict and the same worst sliding window |
| o16 | false invalidations: at most about 1% of healthy 50/50 runs with no allocation change are invalidated (200 runs; 40 with `--quick`) |
| o17 | root G15: all-variant bursts of 30, 40 and 60 units interleaved with a day's traffic, zero true effect, no randomization contract: never a causal claim, `assignment_check.verified` false (45 runs; 18 with `--quick`) |
| o18 | with a declared `sha256_bucket` contract, interleaved bursts of 12, 30 and 60 units are invalid_experiment by the unit check; an honest lift is causal with every unit verified; one flipped unit invalidates; malformed contracts and a contract on observational data are refused |

Controls (both must be REJECTED): `naive_stub.py` (dashboard read: event rows as units, no cohort,
no leakage or SRM checks, any positive gap called a causal win) and `noop_stub.py`.
