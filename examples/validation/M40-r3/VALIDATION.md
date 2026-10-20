# M40 r3 validation of G40 r3 bb44478 (Grok self-validation, not independent review)

Verdict: **FAIL (one P2).** The M40 P2-1 fix works: wheel-smoke no longer writes into the checkout and a stale
build/lib in REPO is not packed. But the same fix deletes a `src/` folder that already exists inside a user's
`--outside` folder, and then says "Nothing was written" (P2-1 below). This is Grok checking a Grok build. It is not
independent review and accepts nothing.

## Own-patch disclosure
The defect is in the lines G40 r3 took from my own M40 proposed-fix.patch (`if srcdir.exists(): shutil.rmtree(srcdir)`).
My M40 positive control used fresh temporary folders only, so it never tried an existing `--outside`. I found it here
with a probe written for this pass, not with my M40 oracle.

## Binding (raw/binding-verify.txt)
- Candidate bb444782e65fa2ea1ca790a335faf7f3917b3191 on review/grok-g40-fresh-install (remote re-checked, unmoved),
  fast-forward from r2 0f593a1.
- G40-r3.patch sha256 7650631b...8e2b equals `git format-patch --stdout 0f593a1..bb44478`; MANIFEST.sha256 14/14 match;
  manifest set equals the diff set.
- Evaluated in a detached clone; `git status --porcelain --ignored` was empty after every run.

## M40 findings, status at r3
| M40 item | Status | Evidence |
|---|---|---|
| P2-1 wheel-smoke edits REPO; stale build/lib shipped | fixed | M40 oracle A06, A07 pass on 3.11.16 (8/8); checkout ignored-file count 0 after all runs |
| P3-1 `--outside` inside the checkout accepted | fixed | M40 oracle A08 pass; refused exit 2 |
| P3-2 offline host without setuptools: documented result not reproducible | open | results/offline-3.13.15.txt: PIP_NO_INDEX=1 gives REJECTED 5/8 and wheel-smoke exit 2; docs still do not say the build needs network or setuptools |
| P4-1 cut pip tail plus "Nothing was written." | open | probe stderr ends ". Nothing was written." after deleting src/ |
| P4-2 skill-copy temp folder left | not rechecked | |

## New finding
- **P2-1 wheel-smoke deletes `src/` inside an existing `--outside` folder.** `wheel_smoke` builds in `<outside>/src`
  and removes that folder first if it exists. With `--outside ~/work` (a folder the user already has) any
  `~/work/src` is deleted without a prompt. results/probe-outside-existing-folder.txt, Python 3.11.16:
  - W3: offline build failure, rc 2, stderr "... Nothing was written.", and `src/keep.txt` is gone.
  - W3b: build succeeds, rc 0, result pass, 0 findings, and `src/keep.txt` is gone.
  Files outside `src/` (notes.txt, an unrelated wheel) are kept, and the checkout is untouched. P2 because it loses
  user data outside the checkout on a documented option, and the message says nothing was written.

## Proposed fix (not applied)
proposed-fix.patch (host_portability.py only): refuse an `--outside` that exists and is not empty (exit 2 before
anything is created or removed), and drop the rmtree. Positive control on a copy (fix-positive-control.txt): W3b gives
rc 2 and `src/keep.txt` stays; G40 tests OK on 3.9.6, 3.11.16, 3.13.15; M40 oracle 5/5, 8/8, 4/4; portability_oracle
8/8.

## Oracles and results (results/pyversions.txt)
| Python | M40 oracle (scored rows) | G40 tests | portability_oracle | naive | no-op |
|---|---|---|---|---|---|
| 3.9.6 | 5/5 (wheel rows skipped: 3.10+) | OK (2 skipped) | 8/8 | 6/8 | 3/8 |
| 3.11.16 | 8/8 | OK | 8/8 | 5/8 | 2/8 |
| 3.12.14 | 4/4 (no offline setuptools) | OK | 8/8 | 5/8 | 2/8 |
| 3.13.15 | 4/4 (no offline setuptools) | OK | 8/8 | 5/8 | 2/8 |

Full suite on fresh clones (results/full-suite-matrix.txt): 323 tests OK on all four Pythons (2 skipped on 3.9.6);
browser processes 0. Checked: no tracked file sits under a build/, dist/, venv/ or node_modules/ folder that the copy
skips, and the repository has no tracked symlinks, so the private copy is complete today.

## Not done in this pass
- The builder's 9 mutants were not re-scored against the M40 oracle. No browser was launched.
