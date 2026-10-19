# G37: privacy inventory and retention handoff (existing roles)

Tool: `employees/legal-compliance/compliance-auditor/privacy_inventory.py` (rules: `privacy-inventory.md`).
Every person, name and contact token here is synthetic; no real personal record is used. Tables come from the
data engineer's G13 contracts. This works inside compliance-auditor and legal-advisor; the data-privacy officer
role proposed in issue 10 stays a contributor proposal and is not registered.

## Run
```
python3 employees/legal-compliance/compliance-auditor/privacy_inventory.py review examples/capabilities/G37/fixtures/clean/package.json   # exit 0
python3 employees/legal-compliance/compliance-auditor/privacy_inventory.py review examples/capabilities/G37/fixtures/september/package.json   # exit 1
python3 employees/legal-compliance/compliance-auditor/privacy_inventory.py review examples/capabilities/G37/fixtures/september/package.json --out $STATE/handoff   # exit 1
python3 employees/legal-compliance/compliance-auditor/privacy_inventory.py review examples/capabilities/G37/README.md   # exit 2
python3 examples/capabilities/G37/privacy_oracle.py   # ACCEPTED 9/9
python3 examples/capabilities/G37/privacy_oracle.py -- python3 examples/capabilities/G37/naive_inventory.py   # REJECTED 0/9
python3 examples/capabilities/G37/privacy_oracle.py -- python3 examples/capabilities/G37/noop_inventory.py   # REJECTED 0/9
```

## Clean control
customers.csv (K1, K2) and orders.csv (A1-A3), all 14 fields inventoried, nothing past retention. R1 (access, K1,
verified, EU-GDPR clock one month) finds customers line 2 and orders lines 2 and 4; due 2026-10-10, closed on time.

## September, worked by hand (as of 2026-10-02T00:00Z)
Inventory: `birth_date` is in customers.csv but neither in the inventory nor in the G13 contract (G13 ignores it)
= `unmapped_field`; `fax` is inventoried but absent = `stale_inventory_entry`; `contact` flows to `crm-export`,
which is not a declared system. tickets.csv `body` is free text, so it is a qualified-review item.

| Table | Retention | Due records |
|---|---|---|
| customers.csv | 730 days from created_at | line 6 K9 (2024-01-15, expired 2026-01-14) |
| orders.csv | 2555 days from event_time, hold for review | line 6 K9 (2018-05-01, expired 2025-04-29): qualified review |
| tickets.csv | 365 days from opened_at | line 2 K2 (expired 2026-06-01), line 5 K9 (2025-03-01); line 6 anchor "not-a-date" is named, not guessed |

| Request | Facts | Result |
|---|---|---|
| R1 access K1 (sent twice) | GDPR, closed 09-20 | 3 records, on time; the copy collapses |
| R2 deletion K2 | CCPA 45 days from 08-01 = 09-15, still open | `overdue_request`; delete customers 3, tickets 2 and 3; orders 3 and 4 retained pending review; propagate to cfo-books, crm-export, helpdesk, warehouse |
| R3 access K3 | identity not verified | nothing looked up or shown |
| R4 correction K4 | received 01-31, one month = 02-28, closed 03-01 | `closed_late`; personal fields listed |
| R5 deletion K404 | no such subject | `no_records_found` |
| R6 access K1 | BR-LGPD has no configured clock | `unknown_jurisdiction_clock`, due unknown, review item |
| R7 | same id, access then deletion | `conflicting_request_ids`, both refused |
| line 10 | type "erase-everything" | `rejected_request_rows` |

Exit 1 with 9 named findings. The handoff lists 6 qualified-review items and 10 obligations.

## Oracle checks
o1 clean control; o2 the values above; o3 the unverified subject's name, contact token and birth date appear in no
output; o4 drift (a new column G13 ignores, a renamed one); o5 seeded drops with retention exactly on, one day and one
second around the boundary, missing subjects, copies, unverified requests and both clocks; o6 eight invalid packages
and an `--out` inside the package exit 2 and keep the previous output, then recovery; o7 four parallel runs with the
network blocked and unchanged data files; o8 review boundaries and traceable obligations; o9 20 000 people and 40 000 orders.
