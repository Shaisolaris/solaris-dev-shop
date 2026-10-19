# M31 validation of G31 scope, estimate and acceptance gate (Grok self-validation, not independent review)

Candidate: G31 `37f42b085c20bd7fbb1a43434e4367bb7fc411f8` (branch review/grok-g31-scope-acceptance), direct parent
G17 `550f1848a76ad4d5b6688090afc0519354ac3370`. Tool `employees/product-project/business-analyst/scope_acceptance.py`,
doc `scope-estimate-acceptance.md`. Validator: Grok, the same agent family that built G31. This is self-validation and
does not replace an independent review. Pass window 06:53 to about 08:08 PT, Mon Oct 19 2026.

## Verdict

PASS (self-validation) with one P3 finding and OBS notes. No P1 or P2 findings, so no proposed-fix patch.

## Prerequisite chain

- The patch sha equals the diff sha (`9025553c...a178`); the manifest has 34/34 entries with 0 mismatches and its set
  equals the diff set. 550f184 is the direct parent (raw/binding-verify.txt).
- G17 550f184 was validated by M17 at ed85c95 (PASS with P4-1: the handback names the wrong prerequisite branch). G31
  loads G17's evaluate() by file path, so G17's behaviour is part of this candidate; M31 did not re-test G17 beyond K07.
- Nothing in the chain is superseded as far as the branch listing shows (550f184 is still the head of
  review/grok-g17-resource-decision).

## Method

- Fresh oracle `oracle/m31_oracle.py` (v2), written from M31.md, G31.md and the doc before I read the builder's oracle.
  It keeps an independent Decimal model of hours, half-up cents and capacity dates, and drives the CLI on edited copies
  of the G31 fixtures in fresh temp dirs.
- Core rows:
  - K01 clean control (230/310/440 h, 34500.00 to 66000.00, capacity finish 2027-02-07) against an independent sum.
  - K02 invented and out-of-scope commitments block.
  - K03 traceability: untraced, missing dependency, silent exclusion and no acceptance criteria block; an optional
    unlisted requirement is fine.
  - K04 demo evidence: changed, missing, failing, late and wrong-capability records and no record block; a re-pinned
    passing record is fine.
  - K05 ambiguity: vague words and missing measures need an escalation; an open one blocks and is listed with its owner;
    no false hit on "breakfast".
  - K06 estimates: hours and cents mismatches, half-up 8.63 not 8.62 at rate 0.0375, stale hours after a scope change,
    and the fixed-estimate rules.
  - K07 dates: 2027-02-07 is ok and 2027-02-06 blocked; no capacity, an edited stored G17 result and an infeasible
    option block.
  - K08 invalid or late input is never ready.
  - K09 acceptance: changed or missing evidence, a failed criterion and a blocked scope never accept; unknown or
    repeated criteria are invalid; a late result never accepts.
  - K10 recovery: --out refuses the package path, an invalid run keeps the earlier result, verify names an edited or
    truncated result.
  - K11 seeded soak: 12 random estimate sets reconcile exactly; one cent off is a mismatch.
  - K12 (v2, added after the v1 mutation run): an other-kind commitment with no refs, a capability without a demo, a
    fixed price that is not hours x rate, a criterion-level escalation and a dependency cycle.
- OBS rows (always pass, they record behaviour): O12 contradictory requirements, O13 a mixed known and unknown trace.
- Controls: the real tool scores 12/12 on every interpreter; naive_scope and noop_scope score 0/12.
- Four interpreters, mutation tests on 3.13.15 and 3.9.6 with the 41 builder mutants copied unchanged, and a fresh
  caller (README demo verbatim under `env -i` with a new HOME). All of it ran on rsync copies; the candidate was never
  modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g31: Ran 22 tests in 14.206s  OK  | full: Ran 171 tests in 43.682s  OK  | builder-oracle: ACCEPTED 11/11 | builder-naive: REJECTED 1/11 | builder-noop: REJECTED 1/11 | m31-oracle: M31 ORACLE 12/12 core PASS | m31-naive: M31 ORACLE 0/12 core FAIL | m31-noop: M31 ORACLE 0/12 core FAIL
== 3.11.16 | g31: Ran 22 tests in 11.998s  OK  | full: Ran 171 tests in 38.258s  OK  | builder-oracle: ACCEPTED 11/11 | builder-naive: REJECTED 1/11 | builder-noop: REJECTED 1/11 | m31-oracle: M31 ORACLE 12/12 core PASS | m31-naive: M31 ORACLE 0/12 core FAIL | m31-noop: M31 ORACLE 0/12 core FAIL
== 3.12.14 | g31: Ran 22 tests in 8.972s  OK  | full: Ran 171 tests in 30.165s  OK  | builder-oracle: ACCEPTED 11/11 | builder-naive: REJECTED 1/11 | builder-noop: REJECTED 1/11 | m31-oracle: M31 ORACLE 12/12 core PASS | m31-naive: M31 ORACLE 0/12 core FAIL | m31-noop: M31 ORACLE 0/12 core FAIL
== 3.13.15 | g31: Ran 22 tests in 10.679s  OK  | full: Ran 171 tests in 39.847s  OK  | builder-oracle: ACCEPTED 11/11 | builder-naive: REJECTED 1/11 | builder-noop: REJECTED 1/11 | m31-oracle: M31 ORACLE 12/12 core PASS | m31-naive: M31 ORACLE 0/12 core FAIL | m31-noop: M31 ORACLE 0/12 core FAIL
pycache in copy: 0
candidate status lines: 0
```

Mutation tests: **v2 oracle 40/41 killed on 3.13.15 and 40/41 on 3.9.6** (results/teeth-*.log). The v1 oracle killed
35/41 on both (results/v1); its six survivors (cycle_ok, unknown_trace_ok, no_demo_ok, criterion_amb_ignored,
fixed_price_unchecked, invented_ok) led to row K12. The builder reports 41/41 killed on 3.12 and 3.9 with its own
tests and oracle. Survivor and its check against the builder's tests:

- teeth-3.13.15.log: unknown_trace_ok SURVIVED
- teeth-3.9.6.log: unknown_trace_ok SURVIVED
- builder tests: unknown_trace_ok builder tests: KILL FAILED (failures=1) FAIL: test_untraced_requirement (tests.test_g31_capability.G31Capability.test_untraced_requirement)

- unknown_trace_ok survives my oracle because my only probe of it is the OBS row O13, which does not score: the doc's
  "no known input or assumption" can be read either way for a requirement with one known and one unknown trace. The
  builder's test_untraced_requirement kills it on both versions, so the suite as a whole is not blind to it.

Fresh caller (results/fresh-caller.txt): on 3.9.6 and 3.13.15 check prints READY, accept prints ACCEPTED and the
builder oracle ACCEPTED 11/11. The demo script exits 1 because its last line runs the noop oracle, which is expected
to print REJECTED 1/11. No __pycache__ in the copy and the tree is unchanged. On 3.9.6 the new HOME gains
Library/Caches/com.apple.python, which Apple's interpreter creates, not the tool.

## Findings

- **P3-1: contradictory requirements are not detected or escalated, and the doc does not say so.** O12 gives R1
  "24/7" and R6 "closed outside office hours" in one package; check reports `ready` with no findings (rc 0). The doc
  lists vague wording, missing measures and open ambiguity as blocking, but a direct contradiction between two in-scope
  requirements passes silently. Either detect it (for example an explicit `conflicts_with` field) or state in the doc
  that contradictions are the analyst's job and not checked.
- OBS-1 (O13): a requirement with one known and one unknown trace is reported `untraced_requirement`. That is the
  stricter reading of "no known input or assumption"; the doc should say whether every trace must resolve.
- OBS-2: the README demo ends on the noop oracle, so running the demo as a script always exits 1. Harmless, but a
  caller may read it as a failure.

## Disclosures

- Oracle authoring fixes after the first run (first run kept as results/kept/oracle-authoring-run-3.9.6.json, 9/11):
  K09 accepts a deleted evidence file being reported as either `missing_evidence` or `evidence_mismatch` (the doc
  allows both readings); K11's generator could produce low > likely, and now enforces likely >= low + 1.
- Oracle v1 to v2: K12 was added after the v1 mutation run to cover the six v1 survivors. v1 is kept as
  oracle/m31_oracle_v1.py with its results in results/v1.
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there and its branch, index and status are unchanged.
