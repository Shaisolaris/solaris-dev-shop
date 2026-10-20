# M40 r5: Grok self-validation of G40 r5 99b49c6 (M40 P3-2 offline reproduction)

Verdict: **PASS. M40 P3-2 is closed by a behaviour change, not only documentation. P4-2 (skill-copy temp folder) stays open.**
This is Grok checking a Grok build, built in the same run by the same agent. It is not independent review and accepts nothing.

Candidate: G40 r5 `99b49c63b56eb17ac8223fd264ff87b2dd99a545` on `review/grok-g40-fresh-install`, a plain fast-forward over r4 `eabf69a`.

## What changed
- `wheel-smoke` and `report` take `--wheelhouse DIR`. The build then runs `pip wheel ... --no-index --find-links DIR`, so the
  documented outcome reproduces with no network. The JSON names the source in `build_backend_from`.
- A `--wheelhouse` that is not a folder, or holds no `setuptools>=61` wheel, is refused with exit 2 before anything is written.
- Offline without a wheelhouse, exit 2 starts `build_backend_unavailable`, names the remedy and the work folder, and keeps pip's error.
- The builder oracle passes `--wheelhouse` (or `$G40_WHEELHOUSE`) through to its wheel rows and the report row.
- `host-portability.md`, `docs/install.md` and the G40 README state that the build needs the package index or a wheelhouse.

## Own probe (oracle/m40r5_probe.py), every case offline (PIP_NO_INDEX=1, PIP_* config removed)
Wheelhouse used: a copy of the setuptools 79.0.1 wheel bundled in Python 3.11's ensurepip, so no network at all.
- C1 offline build with the wheelhouse: exit 0, pass, one wheel, no employees/, control-plane policy packaged.
- C2 offline without one: exit 2, `build_backend_unavailable`, `--wheelhouse` and the work folder named.
- C3 a wheelhouse with only setuptools 60: exit 2, `--outside` never created, "Nothing was written".
- C4 a non-wheel file named setuptools: refused. C5 a wheelhouse that is a file: refused, file kept.
- C6 `report` with a bad wheelhouse refuses before skill-copy runs (no new g40-skill-* folder in TMPDIR).
- C7 a corrupt setuptools wheel: exit 2, no traceback from the tool, backend named.
- C8 the checkout is unchanged.

| Python | r5 probe | probe at r4 eabf69a | M40 r4 probe on r5 | M40 oracle on r5 |
|---|---|---|---|---|
| 3.9.6 | 5/5 (wheel rows n/a) | 4/5 | 2/2 | 5/5 scored |
| 3.11.16 | 8/8 | 5/8 | 12/12 | 8/8 scored |
| 3.12.14 | 8/8 | 5/8 | 12/12 | 4/4 scored |
| 3.13.15 | 8/8 | 5/8 | 12/12 | 4/4 scored |

Teeth: at r4 C1, C2 and C3 fail (C3 on 3.9.6 too). C4 to C7 pass at r4 only because argparse rejects the unknown flag with exit 2,
so they guard against regressions in r5 rather than prove the defect. Disclosed, not counted as teeth.

## Builder evidence rechecked
Builder oracle on 3.11.16, 3.12.14 and 3.13.15: offline with `--wheelhouse` ACCEPTED 8/8, offline without it REJECTED 5/8 (expected,
now documented and named), online ACCEPTED 8/8, naive REJECTED 4/8, no-op REJECTED 2/8. The four new G40 tests fail at eabf69a
(4 failures on 3.13.15). Full suite on fresh clones of 99b49c6: 332 tests OK on 3.9.6 (7 skipped), 3.11.16, 3.12.14 and 3.13.15,
with G40_WHEELHOUSE set so the offline build test runs. Browser processes 0.

## Residuals
- P4-2 skill-copy without `--dest` leaves a g40-skill-* folder in TMPDIR each run (unchanged, not in r5 scope).
- OBS: without G40_WHEELHOUSE, `test_offline_build_with_a_local_wheelhouse_passes` skips on 3.12 and 3.13 (their ensurepip has no setuptools).
- OBS: backend detection reads pip's "build dependencies" text; a pip that rewords it falls back to the plain "pip wheel failed" message (still exit 2).
