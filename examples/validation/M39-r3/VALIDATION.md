# M39 r3 validation of G39 r3 9ab3562 (Grok self-validation, not independent review)

Verdict: **PASS with P3 findings.** The M39 r2 blocker (P2-1, explicit inputs in four spellings unbound) and
P3-1 (a rewritten exit 2 record still GO) are fixed on all four Pythons. Two further spellings that point inside
ROOT through a `..` segment are still silently unbound (P3-1 below). This is Grok checking a Grok build. It is not
independent review and accepts nothing.

## Own-patch disclosure
G39 r3 applies my own M39 r2 proposed-fix.patch. To avoid grading my own patch with only my own earlier oracle, I
added m39r3_probe.py, which probes path spellings and folder contents that the patch did not name.

## Binding (raw/binding-verify.txt)
- Candidate 9ab356256d5147c89c0f780d4ab639c584971326 on review/grok-g39-delivery-drill (remote head re-checked
  2026-10-19 PDT, unmoved), fast-forward from r2 05378c4.
- G39-r3.patch sha256 9307e322...b9c8 equals `git format-patch --stdout 05378c4..9ab3562`; MANIFEST.sha256 11/11
  match and the manifest set equals the diff set.
- Evaluated in a detached clone ($CANDIDATE); the tree was clean after every run.

## M39 r2 findings, status at r3
| M39 r2 item | Status | Evidence |
|---|---|---|
| P2-1 explicit inputs in four spellings | fixed | contract C01 pass on 3.9.6, 3.11.16, 3.12.14, 3.13.15 (`--flag=VALUE`, folder, absolute inside ROOT bound; symlink refused exit 2) |
| P3-1 rewritten record with exit 2 and ok true gives GO | fixed | contract Q05 `rewritten_record_exit_2_ok_true_verdict`: rc 1, NO_GO, failed |
| P3-2 input rewritten by the run is plain GO | open (documented) | probe Q06: GO, listed in `inputs_changed_during_run` only |
| P3-3 verify exits 0 for GO_WITH_GAPS and EVIDENCED_NO_ORDER | open (documented) | probe Q07 and contract Q05: rc 0 for both |
| P3-4 superseded prerequisites | fixed | r3 merges G05 r2 3056378 and G19 h1 350d175; full suite no longer hits the G19 stop() race |

## New findings
- **P3-1 An input named through a `..` segment is silently unbound.** `_named_inputs` drops any relative argument
  whose parts contain `..` (via `_safe_rel`) instead of normalising it. `inp/../inp/a.csv` and `../d/inp/a.csv`
  (ROOT is `d`) both point inside ROOT, the tool really reads them, and after the file changes verify still says
  **GO** with `claimed_inputs: []` (probe R01, R06; same on all four Pythons). `./inp/a.csv` is bound (R05).
  Lower impact than r2 P2-1 because these spellings are less common, but the failure is silent.
- **P3-2 An absolute input outside ROOT is skipped without a note.** Documented as "cannot be re-checked", but the
  record does not list what it skipped, so a reader of the record cannot tell (probe Q05: GO before and after the
  outside file changed; no mention in the record). Suggest an `unbound_inputs` list in the record.

## Probes that hold
- R02: a named folder holding a symlink to a file outside ROOT is refused at record (exit 2, names the symlink).
- R03, R04: an input reached through a symlinked parent folder is bound, and retargeting that parent is caught.
- R05: `./inp/a.csv` is bound.

## Proposed fix (P3-1; not applied)
proposed-fix.patch (delivery_evidence.py only): a relative argument with a `..` segment is normalised against
ROOT and bound if it stays inside (a symlink at the end is still refused); outside ROOT it is skipped as before.
Positive control (fix-positive-control.txt), on a copy only: probes 6/6, contract 4/4, G39 tests OK.

## Oracles and results (results/pyversions.txt)
| Python | m39r3 probes | M39 r2 contract | M39 oracle | G39 tests | drill | drill_oracle |
|---|---|---|---|---|---|---|
| 3.9.6 | 4/6 | 4/4 | 8/9 | OK | PASSED | 18/18 |
| 3.11.16 | 4/6 | 4/4 | 8/9 | OK | PASSED | 18/18 |
| 3.12.14 | 4/6 | 4/4 | 8/9 | OK | PASSED | 18/18 |
| 3.13.15 | 4/6 | 4/4 | 8/9 | OK | PASSED | 18/18 |

- The one M39 oracle miss is D02 `head_lag_one_tolerated_and_repaired`, the intended r2 behaviour change (as in M39 r2).
  The oracle was not edited.
- Controls (results/controls-3.9.6.txt): drill_oracle naive 12/18, no-op 0/18; contract naive 3/4. The probes give
  naive 4/6 because the naive tool shares the real input binding; they test binding, not the naive shortcuts.
- Full suite on fresh clones (results/full-suite-matrix.txt): 309 tests OK on all four Pythons; browser processes 0.

## Not done in this pass
- The builder's 60-mutant set was not re-scored against these oracles (the builder reports 57/60 with its tests;
  r2_missing_input_ok is equivalent). Disclosed, not claimed.
- No browser was launched.
