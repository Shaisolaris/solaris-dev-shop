# G15 evidence: experiment and retention readout

Tool: `employees/data/data-scientist/experiment_readout.py` (reference
`employees/data/data-scientist/experiment-readout.md`). All data here is synthetic.

## Fixtures

Generated once with `readout_oracle.experiment` (seeds 11, 12, 13); counts below are the generator's
ground truth and the tool's output.

| Fixture | Content | Units (control, treatment) | Converted | Outcome |
|---|---|---|---|---|
| `clean-aa` | A/A: every fourth unit converts in both arms | 400, 400 | 100, 100 | no_detectable_difference |
| `retention-lift` | 20% vs 35% retention; 20 units outside the cohort, 6 in both arms, 6 unassigned, pre-assignment and post-horizon events | 600, 600 | 123, 231 | difference_detected |
| `sample-ratio-mismatch` | 300 vs 420 against a planned 50/50 | 300, 420 | 56, 130 | invalid_experiment (no effect read) |

## Oracle

`python3 readout_oracle.py [--seed N] [--quick] -- PYTHON TOOL` generates packages with known truth and
checks 12 properties:

| Check | What it proves |
|---|---|
| o1 | deterministic A/A: exact counts, interval includes 0, no claim |
| o2 | real lift: exact counts, interval matches an independent computation, causal claim |
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

Controls (both must be REJECTED): `naive_stub.py` (dashboard read: event rows as units, no cohort,
no leakage or SRM checks, any positive gap called a causal win) and `noop_stub.py`.
