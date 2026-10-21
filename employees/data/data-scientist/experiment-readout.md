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
| `randomization` | optional, randomized only: `{"method": "sha256_bucket", "salt": "...", "expected_units": N}`, the rule that assigned the arms (rule 7); without it no causal claim is made. `expected_units` is optional: the assignment system's count of units first assigned in the cohort window |
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
   Because those blocks are fixed, a short burst can be diluted by the block it falls in or split
   across two. A sliding-window scan closes that gap: units in assignment order (`assigned_at`, then
   `unit_id`), windows of 20, 40, 80, ... units up to half the cohort, each moved by an eighth of its
   length plus one window ending at the last unit; each window gets an exact two-sided binomial test
   against the planned split (chi-square, 1 df, above 1,280 units). The experiment is invalid when the
   smallest p-value is below 0.002 divided by the number of windows (Bonferroni, conservative for
   overlapping windows). The scan does not use `cohort.start`, so moving the start does not change it.
   `allocation_scan` in the JSON shows the windows tested, the threshold and the worst window
   (first and last assignment time, arm counts, p-value). Together the four tests keep false
   invalidations of a healthy run at or below about 0.5% (0.001 + 0.001 + 0.001 + 0.002 by the union
   bound). Power limit: an all-variant burst of about 30 units or fewer can pass, depending on how much
   normal traffic is interleaved with it (with 60 units a day, 30 units in one day are caught when
   they replace the day's traffic and can be missed when they straddle midnight); the scan is a
   guard against allocation changes, not proof that none happened.
6. Effect: difference in rates with a (1 - alpha) Wald interval and a pooled two-proportion z test.
7. Causal claims need a verified assignment. The allocation tests in rule 5 are guards with limited power: with
   60 units a day, an all-variant, high-converting burst of 30 to 60 units interleaved with one day's traffic is
   missed in most runs and can produce an interval that excludes 0 with no true effect. So "randomized" alone
   is not evidence. The package may declare the assignment rule as `randomization`
   `{"method": "sha256_bucket", "salt": S}`: a unit's arm is the control arm when the first 15 hex digits of
   sha256 of `S:unit_id` (UTF-8), read as a fraction of 16^15, are below the control share, otherwise the other
   arm. The tool recomputes that arm for every cohort unit (units in both arms are excluded and named as in
   rule 3). One unit in an arm the rule does not give it makes the experiment invalid, because the data did not
   come from the declared randomization; an injected burst of n all-variant units passes this check only with
   probability (treatment share)^n (about 1 in 4,000 for 12 units at 50/50). Without a contract, a randomized
   readout whose interval excludes 0 is `association_only`: significance, never causal. `assignment_check` in
   the JSON shows the contract, the units checked, the mismatches (first five named) and `verified`. Units
   that happen to satisfy the rule are indistinguishable from randomized ones; the other rule 5 tests still
   apply to them.
   The per-unit check sees only the units in the log. It cannot tell that units are missing: dropping a share
   of converting control units leaves every remaining unit on the rule, and on such data the readout can
   claim a difference with no true effect. Without more information, differential loss is guarded only by
   SRM, whose power is limited. When the assignment system can supply its count of units first assigned in
   the cohort window, give it as `expected_units`. A log holding a different number of cohort units (units in
   both arms count, since they were assigned) is then `invalid_experiment`. `assignment_check` reports
   `expected_units`, `units_in_log` and `missing_units_checked`. A `difference_detected` trace says whether
   missing units were checked.

## Outcomes

| Outcome | When | Claims allowed |
|---|---|---|
| `insufficient_information` | an arm is below `min_sample_per_arm` | none |
| `invalid_experiment` | SRM, allocation drift or scan, contamination above 5%, or a unit off the declared randomization | none |
| `no_detectable_difference` | interval includes 0 | none; not evidence of no effect |
| `difference_detected` | randomized, every cohort unit verified against the declared `randomization`, and interval excludes 0 | causal and significance, for this experiment |
| `association_only` | interval excludes 0 and assignment is observational, or randomized without a `randomization` contract | significance only, never causal |

`claims_allowed {causal, significance}` in the JSON is what a PM or exec summary may repeat.
Exit 0 means analysed (any outcome), 2 means the package was refused.

Evidence: `examples/capabilities/G15/` (fixtures, `readout_oracle.py`, naive and no-op controls) and
`tests/test_g15_capability.py`.

## Population-completeness gate
A `difference_detected` outcome describes a statistical difference in the observed log, not
by itself permission to claim causality. `claims_allowed.causal` is false unless the declared
randomization rule is verified and an independently supplied `randomization.expected_units`
count agrees with the cohort population, with the other design and quality guards passing.
Do not derive that external count from the same incomplete log to manufacture verification.
A matching count is an input assumption, not authentication of an experiment or proof against
fabricated/replaced records. Missing counts keep the statistical result but explicitly forbid
a causal claim. Follow the claim flags and trace, not the outcome label alone.
