# M34 h1: affected recheck of G34 h1 6ad99da, Linux CI fix (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G34 h1. This is self-validation, not independent review.

- Candidate: G34 h1 `6ad99da2532a5bad8ce47e7779908ad067c29953` on review/grok-g34-content-diagnostics, a
  fast-forward of accepted G34 `de76fae`. One file is changed: the naive negative control. The tool is unchanged.

## Verdict
**PASS.** No P1, P2 or P3. The defect it repairs was CI-blocking: the full suite failed on every Linux job of
the supported CI. M34's earlier P4 findings and observations are unchanged (the tool is identical).

## Results
- **Defect reproduced:** the local replay of .github/workflows/ci.yml on G42 r3 9d844d2 failed one test on
  Linux 3.10, 3.12 and 3.13, and passed every step on macOS 3.12 (results/ci-replay-*.txt). Cause confirmed:
  the naive control's `f.read((1 << 40) + 1)` raises MemoryError on Linux.
- **Fixed on Linux:** a fresh clone of 6ad99da on Linux x86_64 gives, on 3.10.22, 3.12.15 and 3.13.5, G34 tests
  OK, oracle 14/14, naive 9/14 and no-op 3/14 (results/linux-recheck-6ad99da.txt).
- **Right reasons:** the naive control now fails exactly o2, o3, o4, o8 and o9:
  - o2 to o4: redirects ignored;
  - o8: the outside link is followed, not skipped;
  - o9: no size cap.
  That is the set the test asserts, so the control is rejected for its documented shortcuts and not for a crash.
- **Before and after on Linux:** tests.test_g34_capability FAILED on de76fae and OK with the h1 diff
  (results/linux-before-after.txt).
- **macOS, four Pythons:** the same scores, and the full suite has 94 OK on all four (results/mac-four-python.txt,
  full-suite-matrix.txt).
- **Binding (raw/binding-verify.txt):** the remote head equals 6ad99da, the patch equals a regenerated diff of
  de76fae..6ad99da, and the manifest matches.

## Observations
- OBS: the control now walks everything reachable (symlinks followed) to size its cap. A link to a very large
  folder makes the negative control slow (the builder's ad-hoc link to /tmp timed out at 120 s). The oracle's
  fixtures are small. This is disclosed in the handback and never affects the tool.
- OBS: CI coverage is Linux and macOS only. The Windows job was not replayed (no Windows host).

## Files
- results/: CI replays (Linux and macOS), Linux recheck, Linux before and after, macOS four-Python, suite matrix
- raw/binding-verify.txt
