# M24 first pass: G24 day 4 daily integration (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G24. This is self-validation, not independent review.

- Candidate: G24 `cf8351a5fbcc6d6bdccaa7652b802fe524a99c64` on review/grok-g24-daily-integration (unchanged; no
  repair needed).

## Verdict
PASS with one P3. No P1 or P2.

## Method
Same as M06: `oracle/mdaily_probe.py`, fresh-clone `--run all` with root's acceptance files on Python 3.9.6, G24
tests, integration oracle and controls and cross-checks on four Pythons, full suite on fresh clones on four Pythons.

## Results
- **Probe:** 8/9. H1 fails only for G19 (plan 5606672, remote head 350d175). H2, H3 and every tool-teeth row pass.
  G15 r4 7e7f361 (validated by M15 r4 today, PASS) is the current G15 head.
- **Live --run all:** G13, G14, G17, G19 and P03 ACCEPTED, G15 and G16 CANDIDATE; every run rc 0; VERDICT
  INTEGRATED, rc 0; clone clean after.
- **Four Pythons:** G24 tests OK, integration oracle 13/13, naive 1/13, no-op 0/13, cross-checks clean.
- **Full suite:** 235 OK on 3.9.6, 3.11.16, 3.12.14, 3.13.15. Browser 0.
- **Binding:** remote head equals cf8351a; G24.patch equals a regenerated format-patch of cf8351a^..cf8351a;
  manifest matches (raw/binding-verify.txt).

## Findings
- **P3-1: the stack pins G19 at its accepted commit 5606672, not the newer h1 head 350d175.** h1 is post-acceptance
  hardening (an oracle stop() race and demo boundaries, 4 files) and is not accepted. Pinning the accepted
  revision is defensible and the matrix says ACCEPTED truthfully; but the integration does not exercise the h1
  code. Refresh at the next integration or once root rules on h1. No repair made.

## Files
- oracle/: mdaily_probe.py, m42_union.py (not needed: no new merges)
- results/: probe, live run, four-Python table, suite matrix, remote heads listing
- raw/binding-verify.txt
