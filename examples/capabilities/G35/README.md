# G35: campaign accounting without live spend

Tool: `employees/marketing/paid-ads-manager/campaign_ledger.py` (rules: `campaign-accounting.md` next to it).
All data here is synthetic: no ad account, real person, publish or paid impression is involved. Spend and the
order book go through the data engineer's G13 `csv_reconcile.py`; the finance tie-out uses the CFO's G14
`cash_revenue_reconcile.py`.

## Run
```
python3 employees/marketing/paid-ads-manager/campaign_ledger.py reconcile examples/capabilities/G35/fixtures/clean/campaign.json   # exit 0
python3 employees/marketing/paid-ads-manager/campaign_ledger.py reconcile examples/capabilities/G35/fixtures/september/campaign.json   # exit 1
python3 employees/marketing/paid-ads-manager/campaign_ledger.py reconcile examples/capabilities/G35/fixtures/september/campaign.json --out $STATE/brief   # exit 1
python3 employees/marketing/paid-ads-manager/campaign_ledger.py reconcile examples/capabilities/G35/README.md   # exit 2
python3 examples/capabilities/G35/campaign_oracle.py   # ACCEPTED 12/12
python3 examples/capabilities/G35/campaign_oracle.py -- python3 examples/capabilities/G35/naive_ledger.py   # REJECTED 1/12
python3 examples/capabilities/G35/campaign_oracle.py -- python3 examples/capabilities/G35/noop_ledger.py   # REJECTED 0/12
```

## Clean control
One USD search campaign, 3 days of 10.00, two clicked orders (50.00, 25.00): spend 30.00, 2 conversions,
revenue 75.00, CPA 15.00, ROAS 2.5000, finance difference 0.00, creative K1 ready for human review. The naive
control agrees here, as it should on clean data.

## September, worked by hand (as of 2026-10-02T00:00Z)
Spend export (BOM, CRLF, `Campaign`/`Day`/`Cost` headers, lower-case currency):

| Rows | Effect |
|---|---|
| C-search 09-01 15.00 twice | exact copy, 15.00 |
| C-search 09-02 15.00 then 18.00 (newer `updated_at`) | restated, 18.00 |
| C-search 09-03 15.00, 09-05 25.00 | 09-05 is over the 20.00 daily cap |
| C-search 09-29 12.00 loaded 10-03 | late (G13 gap), not counted |
| C-social 09-08 5.00, 09-12 10.00, 09-13 10.00 | 09-08 is before the flight (starts 09-10) |
| C-eu 09-04 8.00 EUR | |
| C-old 09-06 4.00 | unknown campaign, unassigned |

USD spend 102.00 = C-search 73.00 + C-social 25.00 + unassigned 4.00; EUR 8.00.

Orders (book, USD 555.00, EUR 45.00) and their conversions:

| Order | Value | Events | Touch that wins | Result |
|---|---|---|---|---|
| O1 | 120.00 | pixel E1 (sent twice) + server E2 | u1 click C-search 09-02 09:00 | C-search, counted once |
| O2 | 80.00 | E3 pixel says 90.00 | u2 C-search click 09-11, then C-social click 09-12 08:00 | C-social (latest click, 12 h < 1 day); value 80.00 from the book |
| O3 | 60.00 | E4 at 09-08 10:00:00 | u3 click C-search 09-01 10:00 (exactly 7 days) | C-search; the u3 click at 10:00:01 is after the conversion |
| O4 | 40.00 | E5 at 09-08 10:00:01 | u4 click 7 days and 1 second earlier | no_eligible_touch |
| O5 | 30.00 | E6 | u5 view C-social 12 h earlier (view window 1 day) | C-social, view conversion |
| O6 | 200.00 | E10 loaded 10-03 (late) | | no_conversion_event |
| O7 | 45.00 EUR | E7 | u6 click C-eu | C-eu |
| O8 | test order | E8 | | not in the book: conversion_without_order |
| O9 | 25.00 | E9 | u7 clicks on C-search and C-social at the same instant | ambiguous_touch |

| Campaign | Spend | Conversions | Revenue | CPA | ROAS |
|---|---|---|---|---|---|
| C-search | 73.00 | 2 | 180.00 | 36.50 | 2.4658 |
| C-social | 25.00 | 2 (1 click, 1 view) | 110.00 | 12.50 | 4.4000 |
| C-eu | 8.00 EUR | 1 | 45.00 EUR | 8.00 | 5.6250 |

USD identity: 555.00 = attributed 290.00 + unattributed 265.00 (40.00 + 25.00 + 200.00). Finance (G14): a
60.00 credit note on O3 gives recognized revenue 495.00, so `order_value_differs_from_recognized_revenue`
names 60.00. Touches also hold one exact copy, one truncated line (rejected) and a click for unknown C-old.

Creatives: K1 (ROAS 2.47, 2 orders) and K2 (4.4x return, paid partnership disclosed) are true but
`held_unverified` because the report has findings; K3 "Guaranteed 10x returns" (prohibited, unsupported
number), K4 (has `publish_at`), K5 (CPA 30.00 against 36.50) and K6 (social, connection status unknown) are
blocked. Exit 1 with 10 named findings.

## Oracle checks
o1 clean control; o2 the values above; o3 every event three times and shuffled, spend rows twice and
shuffled; o4 window edges; o5 seeded books of 1500 orders whose campaign is fixed before the touches are drawn
(restatements, copies, pixel+server pairs, stale clicks, ties, clicks after the conversion, a view next to a
click); o6 a cap met exactly versus one cent over; o7 creative rules; o8 nine invalid packages and an `--out`
inside the package exit 2 and keep the previous report, then recovery; o9 four parallel runs with the network
blocked, identical reports and unchanged package files; o10 20 000 orders; o11 a reused event id with another
body and an order claimed by two users; o12 a G14 credit note and refund named against order value.
