# Product choice from conflicting evidence (G33)

Tool: `evidence_decision.py` (stdlib, Python 3.9+, exact decimals, local files only). It scores a product
choice package against named options and weighted dimensions, using only claims whose sources still match
their pinned snapshots. It invents no TAM, SAM, SOM, market_size or adoption figures. The owner decides;
the report is a draft.

```bash
python3 evidence_decision.py decide PACKAGE [--json] [--out FILE]   # 0 preferred, 1 no robust choice or blocked, 2 invalid
python3 evidence_decision.py verify RESULT PACKAGE                  # 0 identical, 1 different, 2 invalid
```

## Package (schema `solaris.evidence-decision/1`)

- `decision`: `question`, `owner`, `as_of` (date), `icp` {`segment`, `definition`}.
- `options`: [{`id`, `label`}].
- `dimensions`: [{`id`, `label`, `weight`}] with weights summing to exactly 1. Optional `metric_scale`
  {`thresholds`: five ascending numbers} maps a stated numeric value to scores 1..5. Optional `quantity`
  (true or false) requires every claim on that dimension to carry a numeric `value` that equals a whole number stated in its quote (numbers are compared whole, so `18` does not match `18,000` and `4` does not match `40`; `18000` matches `18,000`; a `%` must match; a value read as a number but not written as a plain number, such as `1,5`, `+18` or `-5`, never matches);
  a claim without a value, with a value that is not a number, or whose quote states no number is flagged
  `value_not_in_quote` and not used.
- `sources`: [{`id`, `kind` interview|external|g13, `title`, `retrieved_at` ≤ `as_of`, ...}].
  - interview / external: `snapshot` {`path`, `sha256`} of a local file.
  - external: also `url`, `mutable` (bool); when mutable, `max_age_days` (int). A mutable source older than
    that age is reported under `verify_before_use` and its claims are excluded until refreshed.
  - g13: `contract`, `metric`, `group` -- the tool loads `csv_reconcile.reconcile` by file path and reruns
    it; a status other than `reconciled` lowers claim confidence to `low`.
- `claims`: [{`id`, `option`, `dimension`, `source`, `segment`, `confidence` low|medium|high, optional
  `score` 0..5, optional `value`, optional `quote`}]. Top-level keys `tam`, `sam`, `som`, `market_size`,
  `adoption`, `adoption_rate` and `assumed_adoption` are refused (exit 2, nothing written).

## Checks before a claim is used

| code | when |
|---|---|
| unknown_source | claim names a source id that is not in `sources` |
| snapshot_mismatch | snapshot file missing or sha256 differs |
| quote_not_in_source | quote (normalized whitespace/case) is not a substring of the snapshot |
| value_not_in_quote | a stated `value` does not appear in the quote; a numeric value must equal a whole number in the quote, not a digit fragment (also when the dimension is `quantity`) |
| unscored_claim | no `score` and no `metric_scale` path that can derive one |
| stated_score_mismatch | stated score differs from the metric-scale mapping of `value` |
| g13_unavailable | G13 contract missing, reconcile refused, or group/metric not present |
| g13_value_mismatch | stated `value` differs from the G13 metric for that group |

Out-of-ICP claims (`segment` ≠ ICP segment) are listed under `excluded` and never enter a cell. Stale
mutable claims are excluded the same way and listed under `verify_before_use` with `age_days`.

## Scoring and decision

Each (option, dimension) cell is the confidence-weighted mean of its claims (low=1, medium=2, high=3), with
`low`/`high` from the min/max scores. An empty cell spans 0..5 and marks the dimension unknown. A cell with
score range ≥ 2 is `conflict`. Contrary evidence is a claim on the other side of 2.5 from the cell mean.
Per-option totals are the weight × cell aggregates; `point` is omitted when any dimension is unknown.
`preferred` is set only when one option's low total is strictly greater than every other option's high total;
otherwise `no_robust_choice` with `deciding_evidence` naming the cells whose ranges (or unknowns) prevent a
robust win. Any finding that blocks a claim withholds the preference: the result is `blocked_evidence`,
`preferred` is null and the exit is 1, even when the remaining totals would still pick a winner. The report includes `claim_confidence` (after any G13 downgrade) and `estimates_made`.

## Recovery

`--out` writes through a temporary file and an atomic rename, refuses to overwrite the package, and a failed
or invalid run leaves an earlier result untouched. `verify` reruns the package and names any field that
differs.
