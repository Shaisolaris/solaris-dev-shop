# M41 r3 validation of G41 r3 a1bd6c4 (Grok self-validation, not independent review)

Verdict: **PASS with P3 residuals (no P1 or P2), unchanged from M41 r2.** G41 r3 is one clean merge of G40 r4 into
G41 r2 9b98d9b; G41's own files are byte-identical. The inventory still classifies every selected goal the same way
as an independent classification, the gate is honestly NOT_READY, and nothing is applied. This is Grok checking a
Grok build made in the same batch by the same agent. It is not independent review and accepts nothing.

Naming: a1bd6c4's commit subject says "G41 r2" in error; 9b98d9b was G41 r2, so this pass calls a1bd6c4 G41 r3.

## Binding (raw/binding-verify.txt)
- Candidate a1bd6c41641c9849912c93e9dbe8db7a13229b55 on review/grok-g41-release-inventory (remote re-checked);
  parents 9b98d9b (M41 r2-validated) and G40 r4 eabf69a.
- The merge tree ff6c2b5 equals `git merge-tree --write-tree 9b98d9b eabf69a` (no hand edit). G41-r3.patch equals
  `git diff --binary 9b98d9b a1bd6c4`; MANIFEST.sha256 4/4 match and equals the diff set (the G40 r4 files only).
  release_candidate.py, examples/capabilities/G41 and tests/test_g41_capability.py: 0 files changed since 9b98d9b.

## Live run on root's current records (results/live-inventory-now.json)
Copies of WORK-QUEUE.json and root-qa-20261019 ACCEPTANCE-A, -B, -PR and candidate-index.json (hashes in
raw/inputs-sha256.txt; the copies are not published). `inventory --git` on the candidate: NOT_READY, exit 1, applied
false; accepted 38, candidate_only 13, missing 41, the same as M41 r2. The independent classification
(oracle/m41_classify.py, unchanged) agrees on all 84 selected goals; the only differences are the 8 unselected goals
(G26 to G29, M26 to M29).

## M41 r2 findings, status at r3
- **P3-1 goals not selected for the week block the gate**: open. M41 oracle R03 `unselected_held_goal_does_not_block`
  fails on all four Pythons (4/5 scored, as in M41 and M41 r2).
- **P3-2 the inventory trusts a stale candidate index**: open. Remote heads differ from the index for 15 goals
  (raw/remote-heads.txt). G01, G19, G22 and G37 are reported accepted while their branches carry newer unaccepted
  commits; G38 is indexed at 01c9afb while its head is r4 ba70b69, and G40 at 8428c90 while its head is r4 eabf69a.
- P4-1 and P4-2: unchanged (tool code identical).

## Oracles and results (results/pyversions.txt)
| Python | M41 oracle | G41 tests | inventory_oracle | naive | no-op |
|---|---|---|---|---|---|
| 3.9.6 | 4/5 (R03 P3-1) | OK | 10/10 | 5/10 | 0/10 |
| 3.11.16 | 4/5 | OK | 10/10 | 5/10 | 0/10 |
| 3.12.14 | 4/5 | OK | 10/10 | 5/10 | 0/10 |
| 3.13.15 | 4/5 | OK | 10/10 | 5/10 | 0/10 |

Checkout clean after every run. Full suite on fresh clones at a1bd6c4 (results/full-suite-matrix.txt, the G41 r3
builder run, reused and disclosed): 345 tests OK on all four Pythons (5 skipped on 3.9.6); browser processes 0.

No proposed fix: there is no P1 or P2. Mutants were not re-scored (tool unchanged). No browser was launched.
