# G22 payment refunds and inventory conservation: fixtures, oracle, controls, demo

- `fixtures/catalog.json`: a synthetic store (3 SKUs, USD). `fixtures/test-secret.txt`: a local demo
  signing value that grants nothing. `fixtures/september.jsonl`: 13 signed envelopes written by
  `make_stream.py` (fixed timestamps; ingest with `--now 1790000200`).
- `ledger_oracle.py [--tool PATH] [--seeds N]`: 10 checks against its own reference model and the G14
  reconciliation, with its own signing secret. Last line `PASSED n/m` or `REJECTED n/m`.
- `naive_ledger.py`: the same CLI without signature checks, dropping out-of-order events and booking
  phantom stock to avoid out-of-stock. Expected `REJECTED 5/10`. `noop_ledger.py`: expected `REJECTED 0/10`.

## The september stream, worked by hand

ord_1: 2 x mug-blue 12.50 + 1 x tee-m 19.99 = 44.99, captured 44.99 (evt_002, then delivered again:
duplicate). A forged refund and a capture signed an hour early are refused. evt_004 (refund 0.10,
restock 1 poster) and evt_003 (capture 0.30) arrive before ord_2 is placed (evt_005: 3 x poster 0.10 =
0.30): both are held, then applied when ord_2 arrives. ord_1 refund 12.50 with one mug restocked is
applied; a further 40.00 would exceed 44.99 - 12.50 = 32.49 and is an exception (unapplied 40.00).
ord_3 wants 5 tee-m with 3 available: out_of_stock. ord_4 reserves 3 tee-m, then is cancelled.
Totals: captured 45.29, refunded 12.60, net 32.69. Stock: mug-blue 10 - 2 + 1 = 9, poster 3 - 3 + 1 = 1,
tee-m 4 - 1 = 3, nothing reserved.

## Demo (run from the repository root; needs only python3)

```bash
set -e
T=$(mktemp -d)
S=employees/specialized/payments-specialist/payment_ledger.py
F=examples/capabilities/G22/fixtures
python3 $S init --db $T/ledger.db --catalog $F/catalog.json
python3 $S ingest --db $T/ledger.db --secret-file $F/test-secret.txt --events $F/september.jsonl --now 1790000200 > $T/first.json || echo "ingest exit $? (3: two envelopes refused)"
python3 $S ingest --db $T/ledger.db --secret-file $F/test-secret.txt --events $F/september.jsonl --now 1790000200 > $T/replay.json || echo "replay exit $?"
python3 $S report --db $T/ledger.db
python3 $S check --db $T/ledger.db
python3 $S export-g14 --db $T/ledger.db --out $T/books --period-start 2026-09-01T00:00:00Z --period-end 2026-10-01T00:00:00Z
python3 employees/leadership/cfo/cash_revenue_reconcile.py reconcile $T/books/package.json | head -3
rm -rf $T
```

Expected: both ingests exit 3 (the forged and stale envelopes); the replay changes nothing; the
report shows `USD net cash 32.69 (captured 45.29, refunded 12.60); 2 held or exception events`;
check prints `consistent`; G14 reconciles.
