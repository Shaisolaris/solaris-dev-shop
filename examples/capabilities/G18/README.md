# G18 day 3 daily integration

Stack: G11 r3 `13ba705` (carries G10 r6 `f79be61` and G03 r3 `d4d98f2`) merged with G14 r2 `6f7b23a`
(carries G13 r3 `5666e7b`), on v0.61 `02ba9c5`. Every one of those commits is accepted by root at
exactly that revision. P03 (mitsuhiko/insta#949 follow-up, `bee80893`) is an outside contribution:
it has no commit here and is bound by its acceptance record, reply hash and validation manifest hash.

`plan.json` names each candidate, its tests and its own oracle. `cross_checks.py` holds the checks
that only make sense once the candidates sit together:

| Check | What it compares | Result on this stack |
|---|---|---|
| x1 | each of the 12 G10 fixtures, re-timed into the G11 regression impact, against the G11 decision netdiag's own verdict implies | 12 agree |
| x2 | a supplied G10 trace that netdiag refuses, or that has no capture time | finding: G11 recommends rollback (exit 0) and the decision trace never mentions it |
| x3 | G13 and G14 on a row loaded exactly at as_of and on "1,250.50", "+10", "1e1", "1,0" | agree; sub-cent is a documented difference |

The x2 finding belongs to G11 and is reported, not fixed here. Until G11 changes, the live matrix is
`NOT_INTEGRATED` for that reason only.

```bash
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration.py  # ACCEPTED 13/13
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration_controls/noop.py  # REJECTED 0/13
python3 examples/capabilities/G18/cross_checks.py  # CROSS-CHECKS FINDINGS (2 findings)
python3 employees/quality-security/assurance/daily_integration.py check --plan examples/capabilities/G18/plan.json  # VERDICT NOT_INTEGRATED
```

The last line is `NOT_INTEGRATED` without acceptance files because P03 then has no binding at all
(`EXTERNAL_UNVERIFIED`). With root's three acceptance files, the P03 readback and the R03 manifest,
`--run tests` runs 5 test modules, 5 oracles and the cross-checks; only x2 remains.
