# M33 r2 validation of G33 r2 evidence-backed product decision (Grok self-validation, not independent review)

Candidate: G33 r2 `861167dd854156f69c6d4a62734ca6c6e45b81d1` (branch review/grok-g33-evidence-decision), direct parent
G33 r1 `d63b1c146cf534f9b8575b0a61a51fa03c5b0c19`, on G13 r3 `5666e7beb161d1252ddd5dcc0a166aca83255370`. Tool
`employees/product-project/product-manager/evidence_decision.py`, doc `evidence-product-decision.md`. Validator: Grok,
the same agent family that built G33. This is self-validation, not independent review. Pass started 09:18 PT, Mon
Oct 19 2026.

## Verdict

PASS (self-validation) with one P3 (which already existed in r1) and one P4. No P1 or P2, so no proposed fix.

Both M33 P3 findings are repaired:
- Top-level `adoption` (and `adoption_rate`, `assumed_adoption`) is refused with exit 2 and nothing written.
- A quantity claim without a numeric value is flagged, and the detail says so when the quote has no number.

M33 OBS-1 is now a documented rule, and the tool follows it: any blocking finding withholds the preference.

## Prerequisite chain

- The format-patch sha equals the patch file and the handback (`f8cec425...7ed`). The manifest has 5/5 entries with
  0 mismatches and its set equals the diff set. d63b1c1 is the direct parent, and its parent is G13 r3 5666e7b
  (raw/binding-verify.txt).
- The remote heads of G33 and G13 are still 861167d and 5666e7b, so nothing in the chain is superseded. G13 r3 was
  validated by M13 r3 (db6028e, PASS); G33 r1 by M33 (4b491d7, PASS with P3-1 and P3-2).
- The r2 fix was written by the builder from the M33 findings. M33 proposed no patch, so no own-patch fix is
  involved. The builder's run of a copy of my M33 oracle (in its handback) is a builder re-run, not this validation.

## Method

- Oracle `oracle/m33r2_oracle.py`: the M33 v2 oracle (independent Decimal model, written from the doc), unchanged in
  E01-E10 and O11, plus three new rows:
  - E11: the r2 doc rule. One blocked claim on a losing option gives blocked_evidence, preferred null and exit 1,
    and the clean package still prefers portal.
  - E12: the r2 repairs and probes beyond them:
    - adoption, adoption_rate, assumed_adoption, tam and market_size refused whatever the value ("35%", 0.35, null,
      0, "");
    - quantity as "true", 1 or null refused, and false behaving like absent;
    - a quantity claim used with 40 or "40 dollars" and flagged with no value (with the numberless-quote detail),
      with "ten", with "4" (a fragment of the quote's 40) or with a JSON number;
    - a metric-scale value "18" that is a fragment of the quote's "18,000".
  - O13 (OBS): refused-key spelling variants (TAM, Adoption, market-size, marketSize), a nested decision.adoption,
    and the value "40,0".
- The same oracle on the r1 tool (results/r1-tool-oracle-3.9.6.json) fails exactly the repaired subs: E02 top_adoption,
  E10 numberless quote, and in E12 the adoption refusals, the quantity type checks, the numberless detail and the
  spelled-out value. It also fails the two fragment subs, which shows that P3-1 already existed in r1.
- The first run is the final run: no authoring fix was needed (kept as results/kept/oracle-first-run-3.9.6.json).
- Four interpreters; mutation tests on 3.13.15 and 3.9.6 with the builder's 38 r2 mutants copied unchanged; a fresh
  caller. All runs were on rsync copies, and the candidate was never modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g33: Ran 19 tests in 8.888s  OK  | full: Ran 143 tests in 23.287s  OK  | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 1/10 | builder-noop: REJECTED 1/10 | m33-oracle: M33 ORACLE 13/14 core FAIL | m33-naive: M33 ORACLE 2/14 core FAIL | m33-noop: M33 ORACLE 2/14 core FAIL
== 3.11.16 | g33: Ran 19 tests in 6.826s  OK  | full: Ran 143 tests in 15.889s  OK  | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 1/10 | builder-noop: REJECTED 1/10 | m33-oracle: M33 ORACLE 13/14 core FAIL | m33-naive: M33 ORACLE 2/14 core FAIL | m33-noop: M33 ORACLE 2/14 core FAIL
== 3.12.14 | g33: Ran 19 tests in 6.684s  OK  | full: Ran 143 tests in 15.660s  OK  | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 1/10 | builder-noop: REJECTED 1/10 | m33-oracle: M33 ORACLE 13/14 core FAIL | m33-naive: M33 ORACLE 2/14 core FAIL | m33-noop: M33 ORACLE 2/14 core FAIL
== 3.13.15 | g33: Ran 19 tests in 6.214s  OK  | full: Ran 143 tests in 14.898s  OK  | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 1/10 | builder-noop: REJECTED 1/10 | m33-oracle: M33 ORACLE 13/14 core FAIL | m33-naive: M33 ORACLE 2/14 core FAIL | m33-noop: M33 ORACLE 2/14 core FAIL
pycache in copy: 0
candidate status lines: 0
```

The oracle scores 13/14 on every interpreter. The only failing subs are the two E12 fragment checks (P3-1), so E12 fails;
E01-E11 pass, O11 and O13 are OBS. The naive and no-op controls score 2/14.

Mutation tests: **37/38 killed on 3.13.15 and 37/38 on 3.9.6** (results/teeth-*.log). The M33 survivor
prefer_despite_findings is now killed by E11. Survivors, each checked with the builder's G33 tests:

- teeth-3.13.15.log: no_atomic_out SURVIVED
- teeth-3.9.6.log: no_atomic_out SURVIVED
- builder tests: no_atomic_out builder tests: KILL FAILED (failures=1) FAIL: test_atomic_out_uses_replace (tests.test_g33_capability.G33Capability.test_atomic_out_uses_replace)

Fresh caller (results/fresh-caller.txt): the README demo, verbatim under `env -i` with a new HOME, on 3.9.6 and
3.13.15:
- The decision is PREFERRED portal; C10 is excluded as stale with its verify entry, and C9 as outside the ICP.
- The builder oracle gives ACCEPTED 10/10, and the naive and no-op controls REJECTED 1/10.
- The demo ends with exit 1 because its last line is the documented REJECTED control.
- No __pycache__ was written and the tree is unchanged.

## Findings

- **P3-1 (already in r1): a claim's value only has to occur as a substring of its quote, so a digit fragment of the
  stated number passes.**
  - On the metric-scale dimension `proof`, with S-mkt fresh, C10 with value "18" and stated score 3, from the quote
    "...North America: 18,000.", is used with score 3 at exit 0 and no finding. The quote's number gives score 5.
  - On a quantity dimension, value "4" from a quote that says "40 dollars" passes the new r2 gate.
  - The doc says the value must "appear in its quote", and the r2 text says "a numeric value that appears in its
    quote". A fragment is not the number the source states. Matching the value against whole numbers in the quote
    (for example NUM.findall(quote)) would close it.
- **P4-1: refused keys are matched only in exact lowercase.** Top-level `TAM`, `Adoption`, `market-size` and
  `marketSize` are accepted with exit 0 (they are ignored, and nothing is computed from them). A nested
  `decision.adoption` is also accepted, which the doc covers ("top-level keys") and handback question 3 raises.
- OBS:
  - Spelled-out numbers ("ten") are flagged, not parsed (handback question 1).
  - "40,0" is flagged as not in the quote.
  - Flagging rather than refusing a numberless quantity claim withholds the whole preference (handback question 2,
    consistent with E11).

## Disclosures

- The r2 repair addresses my own M33 findings. The patch is the builder's.
- No oracle authoring fixes and no harness fixes were needed in this pass. Scripts are copies of the M33 ones with
  paths changed to M33-r2 (scripts/).
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there, and its branch, index and status are unchanged.
