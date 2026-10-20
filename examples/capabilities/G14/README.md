# G14 recognized revenue versus cash: oracle and fixtures

Books for `employees/leadership/cfo/cash_revenue_reconcile.py`, period September 2026 (UTC), as_of
2026-10-03. These replace the CFO contract's advertised `fixtures/evaluation/leadership-operations/cfo/`
paths, which do not exist in the repository.

`fixtures/clean`: two USD invoices delivered and paid in full (one amount written "1,250.50"), bank matches.
Exit 0: billed = revenue = cash = 2250.50, closing AR 0.00, no exceptions.

`fixtures/september` (hand-worked; exit 1 because exceptions are listed):

| | USD | EUR | GBP |
|---|---|---|---|
| billed | 2550.00 | 400.00 | 0.00 (invoice void) |
| credit notes | 150.00 (C6 after delivery, C7 before) | 0.00 | 0.00 |
| recognized revenue | 2000.00 | 400.00 | 0.00 |
| cash received / refunds | 2195.00 / 0.00 | 450.00 / 50.00 | 90.00 / 0.00 |
| AR opening -> closing | 300.00 -> 700.00 | 0.00 -> 0.00 | 0.00 |
| closing deferred | 400.00 (I4 250 undelivered, I7 200 - 50) | 0.00 | 0.00 |
| closing unapplied cash | 195.00 (P8 unknown invoice, P9 EUR invoice) | 0.00 | 90.00 (void invoice) |

Exceptions: P10 loaded after as_of (late), P12 two versions (excluded), I4 no delivery evidence. P1 is
delivered twice and counted once. Bridge USD: 2000.00 - 2195.00 = +400.00 AR - 400.00 deferred - 195.00 unapplied.

```bash
T=employees/leadership/cfo/cash_revenue_reconcile.py
python3 $T reconcile examples/capabilities/G14/fixtures/clean/package.json             # exit 0
python3 $T reconcile examples/capabilities/G14/fixtures/september/package.json         # exit 1
python3 $T reconcile examples/capabilities/G14/fixtures/september/package.json --json  # exit 1
python3 $T reconcile examples/capabilities/G14/README.md                               # exit 2
```

`cash_oracle.py` checks literal values for these books and, for seeded random books, an independent
double-entry journal; exit 0 alone proves nothing:

```bash
PY=python3.12
$PY examples/capabilities/G14/cash_oracle.py -- $PY $T                                  # ACCEPTED 13/13
$PY examples/capabilities/G14/cash_oracle.py -- $PY examples/capabilities/G14/naive_stub.py  # REJECTED
$PY examples/capabilities/G14/cash_oracle.py -- $PY examples/capabilities/G14/noop_stub.py   # REJECTED
```

Checks: o1 clean control; o2 hand-worked September values; o3 currencies never combined (also 60
invoices of 100.00 in two currencies against the journal); o4 credit note before and after delivery,
overpayment then partial refund leaves a customer credit; o5 late row named, a later cutoff takes it in
and the bank control shows the difference; o6 missing amount, negative and sub-cent amounts, a credit note dated before its invoice, missing loaded_at, missing delivery; o7
every row re-delivered and shuffled gives the same balances, conflicting versions named; o8 bank control
per currency, and a control difference alone gives exit 1; o9 three seeded 250-invoice books equal to the journal; o10 eight invalid packages exit 2
and keep the previous report, then recovery; o11 40 000 invoices equal to the journal; o12 no network
use and the package folder byte-identical; o13 refunds above the payments and credit notes above the
invoice (the M14 K14 book) give exit 1 with over_refunded and over_credited named, equal amounts are not challenged.
