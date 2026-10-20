# M33 r3 validation of G33 r3 (whole-number value matching), with r4 repair (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G33. This is self-validation, not independent review.

- Candidate: G33 r3 `327e631916db17170850d62d72479e13c89249dd` on review/grok-g33-evidence-decision. It answers the
  root finding (M33 r2 P3-1): a value only had to be a substring of its quote, so 18 matched 18,000.
- Repair: G33 r4 `a4ae555bdabffdc932b279d97ed2928bdef73df5`, one fast-forward commit, for the P2 below.

## Verdict
PASS after repair. r3 had one P2. r4 fixes it. M33 r2 P3-1 is closed. Three OBS remain.

## Method
- Probe `oracle/m33r3_probe.py` was written from the r3 doc before reading the r3 tests. Unit rows call
  `_value_in_quote`; decide rows edit the fixture's market snapshot (sha256 recomputed) and claim C10, run
  `decide --json`, and check the findings. 12 scored rows, 3 OBS.
- The prior M33 and M33 r2 oracles were rerun on r3 and r4.
- The builder's evidence_oracle and its naive and no-op controls ran on four Pythons. The full suite ran on fresh
  clones on four Pythons.

## Results
- **Probe:** 12/12 on r4 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15. 5/12 on r3. 2/12 on r2.
- **Prior oracles:** M33 11/11 core and M33 r2 14/14 core on r3 and r4.
- **Builder oracle:** 11/11 on four Pythons. naive and no-op each 1/11.
- **Full suite:** 145 OK on four Pythons at a4ae555. Browser 0.
- **Binding:** remote head equals a4ae555; handback patch equals a regenerated diff; manifest matches
  (raw/binding-verify.txt).

## Findings
- **P2-1 (fixed in r4): odd numeric values fell back to substring matching.** r3 compares a value as a whole
  number only when `_num` can read it. Anything else goes back to the old substring rule, but the scorer still
  reads it as a number. On r3:
  - "1,5" matches "surveyed 11,500" and is scored as 15 (score 3 at exit 0; the quote's number gives 5) (D09).
  - "+18" matches "+180" (D10). "-5" matches "-50" (D11).
  - The same holds on a quantity dimension (D13).
  This is the root finding through another door. r4 refuses such values (value_not_in_quote) and keeps the
  substring rule only for values that are not numbers. Its new test fails on r3.
- **OBS: "18%" does not match "18 %"** (a space before the sign). This fails closed.
- **OBS: "18.0" matches "18".** They are the same number.
- **OBS: "18" matches the European "18.000".** The tool reads "." as a decimal point. A source that uses "." for
  thousands needs its value written as stated in the source's own convention; the doc could say this.
- Root rows that pass on r3 and r4: 18 vs 18,000 (E01), 18000 vs 18,000 (E02), 0.5 vs 10.5 (E08), fullwidth digits
  (E12), and the plain 11,500 claim with no finding (D12).

## Files
- oracle/m33r3_probe.py
- results/: probe per Python and per revision, prior oracles per revision, builder oracle, suite matrix
- raw/binding-verify.txt
