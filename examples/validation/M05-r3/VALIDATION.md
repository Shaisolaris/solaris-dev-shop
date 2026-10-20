# M05 r3: affected recheck of G05 r4 (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G05. This is self-validation, not independent review.

- Candidate: G05 r4 `1b840cdee716ceaee3d84e19c23f46e558135b71` on review/grok-g05-revision-bound-evidence, a
  fast-forward of r3 `04b3cf2` (validated by M05 r2, PASS after repair). r4 changes only the oracle file.

## Verdict
PASS. The r3 defect found at integration is fixed on the G05 side. No P1, P2, P3 or P4 in r4 itself.

## The finding r4 repairs (P2, found by the G42 r3 final integration)
On the tree that stacks every newest head, G05's oracle o13, `tests.test_g05_capability` and the full suite
failed on all four Pythons. G01's fixture-runner contract accepts `expectations.gate_codes` only with
`outcome: fail_gate`, and only each fixture kind's own keys; G05 r3's o13 closure fixture used
`expect_blocked: true` with `gate_codes` and the new `subject_revision` / `verified_revision` fields. Neither
candidate is wrong alone; together the integrated tree fails. r4 fixes the fixture form; the key table half is
reconciled in G42 r3, where G01 and G05 meet.

## Results
- **G05 alone, four Pythons:** binding oracle 16/16 and G05 tests OK on 3.9.6, 3.11.16, 3.12.14, 3.13.15.
- **Teeth (oracle/o13_teeth.sh):** on a scratch copy with the stale-revision check in `can_close_finding`
  disabled, o13 fails ("exits 1 0 1") and the oracle reports 14/16. The new fixture form is not weaker.
- **Full suite on fresh clones:** 158 OK on all four Pythons. Browser 0.
- **Binding:** remote head equals 1b840cd; G05-r4.patch equals a regenerated diff of 04b3cf2..1b840cd; manifest
  matches (raw/binding-verify.txt).
- **Integrated tree:** results/g42-interface-test-before-fix.txt is the new G42 interface test failing before the
  G42 r3 reconciliation; the passing run on the final G42 r3 tree is in M42 r3.

## Files
- oracle/o13_teeth.sh
- results/: four-Python table, suite matrix, teeth run, the G42 interface test before the fix
- raw/binding-verify.txt
