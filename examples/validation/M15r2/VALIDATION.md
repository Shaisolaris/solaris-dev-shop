# M15 r2: Grok self-validation of G15 r2 (experiment readout, allocation drift fix)

This is Grok self-validation, not independent review. The same agent family built and validated it.

- Candidate: G15 r2 `6c51c3c07558d766d49ad25bd0953285c4568455` on `review/grok-g15-experiment-readout`,
  a fast-forward from r1 `78daf30ff479c35a5cb59d9a544ee89e530cd100` (scored by M15 `b43015b`, FAIL, P2-1 + P4-1).
- Prerequisites unchanged: G13 r3 `5666e7b`, main `02ba9c5`. Nothing superseded. The candidate was never modified;
  every run used an rsync copy in a private temp dir. week-grok before/after records are identical.
- Pass window: 03:04 to about 03:20 PT, 2026-10-19.

## Disclosure: the fix came from my own patch

The r2 drift fix starts from my M15 proposed patch (`proposed-fix-allocation-drift.patch`), which the builder
discloses. I am scoring a fix I wrote, so this pass weights fresh shapes I had not tried. Check in
`raw/binding-verify.txt`: my patch applies to r1, and all but three of its added lines are present verbatim in r2. The
three differ because the builder extended them (two doc lines and the trace message, now carrying the homogeneity p).
So "applied unchanged" in the handback is "applied, then extended". The builder also added a new piece that is not
mine: an arm x week homogeneity chi-square (weeks - 1 df, p < 0.001, stdlib incomplete-gamma `chi2_sf`) and
builder oracle row 13.

## Verdict: PASS with residuals. P2-1 is fixed for the weekly shapes; P4-1 is fixed.

| Instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| G15 tests / full suite | 12 OK / 136 OK | same | same | same |
| builder oracle (seed 1515) real / naive / noop | 13/13 / 1/13 / 0/13 | same | same | same |
| M15 oracle v3 (regression) real / naive / noop | 15/15 / 2/15 / 2/15 | same | same | same |
| new drift oracle `m15r2_drift.py` | 6/6 core | 6/6 | 6/6 | 6/6 |

- Regression: the M15 Simpson rows X13 and X13b (OBS) moved from `difference_detected` with the wrong sign to
  `invalid_experiment`. No other M15 row changed in result or detail.
- Fresh caller (env -i, new HOME, README commands only) on 3.9.6 and 3.13.15: identical, the three examples give
  the documented outcomes, bad input exits 2, `--out` writes, no stray files or bytecode.
- Teeth (39 builder mutants, unchanged, scored against `m15r2_all.py` = M15 oracle v3 + drift oracle):
  3.13.15 39/39; 3.9.6 38/39. The survivor is `bytecode_written`, equivalent on Apple 3.9.6 because its
  pycache_prefix keeps bytecode out of the tree (killed on 3.13.15).

## New adversarial drift shapes (oracle derives the documented rule independently, closed-form chi-square tails)

- D01: my M15 ramps still invalid. PASS.
- D02 gradual ramps, five strengths over 56 days; D03 a single bad day of 60, 120, 300 units; D04 many short weeks
  (140 days at 2, 3, 6 units/day, so many weeks fall under the 20-unit floor); D05 a 30/70 plan with drift; D06 a
  30-case random-shape property test. In every case the outcome equals the documented rule, and the tool's per-week
  and homogeneity p-values equal mine to 1e-6. PASS.
- O07 (OBS) false invalidation: 1/200 healthy experiments invalidated (0 by pooled SRM), about 0.5%, near the
  handback's 0.2% estimate. Power cost: `difference_detected` in 59/200 with a true +0.04 effect.
- O08 (OBS) single bad day: 40 or 60 units, all to the variant, converting at 0.9 against a 0.1 base, inside one
  otherwise healthy 7-day block. Outcome `difference_detected` with causal claims, difference +0.056 / +0.058,
  true effect 0; worst week p 0.012 to 0.03 (Bonferroni bar about 0.0002) and homogeneity p 0.15 to 0.53. At 90
  units it is invalid.
- O09 (OBS) power vs alignment: one 7-day block at 0.65 share, 20 units/day: 9/20 invalid at 28 days, 0/20 at 91
  days (the block straddles a 7-day boundary, days 45 to 51), 5/20 at 182 days (aligned).

## Findings

- P2-1 (M15 r1): fixed for weekly and gradual ramps, unequal plans and short weeks; the trace names the worst
  week and both p-values.
- P4-1 (M15 r1, horizon end): fixed. The doc now states `[assigned_at, assigned_at + horizon_days)`.
- P3-1 (new, same family): a short allocation change concentrated in a day can still yield a causal claim of the
  wrong size (O08). The tool follows its stated test, but the doc also promises "A ramp or allocation change inside
  the cohort makes the experiment invalid", which is not true below the weekly test's power. I grade it P3 because
  the rule is documented and the failure needs a deliberate, few-percent, sub-week burst; the user may see it
  as P2 because the result is an unsupported causal claim. Suggested direction (not a patch, since P3): qualify the
  doc promise, or add a per-day or sliding-window test. No proposed-fix patch is supplied.
- P4-1 (new): detection power depends on where a burst falls against the fixed 7-day blocks and on the Bonferroni
  factor (O09). Worth a doc sentence.
- OBS: about 0.5% false invalidation of healthy runs (O07), and power loss from the stricter bar. In line with the
  handback's open questions.

## Disclosures

- The drift oracle is new for r2. The M15 oracle v3 is reused unchanged for regression.
- The pass scores a fix built from my own patch (see above).
- Not done: a stratified estimate (the handback lists it as not built); independent review.

## Layout

`oracle/` (M15 v3 copy, drift oracle, combined), `scripts/` (matrix, teeth, fresh caller), `results/`, `raw/`
(binding verify, week-grok before/after).
