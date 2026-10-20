# M18 r2: affected recheck of G18 r2 171811c, restacked on G11 h1 (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G18. This is self-validation, not independent review.

- Candidate: G18 r2 `171811c541cdbfc43674bc0622baf5dcb85e2b4d` on review/grok-g18-daily-integration, a
  fast-forward of r1 `fd94c64` (M18: PASS for the build; the stack was NOT_INTEGRATED on the carried G11 x2 finding).

## Verdict
**PASS.** The carried x2 finding is resolved on this stack by G11 h1 94a0de4. No P1, P2, P3 or P4 in G18 r2.
G18 r2's INTEGRATED status depends on root accepting G11 h1, a post-acceptance revision that is not yet accepted.

## Results
- **Probe:** 9/9 on r2 (results/probe-171811c.txt). The plan names G11 94a0de4, the current remote head of
  review/grok-g11-incident-slo. All merges are clean. T0 to T4 behave as specified.
- **Live --run all at r2:** fresh clone, root's three acceptance files, Python 3.9.6. VERDICT INTEGRATED, rc 0.
  G11 is reported as ACCEPTED_OTHER_REVISION (results/live-run-all.txt). r1 was NOT_INTEGRATED on x2.
- **Four Pythons:** G18 tests OK, integration oracle 13/13, naive 1/13, no-op 0/13, cross-checks CLEAN.
- **Full suite on fresh clones:** 252 OK on 3.9.6, 3.11.16, 3.12.14 and 3.13.15. Browser launches: 0.
- **Teeth (results/teeth-g11-reverted.txt):** I reverted incident_slo.py in the r2 tree to the accepted 13ba705.
  The cross-checks then report 2 findings and tests.test_g18_capability fails. r2's new assertion catches a G11
  regression, and the clean result comes from G11 h1, not from a weakened check.
- **Binding (raw/binding-verify.txt):** the remote head equals 171811c, the patch equals a regenerated diff of
  fd94c64..171811c, and the manifest matches.

## Observations
- OBS: the probe's H1 matches a plan commit against every remote head whose branch starts with grok-g11-. That
  now includes the root-decision alternative review/grok-g11-x2-proposed-fix-for-root (9aea147). H1 would also
  pass if the plan named 9aea147. The plan names 94a0de4, checked by hand.
- OBS: G11 h1 changes an accepted G11 decision (refused or untimed trace with a non-application fault:
  insufficient_evidence instead of rollback). Its review belongs to root, with M11 h1 8beb3b6.

## Files
- oracle/: mdaily_probe.py, m42_union.py (not needed: the merge is clean)
- results/: probes on r1 and r2, live run, four-Python table, suite matrix, teeth, remote heads listing
- raw/binding-verify.txt
