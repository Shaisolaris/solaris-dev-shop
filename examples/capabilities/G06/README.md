# G06 day 1 daily integration

Stack on v0.61 `02ba9c5`: G03 r3 `d4d98f2` (accepted), G01 h1 `aa0b083` (G01 was accepted at `a069a79`;
h1 is a docs-only hardening on top, not accepted at this revision) and G02 r4 `90a5ec9` (the newest
repair head, M02 r3 P2 repair; root accepted no G02 revision). r2 of this integration merges those two
newer heads onto the r1 stack `c5baac7` without rewriting it. P01 (Tinche/aiofiles#245, code head `2577f3e`) and P02
(lucc/khard#360, a design and LLM-use response with no code commit) are outside contributions:
nothing of theirs is in this repository, so they are bound by their acceptance records, the reply
body hashes and the validation manifest hashes, never by a missing code branch.

`plan.json` names each candidate, its tests and its own oracle. `cross_checks.py`:

| Check | What it compares | Result on this stack |
|---|---|---|
| x1 | G02 activation (twice) over a project whose Development/ holds an owner WAL database and a G03 snapshot | every owner byte unchanged; G03 verify, health and recover dry run exit 0 |
| x2 | G03 restore inside the activated project, then G02 resume | 200 rows back, resume exit 0, G02 notes unchanged |
| x3 | G01's changed assurance engine auditing the skills G02 and G03 changed | 61 scanned, 0 gaps |

No cross-goal defect was found on this stack; the checks stay as regression protection.

```bash
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration.py  # ACCEPTED 13/13
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration_controls/noop.py  # REJECTED 0/13
python3 examples/capabilities/G06/cross_checks.py  # CROSS-CHECKS CLEAN (0 findings)
python3 employees/quality-security/assurance/daily_integration.py check --plan examples/capabilities/G06/plan.json  # VERDICT NOT_INTEGRATED
```

The last line is `NOT_INTEGRATED` without acceptance files because P01 and P02 then have no binding
(`EXTERNAL_UNVERIFIED`). With root's three acceptance files, both reply readbacks and the R01 and
R02 manifests, `--run tests` runs every candidate test module and oracle and the cross-checks.
