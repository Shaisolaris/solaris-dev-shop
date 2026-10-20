# G12 day 2 daily integration

Stack on v0.61 `02ba9c5`: G09 `edfa64d` (accepted; carries G08 r2 `ddebe98`, accepted, and G03 r3 `d4d98f2`),
merged with G07 `0d6a78d` (candidate), G04 r3 `e9fa278` and G05 r3 `04b3cf2` (newest repair heads, the M04 r2
and M05 r2 P2 repairs; candidates). G12 r2 merges G05 r3 and G04 r3 onto the r1 stack `2718b1f` without
rewriting it. G04, G05 and G07 all carry G04 `314b4db` and G02 `bbe682b`; G02 itself is not a G12 prerequisite.

| Check | What it composes | Result on this stack |
|---|---|---|
| x1 | G07 ownership transfer (epoch 1 to 2) with a G04 r2 fleet-bound order | stale owner refused (exit 2), new owner runs, brief names the new owner |
| x2 | a G05 r3 receipt bound to the G04 brief digest | current on a plain re-run, stale after the owner change |
| x3 | a G05 r3 receipt bound to the reviewed G08 artifact (revision = its sha256) | current for the live r2, stale after a G08 rollback to r1 |

Six files are changed by more than one prerequisite. Four have only one real change (G05 carries G04
`314b4db` unchanged). In `handoff.py`, G04 and G07 edit disjoint lines and git merged them cleanly. In
`handoff-work-orders.md` both add a reason to the exit 2 line; r2 keeps both. `plan.json` names all six in
`resolved_overlaps`, with reasons.

No cross-goal defect was found on this stack; the checks stay as regression protection.

```bash
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration.py  # ACCEPTED 13/13
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration_controls/noop.py  # REJECTED 0/13
python3 examples/capabilities/G12/cross_checks.py  # CROSS-CHECKS CLEAN (0 findings)
python3 employees/quality-security/assurance/daily_integration.py check --plan examples/capabilities/G12/plan.json  # VERDICT INTEGRATED
```

Without `--run all` and acceptance files the last line checks bindings, drift, overlap and scope only: it
reports `INTEGRATED` with every prerequisite `UNKNOWN` and nothing run. The verdict that counts is
`--run all` with root's acceptance files (see the handback).
