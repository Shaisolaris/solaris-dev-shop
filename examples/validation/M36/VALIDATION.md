# M36 first pass: G36 day 6 daily integration, with r2 repair (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G36. This is self-validation, not independent review.

- Candidate: G36 r1 `7a407bb914deb6df5ddac83fb24eea8d2f1333fd` on review/grok-g36-daily-integration.
- Repair: G36 r2 `92ca6c3272b9dcbfd854fc5cfdf9359ddefa1ab4`, a fast-forward (three clean merges and a plan/README
  commit), for the P2 below.

## Verdict
PASS after repair. r1 had one P2. r2 fixes it. No other finding.

## Method
Same as M06: `oracle/mdaily_probe.py` on r1 and r2, `oracle/m42_union.py` on the new merges, fresh-clone
`--run all` with root's acceptance files on Python 3.9.6, G36 tests, integration oracle and controls and
cross-checks on four Pythons, full suite on fresh clones on four Pythons.

## Results
- **Probe:** 8/9 on r1 (H1 fails: G04 155fc33 vs e9fa278, G31 e998d2b vs fcf492a, G33 327e631 vs a4ae555). 9/9 on r2.
- **Union:** the three new merges change no file on both sides. UNION OK.
- **Live --run all at r2:** VERDICT INTEGRATED, rc 0, every run rc 0, clone clean after.
- **Four Pythons at r2:** G36 tests OK, integration oracle 13/13, naive 1/13, no-op 0/13, cross-checks clean.
- **Full suite:** 320 OK on 3.9.6, 3.11.16, 3.12.14, 3.13.15. Browser 0.
- **Binding:** remote head equals 92ca6c3; patch equals a regenerated diff; manifest matches (raw/binding-verify.txt).

## Findings
- **P2-1 (fixed in r2): the day 6 stack carried three candidates with known P2s.** G04 r2 (an owner change on a
  delivered revision delivered it twice, M04 r2), G31 r2 (two contradictory commitments were ready, M31 r2) and
  G33 r3 ("1,5", "+18", "-5" fell back to substring matching, M33 r3). Each has a repair head; r2 merges all three
  and names them in plan.json. The tool cannot see this, since it checks the plan against HEAD, not current heads.
- The cross-checks x1 to x4 do not exercise G04 owner changes, so unlike G12 none needed changing.

## Files
- oracle/: mdaily_probe.py, m42_union.py
- results/: probes on r1 and r2, union check, live run, four-Python table, suite matrix, remote heads listing
- raw/binding-verify.txt
