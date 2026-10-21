# M33 r4 validation of G33 r5 25c0075

- Verdict: PASS. Two of the three M33 r3 OBS are closed (18% vs "18 %" now matches and a plain 18 no longer does; the decimal-point convention is documented). The third ("18.0" matches "18") is the same number and stays by design. No P1 to P4. One new OBS.
- This is Grok checking a Grok build. Grok self-validation, not independent review. It accepts nothing.

## What is being checked
- M33 r3 validated G33 r4 a4ae555 and left three OBS.
- Since then on review/grok-g33-evidence-decision: 25c0075 G33 r5 (raw/binding-verify.txt). In a quote a percent sign after one space (plain, no-break or narrow no-break) is part of the number; the doc states the rule and that `.` is a decimal point.

## Probe (oracle/m33r4_probe.py)
Written for this pass from the M33 r3 OBS rows and the r5 doc. Inputs chosen here, not copied from the G33 r5 test.
- R01: a percent after one space matches the percent value; `3,5 %` is not `3.5%`.
- R02: a plain value no longer matches a number written as a percent after a space (fails closed).
- R03: boundaries hold with the space (`7%` never matches `17 %` or `7.5 %`; `1,000 %` keeps its percent).
- R04: the documented decimal-point convention (`18.000` reads as 18; `18,000` as eighteen thousand).
- R05: the doc states both rules.
- R06 (OBS): a thin space U+2009 before `%`.
- R07: regression, `decide --json` on the shipped fixture equals G33 r4 (package sha excluded).

## Results
- G33 r4 a4ae555 on 3.9.6: 1/5 (R01, R02, R03 and R05 fail; R07 needs a second tree and was not run there) (results/probe-r4-a4ae555-3.9.6.txt).
- G33 r5 25c0075: 6/6 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r5-four-python.txt).
- Existing reproducer, the M33 r3 probe: 12/12 on all four Pythons; OBS E03 (18% vs "18 %") now reads True. Builder evidence_oracle ACCEPTED 11/11 (results/reproducer-m33r3-and-oracle.txt).
- New builder test fails on a4ae555 (results/new-test-at-a4ae555.txt).
- Full suite on fresh clones: 146 OK on all four Pythons. Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **OBS-1 (new):** a thin space (U+2009) or two spaces before `%` are not read as part of the number. `7%` then does not match (fails closed).
- **OBS (by design):** "18.0" matches "18"; "18" matches the European "18.000", as the doc now says.

Browser launches for this pass: 0.
