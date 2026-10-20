# M11 h1: affected recheck of G11 h1 94a0de4 (Grok self-validation, not independent review)

Verdict: **PASS with one P4 and one observation.** G11 h1 closes the proposed P2 that G18 cross-check x2 carried
(M18 ce0f3b0): a supplied G10 trace that G10 refuses, or that has no capture time, is no longer dropped silently in
front of a rollback. Every supplied trace now has a line in the decision trace, the blocking cases become
insufficient_evidence, the G18 cross-checks turn clean with G11 h1 in place, and nothing else in G11 moved. This is
Grok checking a Grok build. It is not independent review and accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate 94a0de462a82e0d55e1bf58ee468bf7953d1c59a, current remote head of review/grok-g11-incident-slo.
- Accepted G11 r3 13ba7055537e305732856aea3c74ff28f0848be8 is its direct parent (1 commit). The handback G11-h1.patch
  equals `git diff --binary 13ba705 94a0de4`. MANIFEST.sha256 13/13 match the tree.
- Diff scope: incident_slo.py (`_decide` only), incident-slo.md (rollback step 5), tests/test_g11_capability.py (one new
  test). netdiag.py, the G11 oracle and every G11 fixture are unchanged.

## Code review of `_decide`
The G10 loop still runs only after the burn-rate check, so decisions 1 to 4 are untouched. A usable dns, route or tls
trace inside the impact still returns do_not_rollback at once. A refused trace, or an untimed trace whose verdict would
exclude the application, is collected; after the loop any such trace returns insufficient_evidence naming every one of
them and the revision. Untimed traces that do not exclude the application, and traces outside the impact, only add a
trace line. The exclusion test is the same expression as before, so x1 layer agreement cannot drift.

## Checks I wrote for this pass
- **oracle/m11h1_probe.py, 15 cases** (results/probe-h1-*.txt): untimed route, tls and both probable-tls traces block;
  an untimed undetermined or healthy trace is listed and the rollback stands; two refused traces are both named; a
  trace file that is not JSON is refused by G10 and blocks; a trace from the next day is listed as not used; a timed
  application trace plus an untimed dns trace blocks; a refused trace on the clean control stays do_not_rollback; a
  refused trace with a migration and no snapshot gives insufficient_evidence (step 5 comes before step 6); fixture 03
  is unchanged; the text report states the reason. 15/15 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15.
- **Defect first, rechecked** (results/probe-accepted-13ba705-*.txt): the same probe on 13ba705 fails 12 of 15 cases
  on all four Pythons (rollback with no G10 line, or a missing trace line).
- **G18 cross-checks, unmodified script** (results/g18-crosschecks-*.txt): on G18 fd94c64 as published, 2 x2 findings on
  all four Pythons; on the same tree with the G11 h1 incident_slo.py and doc overlaid, CROSS-CHECKS CLEAN (x1 12
  fixtures agree, x2 both cases insufficient_evidence with the trace mentioned, x3 unchanged) on all four.
- **G11 oracle** on h1: ACCEPTED 14/14 on all four Pythons (results/g11-oracle-h1-*.txt).
- **Full suite** on a clean tree at 94a0de4: 193 tests OK on 3.9.6, 3.11.16, 3.12.14 and 3.13.15
  (results/full-suite-matrix.txt). Browser not used.

## Findings
- **P4-1, wording.** For a G10 `probable` verdict with several non-application candidates (G10 fixtures 07 and 12), the
  reason says the trace "places the fault at the tls layer", which is firmer than G10's own verdict. The decision is
  right (the application is not a candidate), only the wording overstates. No fix proposed.
- **OBS.** When no rollback is on the table (no budget-burning minute, impact before the change, low burn), a refused
  trace still has no line in the decision trace; it shows only in the timeline as an unreadable trace. That is the safe
  direction and matches the doc, which scopes the rule to the G10 step.
- No P1, P2 or P3.

## Follow-up for the stack
G18 reports NOT_INTEGRATED only because of x2. A G18 refresh that stacks G11 h1 should report the stack integrated;
G42 r3 still carries G11 13ba705.
