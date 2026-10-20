# M30 first pass: G30 day 5 daily integration (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G30. This is self-validation, not independent review.

- Candidate: G30 r2 `135d95f943467f2bc69473bc30c5dfa6e6fd58e3` on review/grok-g30-daily-integration (unchanged; no
  repair needed).

## Verdict
PASS with one P3. No P1 or P2.

## Method
Same as M06: `oracle/mdaily_probe.py`, fresh-clone `--run all` with root's acceptance files on Python 3.9.6, G30
tests, integration oracle and controls and cross-checks on four Pythons, full suite on fresh clones on four Pythons.

## Results
- **Probe:** 8/9. H1 fails only for G22 (plan 8bc3553 = G22 h1, remote head 29cd7fc = G22 h2). H2, H3 and every
  tool-teeth row pass. G20 r3 0d4db69 (validated by M20 r2 today, PASS) is the current G20 head.
- **Live --run all:** G13, G14, G17, G21, G23 and G25 ACCEPTED, G20 CANDIDATE, G22 ACCEPTED_OTHER_REVISION (h1 is
  newer than the accepted G22 commit); every run rc 0; VERDICT INTEGRATED, rc 0; clone clean after.
- **Four Pythons:** G30 tests OK, integration oracle 13/13, naive 1/13, no-op 0/13, cross-checks clean.
- **Full suite:** 282 OK (1 skipped: the opt-in Chrome render test, not enabled) on 3.9.6, 3.11.16, 3.12.14,
  3.13.15. Browser 0.
- **Binding:** remote head equals 135d95f; G30-r2.patch equals a regenerated format-patch of e1ec14d..135d95f;
  manifest matches (raw/binding-verify.txt).

## Findings
- **P3-1: the stack pins G22 at h1 8bc3553, not the newer h2 29cd7fc.** h2 adds the audited resolve path that
  closes the M22 h1 P3 (recorded exceptions can now be resolved or re-delivered, so later periods export again).
  The defect h2 fixes was P3, and h1 is internally consistent, so the stale pin is P3 and no repair was made.
  Restack on G22 h2 at the next integration, after M22 h2 (PASS today) is reviewed.

## Files
- oracle/: mdaily_probe.py, m42_union.py (not needed: no new merges)
- results/: probe, live run, four-Python table, suite matrix, remote heads listing
- raw/binding-verify.txt
