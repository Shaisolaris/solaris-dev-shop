# G30 day 5 daily integration

Stack on v0.61 `02ba9c5`: G17 `550f184` (accepted; carries G14 r2 `6f7b23a` and G13 r3 `5666e7b`, both
accepted), G21 `822a9c1` (carries G19 `5606672`), G22 `1faee8d` (accepted; carries G19, G13 and G14), G20 r2
`174ef33` (newest repair head, root QA), G23 `0ff2641` (accepted) and G25 `eb9c7c4` (accepted). G24 is not
stacked: its own plan test binds its exact HEAD, and nothing here needs G15 or G16. There are no outside
contributions on this day.

| Check | What it compares | Result on this stack |
|---|---|---|
| x1 | the monthly inflow G17 takes from G22 books reconciled by G14, against G14's own net cash | 33.144028/month both |
| x2 | G22 books with open exceptions (an unapplied 40.00 refund, an out-of-stock order) fed to G14 and G17 | FINDING: exported and decided on as if clean |
| x3 | G23 and G25 report scopes | both state synthetic, offline evidence |

Demonstrated defect (x2, owned by G22): `payment_ledger.py export-g14` exports only applied money rows and
exits 0 while `ingest` has left exceptions open. The 40.00 refund the processor reports as succeeded is
not in the books, G14 reconciles them (net cash 32.69, the same as a stream without those events), and
G17 decides on them. The finding is reported here; this goal does not edit G22's files.

Two overlaps are resolved in the plan: G21 and G22 both touch `employees/engineering/full-stack-developer/`
`SKILL.md` and `learnings.md`. G22 carries the G19 blobs unchanged; G21 builds on G19 and adds one line to
each, so HEAD takes the G21 blobs (strict supersets).

G20 is checked only by its JavaScriptCore oracle and source tests. No check here starts a browser.

```bash
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration.py  # ACCEPTED 13/13
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration_controls/noop.py  # REJECTED 0/13
python3 examples/capabilities/G30/cross_checks.py  # CROSS-CHECKS FINDINGS (1 finding)
python3 employees/quality-security/assurance/daily_integration.py check --plan examples/capabilities/G30/plan.json  # VERDICT INTEGRATED
```

The last line runs no tests or cross-checks, so it only binds the stack. With `--run all` the x2 finding
makes it `NOT_INTEGRATED`.
