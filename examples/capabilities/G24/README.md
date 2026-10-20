# G24 day 4 daily integration

Stack on v0.61 `02ba9c5`: G15 r4 `7e7f361` (newest repair head, root QA batch), G16 r8 `49aba3f`
(candidate), G17 `550f184` (accepted; carries G14 r2 `6f7b23a` and G13 r3 `5666e7b`, both accepted)
and G19 h1 `350d175` (newest head: post-acceptance hardening of the accepted revision `5606672`, the oracle
stop() race and demo boundaries; not accepted yet, so the matrix reports it as another revision). P03 (insta `bee80893`) and P04 (ez-vcard#166, a design discussion with no code
commit: the maintainer chose LaciString in vinnie and asked for no PR code update) are outside
contributions, bound by their acceptance records, reply hashes and validation manifest hashes.

| Check | What it compares | Result on this stack |
|---|---|---|
| x1 | the monthly inflow G17 takes from G14 books against the G14 tool run separately | 109500 both |
| x2 | books G14 does not reconcile cleanly, fed to G17 | kept out of the decision (blocked_evidence) |
| x3 | the CSV parser G15 loads against the integrated G13 file | one copy, loaded by path |

One overlap is resolved in the plan: G15 and G17 both touch `employees/data/data-analyst/SKILL.md`.
G15 carries only the G13 lines, and G17 keeps those and adds the CFO reconcile line, so HEAD takes the
G17 blob (a strict superset). The plan names this in `resolved_overlaps`.

No cross-goal defect was found on this stack; the checks stay as regression protection.

```bash
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration.py  # ACCEPTED 13/13
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration_controls/noop.py  # REJECTED 0/13
python3 examples/capabilities/G24/cross_checks.py  # CROSS-CHECKS CLEAN (0 findings)
python3 employees/quality-security/assurance/daily_integration.py check --plan examples/capabilities/G24/plan.json  # VERDICT NOT_INTEGRATED
```

The last line is `NOT_INTEGRATED` without acceptance files because P03 and P04 then have no binding
(`EXTERNAL_UNVERIFIED`).
