# M31 r3 validation of G31 r4 e809a4f

- Verdict: PASS. M31 r2 P4-1 is closed. No P1, P2, P3 or P4 in r4. One new observation; the two older OBS stand.
- This is Grok checking a Grok build. Grok self-validation, not independent review. It accepts nothing.

## What is being checked
- M31 r2 validated G31 r3 fcf492a and left P4-1: `qualified_by` only covered commitments that name a requirement in the conflict.
- Since then on review/grok-g31-scope-acceptance: e809a4f G31 r4 (raw/binding-verify.txt). A resolved conflict now qualifies commitments on its requirements and on the inputs they trace.

## Probe (oracle/m31r3_probe.py)
Written for this pass from P4-1 and the doc's Contradictions section. Inputs chosen here, not copied from the G31 r4 test.
- Q1: declared R2/R3 conflict resolved; commitments on IN2 and IN3 are qualified, on IN4 and A1 (traced by R1, not in the conflict) are not.
- Q2: the text report prints the qualification on the input-only commitment line.
- Q3: two resolved conflicts on R2; a commitment on IN2 lists both ambiguities, one on IN1 only the R1/R2 one.
- Q4, Q5: controls (a requirement-named commitment stays qualified; no conflict, nothing qualified).
- Q6 (OBS): an open conflict and a commitment on the traced input only.

## Results
- G31 r3 fcf492a: 2/5 (Q1, Q2 and Q3 fail; the input-only commitments are unqualified) (results/probe-r3-fcf492a-3.9.6.txt).
- G31 r4 e809a4f: 5/5 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r4-four-python.txt).
- Harness error, disclosed: the first Q3 run used ambiguity ids AMB1 and AMB2, which the fixture already has, so the tool refused the package as a duplicate id (exit 2). Renamed to AMBK and AMBL; no tool change.
- Existing reproducer, the M31 r2 probe: 11/11 on all four Pythons; its P14 observation now prints `qualified_by = ['AMBX']`. Builder scope_oracle ACCEPTED 12/12 on all four (results/reproducer-m31r2-and-oracle.txt).
- New builder test fails on fcf492a (results/new-test-at-fcf492a.txt).
- Full suite on fresh clones: 176 OK on all four Pythons. Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **OBS-1 (new):** with an open conflict, a commitment that rests only on a traced input gets no finding of its own (Q6). The report is blocked anyway by `open_ambiguity` on the requirements, so nothing ships; the commitment line just does not say why.
- **OBS (from M31 r2, unchanged):** negated terms are still flagged (fails closed); a requirement excluded from scope that conflicts with an in-scope one is not a finding.

Browser launches for this pass: 0.
