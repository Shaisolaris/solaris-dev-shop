# G36 day 6 daily integration

Stack on v0.61 `02ba9c5`: G31 r4 `e809a4f` (via r2 `e998d2b`; carries G17 `550f184`, G14 r2 `6f7b23a` and G13 r3 `5666e7b`),
G33 r5 `25c0075`, G35 `34bb98f`, G34 h1 `6ad99da`, G04 r4 `7ed5f70` and G32 r5 `807f1eb`. There are no
outside contributions on this day. G36 r2 merged G04 r3, G31 r3 and G33 r4 onto the r1 stack `7a407bb`;
G36 r3 merges G04 r4, G31 r4, G32 r5, G33 r5 and G34 h1 (the newest heads, validated by M04 r3, M31 r3,
M32 r5 and M33 r4; G34 h1 is a post-acceptance test-control change) without rewriting either, and carries
the M12 P4-1 tool fix from G12 r3 `a245f1f` (a plan text over 300 characters is named as too long).

| Check | What it compares | Result on this stack |
|---|---|---|
| x1 | the G17 result G31 stores for its capacity package, against a fresh G17 run; then a G17 package changed after the result was stored | equal; G31 commits 2027-02-07, and blocks once the package changes |
| x2 | G35's finance tie-out, against G14 run separately on the same finance package | recognized revenue EUR 45.00, USD 495.00 in both; result reconciled |
| x3 | the G13 parser G33 and G35 load, and the G13 status G35 reports for its spend export | one `csv_reconcile.py`; reconciled_with_gaps in both |
| x4 | read-only statements from real runs | G31 read_only, G35 nothing published or spent, all 7 G32 drafts status draft with send not performed |

No cross-goal defect was found on this stack. The checks are not blind: the tests swap in a G31 that keeps
a stale G17 result, a G17 that no longer gives the stored result, a G14 with a different USD figure, a G13
with a different status and a G32 that marks two drafts sent, and each one is reported.

Seven overlaps are resolved in the plan, each with its reason:

- `employees/leadership/cmo/` `SKILL.md`, `capability.contract.json` and `learnings.md`: G33 and G35 add
  lines at different places on the same base; HEAD is the union (the JSON parses).
- `employees/data/data-analyst/SKILL.md`: G33 carries the G13 blob, G31 and G35 carry the G14 blob that
  builds on it; HEAD is the G14 blob.
- `employees/infrastructure/fleet-dispatcher/handoff.py`, `handoff-work-orders.md` and
  `tests/test_g04_capability.py`: G32 carries G04 r1 `314b4db` unchanged; G04 r3 builds on it; HEAD is the
  G04 r3 blob.

G34 reads saved HTML snapshots only. No check here starts a browser or opens a network connection.

```bash
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration.py  # ACCEPTED 13/13
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration_controls/noop.py  # REJECTED 0/13
python3 examples/capabilities/G36/cross_checks.py  # CROSS-CHECKS CLEAN (0 findings)
python3 employees/quality-security/assurance/daily_integration.py check --plan examples/capabilities/G36/plan.json  # VERDICT INTEGRATED
```

The last line runs no tests or cross-checks, so it only binds the stack. `--run all` also runs every
prerequisite's tests and oracle and the cross-checks.
