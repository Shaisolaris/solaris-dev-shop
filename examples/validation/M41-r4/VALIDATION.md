# M41 r4 validation of G41 r4 b881336 (Grok self-validation, not independent review)

Verdict: **PASS. M41 P3-1 and P3-2 are fixed, and there is no P1 or P2.** Grok checked a Grok build made in the same
batch by the same agent. This is not independent review and accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate b8813367c2a80cb3f0b8aa23b823407d30d6b90a on review/grok-g41-release-inventory, re-checked on the remote.
- It is one commit on top of r3 a1bd6c4, a fast-forward.
- G41-r4.patch equals `git diff --binary a1bd6c4 b881336`. MANIFEST.sha256 matches 3 of 3 files and equals the diff set.

## Findings
- **P3-1, unselected goals blocked the gate: fixed.**
  - M41 oracle R03 `unselected_held_goal_does_not_block` now passes on all four Pythons (5/5 scored; r3 scored 4/5).
  - G41's new Selection test fails at r3 and passes at r4 (results/new-tests-at-r3.txt).
  - On root's real records, the 8 unselected goals (G26 to G29, M26 to M29) are reported `not_selected` and no longer
    count as missing. The independent classification (oracle/m41_classify.py, unchanged) agrees on all 84 selected
    goals (results/independent-classification.txt).
- **P3-2, the tool trusted a stale candidate index: fixed when `--remote-heads` is given.**
  - Live run on a fresh clone at b881336, with the review branches fetched. Inputs are byte-identical to M41 r3
    (raw/inputs-sha256.txt), and the listing is a fresh `git ls-remote` of 139 review branches (raw/remote-heads.txt).
  - Without `--remote-heads` (results/live-inventory-index-only.json): accepted 38, candidate_only 13, missing 33,
    not_selected 8; NOT_READY.
  - With `--remote-heads` (results/live-inventory-remote.json): G01, G11, G19, G22, G34 and G37 become
    acceptance_stale, which is exactly the set FINAL-COHORT reports as "accepted with a newer unaccepted head".
    Eleven candidate_only goals also get a "candidate index is stale" reason. NOT_READY, exit 1, applied false.
  - The 17 goals and head SHAs the tool flags equal the independent list of "index candidate differs from the remote
    review branch head" (G11 has two branches, 9aea147 included).
  - The clone was clean after the runs.
- **Teeth (results/teeth.txt, scripts/m41r4_teeth.py).** Mutants of r4, each scored by G41's tests and the M41 oracle:
  - keep_unselected_blocking: caught by both.
  - ignore_newer_heads, any_differing_head_is_newer and ignore_unknown_heads: caught by G41's tests.
  - **OBS (P4, test gap): word_match_substring survived.** Loosening the goal-id word match is not pinned by any test.
    No current branch name would be misread, because the live run's flagged set equals the independent list.
- **OBS (P4, usability, pre-existing since r1): repeating `--acceptance` keeps only the last file** (argparse
  nargs="+" without append).
  - My first live run passed `--acceptance A --acceptance B --acceptance PR` and silently got 4 accepted instead of 38.
  - It fails closed (NOT_READY), and the documented form (one flag, every file after it) is correct.
  - Root may want `action="extend"` or a refusal of the repeated flag.
- Remote-head checks cover only branches that descend from an indexed or accepted revision. M validation branches
  start from main, so they are not compared (disclosed in the doc).
- P4-1 and P4-2 from M41 r2: unchanged.

## Oracles and results (results/pyversions.txt)
| Python | M41 oracle | G41 tests | inventory_oracle | naive | no-op |
|---|---|---|---|---|---|
| 3.9.6 | 5/5 | OK | 10/10 | 5/10 | 0/10 |
| 3.11.16 | 5/5 | OK | 10/10 | 5/10 | 0/10 |
| 3.12.14 | 5/5 | OK | 10/10 | 5/10 | 0/10 |
| 3.13.15 | 5/5 | OK | 10/10 | 5/10 | 0/10 |

The checkout was clean after every run. Full suite on fresh clones at b881336 (results/full-suite-matrix.txt): 347 OK
on all four Pythons (5 skipped on 3.9.6). Browser processes: 0. No browser was launched.
