# M06 first pass: G06 day 1 daily integration, with r2 repair (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G06. This is self-validation, not independent review.

- Candidate: G06 r1 `c5baac717c7e3655f6eea06aa5f92bf581f3f45f` on review/grok-g06-daily-integration.
- Repair: G06 r2 `7d5dae5f969c147987e84b552b3289b481012d9a`, a fast-forward (two clean merges and a plan/README
  commit), for the P2 below.

## Verdict
PASS after repair. r1 had one P2. r2 fixes it. No other finding.

## Method
- `oracle/mdaily_probe.py`, written from daily-integration.md, plan.json and the README, run on r1 and r2:
  - H1 every plan commit equals its goal's current remote head (listing taken at the start of the pass,
    results/remote-heads-at-start.txt); H2 every plan commit is in HEAD; H3 every merge is a clean merge.
  - Tool teeth on a clone of HEAD: T0 clean gives INTEGRATED; T1 a plan commit that is not the candidate, T2 a
    prerequisite file reverted, T3 a commit outside the writable globs, T4 an uncommitted change each give
    NOT_INTEGRATED with the right finding.
  - X1 the cross-checks run on a clean clone.
- `oracle/m42_union.py` (from M42) on the two new merges.
- Fresh-clone `--run all` with root's three acceptance files (Python 3.9.6 for PyYAML); G06 tests, the
  integration oracle with its naive and no-op controls and the cross-checks on four Pythons; full suite on fresh
  clones on four Pythons.

## Results
- **Probe:** 8/9 on r1 (H1 fails: G01 a069a79 vs aa0b083, G02 8fdae9c vs 90a5ec9). 9/9 on r2.
- **Union:** both new merges change no file on both sides. UNION OK.
- **Live --run all at r2:** G01 ACCEPTED_OTHER_REVISION, G02 CANDIDATE, G03, P01, P02 ACCEPTED; every test,
  oracle, cross-check and gate rc 0; VERDICT INTEGRATED, rc 0; clone clean after.
- **Four Pythons at r2:** G06 tests OK, integration oracle 13/13, naive 1/13, no-op 0/13, cross-checks clean.
- **Full suite:** 214 OK on 3.9.6, 3.11.16, 3.12.14, 3.13.15. Browser 0.
- **Binding:** remote head equals 7d5dae5; handback patch equals a regenerated diff; manifest matches
  (raw/binding-verify.txt).

## Findings
- **P2-1 (fixed in r2): the day 1 stack carried G02 r3, which has a known P2.** M02 r3 found that G02 r3 read
  "UNRESOLVED" followed by words, and accented text, as an answer; G02 r4 90a5ec9 fixes it. r1's plan and merges
  named r3, so the integration did not contain the repair. G01 had also moved (h1 aa0b083, docs only). The tool
  itself cannot see this: it checks the plan against HEAD, not against the goals' current heads, so r1 still
  reports INTEGRATED. r2 merges both heads and names them in plan.json.
- **OBS:** G01 h1 changed ASSURANCE.md, so G06's copy of the shared assurance files no longer equals G18's.
  Nothing requires them to match.

## Files
- oracle/: mdaily_probe.py, m42_union.py
- results/: probe on r1 and r2, union check, live run, four-Python table, suite matrix, remote heads listing
- raw/binding-verify.txt
