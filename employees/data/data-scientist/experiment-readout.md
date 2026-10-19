# Experiment and retention readout (G15)

`experiment_readout.py analyse PACKAGE.json [--json] [--out REPORT]` turns an assignments export and
an events export into a readout that states what the data supports and nothing more.

## Package (schema `solaris.experiment/1`)

| Field | Meaning |
|---|---|
| `experiment` | name used in the report |
| `unit` | must be `unit_id`; the unit of analysis, one outcome per unit |
| `assignment` | `randomized` or `observational` |
| `arms` | two names, control first |
| `planned_split` | two shares adding up to 1 |
| `timezone` | IANA zone for timestamps without an offset |
| `cohort` | `{start, end}`: units first assigned in `[start, end)` are the fixed cohort |
| `as_of` | data cut; units whose horizon ends after it are immature |
| `outcome` | `{event, horizon_days}`: converted means the event in `[assigned_at, assigned_at + horizon_days)`; an event exactly at the end does not count |
| `min_sample_per_arm` | below this in either arm the readout is insufficient_information |
| `alpha` | optional, default 0.05 |
| `assignments`, `events` | `{file, header_aliases?, delimiter?}` read by the G13 data-engineer reader |

Assignments carry `unit_id, arm, assigned_at`; events carry `unit_id, event, occurred_at, session_id`.
Unknown package fields, duplicate keys, bad timestamps or columns are refused with exit 2 and any
previous report is left unchanged.

## Rules

1. One outcome per unit. Sessions and repeated events never add units.
2. The cohort is fixed by first assignment; immature units are excluded and counted, never treated
   as non-converted.
3. Units seen in both arms are excluded and named. If they exceed 5% of the cohort the experiment
   is invalid.
4. Outcome events before assignment or at or after the end of the horizon do not count. Events of unassigned units
   are ignored and counted.
5. A sample-ratio mismatch (chi-square against the planned split, p < 0.001) makes the experiment
   invalid; no effect is read.
   The same test runs per assignment week (weeks from cohort start with at least 20 units,
   p < 0.001 divided by the number of weeks tested). A ramp or allocation change inside the cohort
   makes the experiment invalid even when the pooled split matches the plan: pooling periods with
   different base rates can reverse the sign of the effect (Simpson). The split must also be the same
   across those weeks: a chi-square test of arm against week (weeks - 1 degrees of freedom,
   p < 0.001) catches a gradual drift in which no single week fails its own test.
   `allocation_by_week` in the JSON shows the worst week and both p-values. Weeks are 7-day blocks
   from `cohort.start`, not calendar weeks.
6. Effect: difference in rates with a (1 - alpha) Wald interval and a pooled two-proportion z test.

## Outcomes

| Outcome | When | Claims allowed |
|---|---|---|
| `insufficient_information` | an arm is below `min_sample_per_arm` | none |
| `invalid_experiment` | SRM or contamination above 5% | none |
| `no_detectable_difference` | interval includes 0 | none; not evidence of no effect |
| `difference_detected` | randomized and interval excludes 0 | causal and significance, for this experiment |
| `association_only` | observational and interval excludes 0 | significance only, never causal |

`claims_allowed {causal, significance}` in the JSON is what a PM or exec summary may repeat.
Exit 0 means analysed (any outcome), 2 means the package was refused.

Evidence: `examples/capabilities/G15/` (fixtures, `readout_oracle.py`, naive and no-op controls) and
`tests/test_g15_capability.py`.
