# G17: resource and cash decision check (COO, with CFO books and BA scenarios)

Tool: `employees/leadership/coo/resource_decision.py` (stdlib, Python 3.9+, local files only). Rules and
package format: `employees/leadership/coo/resource-cash-decision.md`. All data here is synthetic.

## Demo (from the repository root)

```bash
python3 employees/leadership/coo/resource_decision.py evaluate examples/capabilities/G17/fixtures/studio.json   # exit 0
python3 employees/leadership/coo/resource_decision.py evaluate examples/capabilities/G17/fixtures/studio.json --json   # exit 0
python3 examples/capabilities/G17/decision_oracle.py   # ACCEPTED 12/12
python3 examples/capabilities/G17/decision_oracle.py --tool examples/capabilities/G17/naive_decision.py   # REJECTED 1/12
python3 examples/capabilities/G17/decision_oracle.py --tool examples/capabilities/G17/noop_decision.py   # REJECTED 1/12
```

## The studio fixture, worked by hand (downside case)

Launch (needs integration, after api and web) is due in week 16. Backend downside capacity is
3 people x 36 h x 0.60 focus = 64.8 h/week, 1,036.8 h by week 16. Required backend hours are api 900 +
integration 150 + R1 rework 60 = 1,110 h, so **as-is** is short 73.2 backend hours (binding: capacity) and
finishes in week 18. Its cash: 505,000 opening + 26 weeks x (98,000 - 126,000) x 12/52 = **337,000.00**, above
the 2-month buffer of 252,000.

| option | downside result | binding |
|---|---|---|
| as-is | launch week 18 > 16 | capacity (backend short 73.2 h) |
| contractors | schedule holds; week 17 cash 304,692.31 < buffer 308,000.00 (2 x outflow incl. contractors) | cash |
| hire (irreversible) | later downside start leaves backend 8.4 h short; week 18 cash 315,769.23 < 316,000.00 | capacity, cash |
| descope-reporting | launch met by the shifted deadline (week 18); lowest cash 337,000.00 | none |

Status `feasible_options`, feasible in the downside: `descope-reporting`. The report orders what the numbers
allow; the decision owner decides, and the delivery lead's recorded dissent is carried into the record.

Inflow comes from a G14 reconciliation of `fixtures/books-sept` (108,000.00 USD net cash in a 30-day
September, scaled to 109,500 per average month). Pointing it at `fixtures/books-unreconciled` (a payment with
no invoice) blocks the decision (`blocked_evidence`, exit 1).

## Oracle

`decision_oracle.py` builds packages in a temporary directory and checks: the clean studio figures (d1); an
impossible week-6 deadline rejected with the dependency chain named (d2); narrowing by dropping optional work
that reruns feasible (d3); 12 invalid packages refused with nothing written (d4); unreconciled G14 books
blocking the decision and a currency mismatch refused (d5); realised risk in the downside only, with owner and
mitigation (d6); reversible-first ordering and the irreversible-only status (d7); no invented certainty and
unranged figures named as missing evidence (d8); `--out` then `verify`, a tampered figure detected, and `--out`
onto the package refused (d9); 15 seeded unseen packages against an independent reference scheduler and cash
model (d10); a staffing cap that extra people cannot beat (d11); inputs byte-identical after every run and no
process or network use (s1). `--seed N` changes the unseen packages. The naive control (total hours against
total capacity, base values only) and the no-op control (approves everything) are both rejected.
