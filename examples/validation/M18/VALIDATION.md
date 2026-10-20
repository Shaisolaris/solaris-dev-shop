# M18 first pass: G18 day 3 daily integration (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G18. This is self-validation, not independent review.

- Candidate: G18 `fd94c645d88385d8c788f59c6a3c7e5ed3929542` on review/grok-g18-daily-integration (unchanged; no
  repair made in this pass).

## Verdict
PASS for the G18 build: its matrix is current and correct, and it reports the stack truthfully as NOT_INTEGRATED.
The stack itself is not integrated because of one cross-goal finding against G11 (accepted), which G18 found and
escalated. That finding is carried here for root; it is not a G18 defect and was not repaired (see below).

## Method
Same as M06: `oracle/mdaily_probe.py` (H1 plan heads current, H2 plan commits in HEAD, H3 clean merges, T0 to T4
tool teeth on a clone, X1 cross-checks), fresh-clone `--run all` with root's acceptance files on Python 3.9.6, G18
tests, integration oracle and controls and cross-checks on four Pythons, and the full suite on fresh clones on
four Pythons.

## Results
- **Probe:** 9/9. All five plan commits (G03, G10, G11, G13, G14) are the current remote heads, all in HEAD, both
  merges clean, every tool-teeth row behaves as documented.
- **Live --run all:** every prerequisite test and oracle and every CI gate rc 0; the only finding is
  `RUN_FAILED G18: cross_check ... rc=1`; VERDICT NOT_INTEGRATED, rc 1, clone clean after. This matches the G18
  handback exactly.
- **Four Pythons:** G18 tests OK, integration oracle 13/13, naive 1/13, no-op 0/13; cross-checks report the same
  2 x2 findings on every interpreter.
- **Full suite:** 251 OK on 3.9.6, 3.11.16, 3.12.14, 3.13.15. Browser 0.
- **Binding:** remote head equals fd94c64; G18.patch equals a regenerated format-patch of fd94c64^..fd94c64;
  manifest matches (raw/binding-verify.txt).

## Findings
- **Carried, for root: cross-check x2 against G11 (P2 proposed by the G18 builder).** When G10 hands G11 an
  unusable diagnosis (refused capture time, or no capture time), G11 still recommends a rollback with exit 0 and
  its decision trace never mentions the supplied G10 trace. Reproduced on four Pythons in this pass through the
  G18 cross-checks; I did not write a separate G11 probe. G11 is accepted at 13ba705 and outside G18's writable
  scope, and the G18 handback asks root whether this is a blocker or an accepted residual. A repair would change
  accepted G11 behaviour (for example, treat an unusable diagnosis as insufficient evidence), so it is left for
  that decision rather than made here.
- No P1, P2 or P3 in G18 itself.

## Files
- oracle/: mdaily_probe.py, m42_union.py (not needed: no new merges)
- results/: probe, live run, four-Python table, suite matrix, remote heads listing
- raw/binding-verify.txt
