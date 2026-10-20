# M40 r4 validation of G40 r4 eabf69a (Grok self-validation, not independent review)

Verdict: **PASS with one P4 still open (P4-2) and P3-2 closed by documentation only.** wheel-smoke no longer deletes or
writes into a folder the user already has: an existing, non-empty `--outside` (or a file, or a dangling link) is
refused with exit 2 and every file is kept. A failed build now names the work folder instead of saying nothing was
written. This is Grok checking a Grok build, built in the same batch by the same agent. It is not independent review
and accepts nothing.

## Own-build disclosure
G40 r4 was built by me from my own M40 r3 proposed patch, with two additions (the failed-build message and the
`report --outside` early check). I wrote a new probe (oracle/m40r4_probe.py) for this pass that tries folder shapes the
builder tests do not: a hidden-file-only folder, symlinks, a nested new path, a rerun into a filled folder.

## Binding (raw/binding-verify.txt)
- Candidate eabf69ac9cf4f539bc39482b75681bf75e6e97e5 on review/grok-g40-fresh-install (remote re-checked), a
  fast-forward of one commit from r3 bb44478.
- G40-r4.patch equals `git format-patch --stdout bb44478..eabf69a`; MANIFEST.sha256 4/4 match; manifest set equals the
  diff set (host_portability.py, host-portability.md, G40 README, tests/test_g40_capability.py).
- Evaluated in a detached clone; `git status --porcelain --ignored` empty after every run.

## M40 r3 findings, status at r4
| M40 r3 item | Status | Evidence |
|---|---|---|
| P2-1 wheel-smoke deletes `src/` in an existing `--outside` | fixed | probe V1, V2, V3, V6, V8 (all files kept, exit 2) on 3.11.16, 3.12.14, 3.13.15 |
| P4-1 "Nothing was written" after a failed build | fixed | probe V10; results/offline-3.13.15.txt names the work folder; refusals before anything is created still say "Nothing was written" |
| P3-2 offline host without setuptools | documented, not changed | host-portability.md now says the build needs setuptools>=61 from the index or already installed; offline 3.13.15 still exits 2 (results/offline-3.13.15.txt) |
| P4-2 skill-copy temp folder left | open, not in r4 scope | |

## Probe (oracle/m40r4_probe.py, results/probe-*.json)
On a private copy of the candidate checkout:
- V1 folder with src/keep.txt, an old wheel and notes.txt: exit 2, every file kept, nothing added. V2 the same through
  `report --outside`. V3 a folder holding only `.keep` counts as not empty. V4 a file: exit 2, no traceback, kept.
  V5 dangling symlink: exit 2, target not created. V6 symlink to the non-empty folder: exit 2, kept.
- V7 a new nested path: created, exit 0, result pass. V8 rerun into the folder V7 filled: exit 2, its files kept.
  V9 an existing empty folder: exit 0 pass.
- V10 a copy whose build backend cannot be imported: exit 2, stderr names the work folder and does not say "Nothing was
  written", and nothing else is created next to it. V11 `--outside` under REPO still refused. V12 the checkout copy is
  unchanged after every run.
- 12/12 on 3.11.16, 3.12.14 and 3.13.15. On 3.9.6 wheel-smoke needs 3.10+: V0 (refused, nothing created) and V12, 2/2.

## Oracles and results (results/pyversions.txt)
| Python | m40r4 probe | M40 oracle (scored rows) | G40 tests |
|---|---|---|---|
| 3.9.6 | 2/2 | 5/5 (wheel rows skipped: 3.10+) | 18 OK (5 skipped) |
| 3.11.16 | 12/12 | 8/8 | 18 OK |
| 3.12.14 | 12/12 | 4/4 (no offline setuptools) | 18 OK |
| 3.13.15 | 12/12 | 4/4 (no offline setuptools) | 18 OK |

Builder portability_oracle ACCEPTED 8/8 on all four, naive and no-op still rejected (G40 r4 handback, raw/oracle-matrix).
Full suite on fresh clones (results/full-suite-matrix.txt): 327 tests OK on all four Pythons (5 skipped on 3.9.6);
browser processes 0.

## Residuals
- P4-2 (skill-copy temp folder) unchanged.
- The non-empty check and the mkdir are two steps; a folder filled by another process between them is not guarded.
  Not a realistic case for a local smoke run; noted only.

Browser launches for this pass: 0.
