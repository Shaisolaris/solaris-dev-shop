# M41 r2 validation of G41 9b98d9b (Grok self-validation, not independent review)

Verdict: **PASS with P3 residuals (no P1 or P2), unchanged from M41.** G41 r2 is one clean merge of G40 r3 into the
validated G41 5042950; G41's own files are byte-identical. The inventory still classifies every selected goal the
same way as an independent classification, the gate is honestly NOT_READY, and nothing is applied. The M41 P3
residuals remain, and P3-2 has grown. This is Grok checking a Grok build. It is not independent review and accepts
nothing.

## Binding (raw/binding-verify.txt)
- Candidate 9b98d9b749a32fb5987a12657e2fc9903ab9edb5 on review/grok-g41-release-inventory (remote re-checked,
  unmoved); parents 5042950 (M41-validated G41) and G40 r3 bb44478.
- The merge tree equals `git merge-tree --write-tree 5042950 bb44478` (no hand edit). MANIFEST.sha256 14/14 match and
  equals the diff set. release_candidate.py, examples/capabilities/G41 and tests/test_g41_capability.py: 0 files
  changed since 5042950.

## Live run on root's current records (results/live-inventory-now.json)
Copies of WORK-QUEUE.json and root-qa-20261019 ACCEPTANCE-A, -B, -PR and candidate-index.json (hashes and the M41
11:47 hashes in raw/inputs-sha256.txt; the copies are not published). `inventory --git` on the candidate:
NOT_READY, exit 1, applied false; accepted 38, candidate_only 13, missing 41. The independent classification
(oracle/m41_classify.py, unchanged) agrees on all 84 selected goals; the only differences are the 8 unselected goals
(G26 to G29, M26 to M29), as in M41.

## M41 findings, status at r2
- **P3-1 goals not selected for the week block the gate**: open. M41 oracle R03 `unselected_held_goal_does_not_block`
  fails on all four Pythons (4/5 scored, the same score as M41 on 5042950).
- **P3-2 the inventory trusts a stale candidate index**: open and wider. Remote heads now differ from the index for 15
  goals (raw/remote-heads.txt). Four are reported **accepted** while their branch carries newer, unreviewed commits:
  G01 a069a79 to aa0b083, G19 5606672 to 350d175, G37 9b0f58e to e9b7a77, and now G22 1faee8d to 8bc3553 (G22 h1,
  published in this batch and labelled as needing an affected recheck). G20 is indexed at 8d45038 while its head is
  r3 0d4db69.
- P4-1 and P4-2: unchanged (tool code identical).

## Oracles and results (results/pyversions.txt)
| Python | M41 oracle | G41 tests | inventory_oracle | naive | no-op |
|---|---|---|---|---|---|
| 3.9.6 | 4/5 (R03 P3-1) | OK | 10/10 | 5/10 | 0/10 |
| 3.11.16 | 4/5 | OK | 10/10 | 5/10 | 0/10 |
| 3.12.14 | 4/5 | OK | 10/10 | 5/10 | 0/10 |
| 3.13.15 | 4/5 | OK | 10/10 | 5/10 | 0/10 |

Checkout clean (`--porcelain --ignored` empty) after every run. Full suite on fresh clones (results/full-suite-matrix.txt):
341 tests OK on all four Pythons (2 skipped on 3.9.6); browser processes 0. The M41 G19 stop() flake does not recur
here (G19 h1 is in the lineage).

No proposed fix: there is no P1 or P2. Mutants were not re-scored (tool unchanged since M41). No browser was launched.
