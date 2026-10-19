# M33 validation of G33 evidence-based product decision (Grok self-validation, not independent review)

Candidate: G33 `d63b1c146cf534f9b8575b0a61a51fa03c5b0c19` (branch review/grok-g33-evidence-decision), direct parent
G13 r3 `5666e7beb161d1252ddd5dcc0a166aca83255370`. Tool
`employees/product-project/product-manager/evidence_decision.py`, doc `evidence-product-decision.md`. Validator: Grok,
the same agent family that built G33. This is self-validation and does not replace an independent review. Pass
window 06:53 to about 08:08 PT, Mon Oct 19 2026.

## Verdict

PASS (self-validation) with two P3 findings and OBS notes. Conflicting evidence, the focus of the request, is handled
as documented. No P1 or P2 findings, so no proposed-fix patch.

## Prerequisite chain

- The patch sha equals the diff sha (`d67f80fe...ccf9`); the manifest has 31/31 entries with 0 mismatches and its set
  equals the diff set. 5666e7b is the direct parent (raw/binding-verify.txt).
- G13 r3 5666e7b was validated by M13 r3 at db6028e (PASS, T1 P4). G33 reads G13 contracts as evidence; M33 checked
  that use (E07) but did not re-test G13.
- Nothing in the chain is superseded as far as the branch listing shows (5666e7b is still the head of
  review/grok-g13-csv-reconciliation).

## Method

- Fresh oracle `oracle/m33_oracle.py` (v2), written from M33.md, G33.md and the doc before I read the builder's
  oracle. It keeps an independent Decimal model of the doc's scoring (confidence-weighted cell mean with low=1,
  medium=2, high=3; min and max ranges; an unknown cell spans 0..5; conflict when the range is 2 or more; totals are
  weight x cell; preferred only when one option's low total beats every other option's high total; a metric scale
  score is the number of thresholds at or below the value) and drives the CLI on edited copies of the fixture.
- Core rows:
  - E01 clean control: preferred portal; totals 3.5000, 3.9500 and 3.8214 equal my model; C9 (out of ICP) and C10
    (stale) are excluded; no market size computed.
  - E02 no invented market numbers: top-level tam, sam, som, market_size and adoption refused with nothing written; a
    fresh analyst figure is score-checked and used only as evidence; invented values and quotes blocked.
  - E03 source integrity: edited or missing snapshots, unknown sources, late retrieval, unscored claims and bad scores
    never feed a cell.
  - **E04 conflicting evidence:** a strong contrary interview claim (C20, score 1, high confidence) makes the portal
    pain cell a conflict (1..5), is listed under contrary_evidence, and the decision becomes no_robust_choice naming
    that cell, with totals equal to my model.
  - E05 the decision moves predictably: sweeping C1 over scores 0..5 and every confidence matches my model each time.
  - E06 an unknown dimension spans 0..5 with no point and blocks a robust win; a mutable source is usable at
    max_age_days (30) and excluded at 31.
  - E07 G13 evidence: the gaps contract lowers confidence to low; a wrong value, a missing contract and a stated score
    against the metric scale are named.
  - E08 recovery: --out refuses the package path, an invalid run keeps the earlier result, verify names an edited or
    truncated result.
  - E09 seeded soak: 30 random packages (2 to 4 options, random weights, scores, confidences, out-of-ICP claims and
    real quotes) match my model exactly.
  - E10 (v2) package rules: weights must sum to exactly 1 (0.99 refused, 0.4500 + 0.3000 + 0.2500 fine); a quantity
    dimension needs a value in every claim's quote; an out-of-ICP G13 claim is excluded like any other.
- OBS row O11: one blocked claim on a losing option while portal would still win robustly.
- Controls: the real tool scores 9/11 (E02 and E10 fail on the findings below); naive_decision and noop_decision
  score 1/11, the one pass being the OBS row, which always passes (matrix). Four interpreters, mutation tests on 3.13.15 and 3.9.6 with the 32 builder mutants copied
  unchanged, and a fresh caller. All of it ran on rsync copies; the candidate was never modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g33: Ran 19 tests in 7.515s  OK  | full: Ran 143 tests in 20.167s  OK  | builder-oracle: ACCEPTED 9/9 | builder-naive: REJECTED 1/9 | builder-noop: REJECTED 1/9 | m33-oracle: M33 ORACLE 9/11 core FAIL | m33-naive: M33 ORACLE 1/11 core FAIL | m33-noop: M33 ORACLE 1/11 core FAIL
== 3.11.16 | g33: Ran 19 tests in 5.994s  OK  | full: Ran 143 tests in 15.460s  OK  | builder-oracle: ACCEPTED 9/9 | builder-naive: REJECTED 1/9 | builder-noop: REJECTED 1/9 | m33-oracle: M33 ORACLE 9/11 core FAIL | m33-naive: M33 ORACLE 1/11 core FAIL | m33-noop: M33 ORACLE 1/11 core FAIL
== 3.12.14 | g33: Ran 19 tests in 6.170s  OK  | full: Ran 143 tests in 16.263s  OK  | builder-oracle: ACCEPTED 9/9 | builder-naive: REJECTED 1/9 | builder-noop: REJECTED 1/9 | m33-oracle: M33 ORACLE 9/11 core FAIL | m33-naive: M33 ORACLE 1/11 core FAIL | m33-noop: M33 ORACLE 1/11 core FAIL
== 3.13.15 | g33: Ran 19 tests in 6.196s  OK  | full: Ran 143 tests in 16.180s  OK  | builder-oracle: ACCEPTED 9/9 | builder-naive: REJECTED 1/9 | builder-noop: REJECTED 1/9 | m33-oracle: M33 ORACLE 9/11 core FAIL | m33-naive: M33 ORACLE 1/11 core FAIL | m33-noop: M33 ORACLE 1/11 core FAIL
pycache in copy: 0
candidate status lines: 0
```

Mutation tests: **v2 oracle 30/32 killed on 3.13.15 and 30/32 on 3.9.6** (results/teeth-*.log). The v1 oracle and
harness killed 24/32 on both (results/v1). The builder reports 32/32 on 3.12 and 3.9 with its own tests. Survivors,
both killed by the builder's tests:

- teeth-3.13.15.log: prefer_despite_findings SURVIVED
- teeth-3.13.15.log: no_atomic_out SURVIVED
- teeth-3.9.6.log: prefer_despite_findings SURVIVED
- teeth-3.9.6.log: no_atomic_out SURVIVED
- builder tests: no_atomic_out builder tests: KILL FAILED (failures=1) FAIL: test_atomic_out_uses_replace (tests.test_g33_capability.G33Capability.test_atomic_out_uses_replace)
- builder tests: prefer_despite_findings builder tests: KILL FAILED (failures=1) FAIL: test_findings_clear_preferred_even_when_totals_win (tests.test_g33_capability.G33Capability.test_findings_clear_preferred_even_when_totals_win)

- no_atomic_out writes --out with open/write instead of os.replace. A black-box oracle cannot see the difference
  without a crash mid-write; the builder's test inspects the code path.
- prefer_despite_findings: see OBS-1. My oracle records the behaviour in O11 but does not score it, because the doc
  can be read either way.

Fresh caller (results/fresh-caller.txt): on 3.9.6 and 3.13.15 decide prints PREFERRED portal and the builder oracle
ACCEPTED 9/9. The demo script exits 1 only because its last line runs the noop control (REJECTED 1/9). No
__pycache__ and the tree is unchanged.

## Findings

- **P3-1: a top-level `adoption` key is accepted although the doc says it is refused.** The doc lists `tam`, `sam`,
  `som`, `market_size` and `adoption` as refused top-level keys. The code refuses `tam`, `sam`, `som`,
  `market_size`, `adoption_rate` and `assumed_adoption`, so a package with `"adoption": "35%"` runs (rc 0). The value
  does not reach the output (`estimates_made` stays "none"), so this is a fail-open gap against the doc rather than a
  wrong decision. Fix: add `adoption` to the refused list, or change the doc.
- **P3-2: a quantity dimension does not require a value when the quote has no number.** The doc: "Optional
  `quantity` requires every claim on that dimension to carry a `value` that appears in its quote." With `quantity`
  set on pain, C1 (quote has "40", no value) is flagged `value_not_in_quote`, but C5 (no number in its quote, no
  value) is accepted and scored, because the check runs only when the quote contains a number. A purely qualitative
  claim can therefore score a quantity dimension. No fixture uses `quantity`, which is why I rate it P3 and not P2;
  it can be argued either way.
- OBS-1 (O11): any finding withholds the preference. With one invented quote on the losing option (reports), portal
  still wins on the totals, but the tool returns `blocked_evidence`, preferred null, rc 1. The doc says findings
  "exit 1 when no preferred option survives", which can be read as "a preference can survive a finding". The
  builder's test makes the stricter behaviour deliberate; the doc should say so.

## Disclosures

- Oracle authoring fix after the first run (results/kept, 7/9): E07 switched the G13 source to the g13-gaps contract
  but kept value 5, so the claims were blocked before any confidence downgrade could show. The gaps contract's orders
  value (8) was **taken from the builder's test**, not derived independently.
- v2 added E10 and O11 after the v1 mutation run (first v2 run kept as results/kept/oracle-v2-first-run-3.9.6.json,
  no authoring fix needed).
- v2 harness: a mutant now counts as killed when a row's pass value **or any of its named sub-checks** changes.
  Under v1 the real E02 failure masked the other E02 sub-checks (quote and value checks), so those mutants could not
  be killed.
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there and its branch, index and status are unchanged.
