# M31 r2 validation of G31 r2 (contradiction boundary), with r3 repair (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G31. This is self-validation, not independent review.

- Candidate: G31 r2 `e998d2b434c082fe4cf129cec89dbeae458d8690` on review/grok-g31-scope-acceptance, which
  answers M31 P3-1 (contradictory requirements were not detected or escalated).
- Repair: G31 r3 `fcf492af1ba12599503fe2d25202d3d1a40f2059`, one fast-forward commit, for the P2 below.

## Verdict
PASS after repair. r2 had one P2. r3 fixes it. M31 P3-1 is closed. One P4 and two OBS remain.

## Method
- Probe `oracle/m31r2_probe.py` was written from the r2 doc (Contradictions section and finding table) before
  reading the r2 tests. It copies the fixture folder, edits portal.json, runs `check --json`, and checks the exit
  code and finding codes. 11 scored cases, 3 OBS.
- The prior M31 oracle (grok-output/M31/oracle/m31_oracle.py) was rerun on r1, r2 and r3.
- The builder's scope_oracle and its naive and no-op controls ran on four Pythons. The full suite ran on fresh
  clones on four Pythons.

## Results
- **Probe:** 11/11 on r3 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15. 10/11 on r2 (P07 fails). 2/11 on r1.
- **Prior M31 oracle:** 12/12 core on r1, r2 and r3. Its O12 row (contradictory requirements) now records
  `unresolved_conflict`, where r1 was ready.
- **Builder scope_oracle:** 12/12 on four Pythons. naive and no-op each 1/12.
- **Full suite:** 175 OK on four Pythons at fcf492a. Browser 0.
- **Binding:** remote head equals fcf492a; handback patch equals a regenerated diff; manifest matches
  (raw/binding-verify.txt).

## Findings
- **P2-1 (fixed in r3): two commitments that contradict each other were `ready`.** The r2 doc says the texts
  compared include commitment texts, and any two texts of one proposal on opposite sides of a family are a
  contradiction. The code compared each commitment only with requirement-side texts. P07 adds "Support desk
  answers 24/7" and "Support desk answers during office hours only" on neutral requirements: r2 exits 0 with no
  finding. r3 gives `conflicting_commitment` on both. Its new test fails on r2.
- **P4-1: `qualified_by` only covers commitments that name a requirement in the conflict.** P14: with the R3/R4
  conflict resolved, a commitment of kind other that rests only on IN3 (the input R3 traces) has an empty
  `qualified_by`. The doc's wording ("commitments resting on those requirements") permits this. Low impact.
- **OBS: negated terms are still flagged.** P13 "no offline mode" vs "online only" is reported as a conflict.
  This fails closed: the owner adds a resolved ambiguity.
- **OBS: a requirement excluded from scope that conflicts with an in-scope one is not a finding** (P12), as the doc
  and the r2 tests say.
- Root boundary checks that pass on r2 and r3: declared conflicts_with (P02), cross-requirement terms (P03),
  resolved ambiguity gives ready plus `qualified_by` (P04), open ambiguity blocks and escalates (P05), commitment vs
  criterion (P06), both sides in one text (P08), requirement vs its own input (P09), an ambiguity covering one side
  only does not settle it (P10), case-insensitive matching (P11).

## Files
- oracle/m31r2_probe.py
- results/: probe per Python and per revision, M31 oracle per revision, builder oracle, suite matrix
- raw/binding-verify.txt
