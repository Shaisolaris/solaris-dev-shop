# Signed-webhook order ledger (local, synthetic)

`payment_ledger.py` is a working local model of the part of a store backend that takes payment
webhooks: orders, captures, partial refunds and cancels, with exact money and conserved stock. It
never contacts a payment provider. Events are local JSON files, signed with a local test secret
(`examples/capabilities/G22/fixtures/test-secret.txt` is a demo value that grants nothing). Python
3.9+ stdlib, one SQLite file. It is the reference behaviour to port into a real handler, not a
replacement for the provider's own idempotency or for reconciliation against the provider's records.

## Rules it proves

1. **Verify before reading.** An envelope is `{"signature": "t=<unix>,v1=<hex>", "body": "<raw JSON>"}`;
   `v1` is HMAC-SHA256 of `"<t>.<body>"` with the secret, compared in constant time. A wrong
   signature or `t` more than `--tolerance` seconds (default 300) from `--now` is refused, and
   nothing is stored.
2. **One effect per event id.** The id, the body hash and the effect commit in one transaction. The
   same id and body again: `duplicate`, no effect. The same id with another body: refused as
   `conflicting_replay`. A payment or refund id already recorded is an exception.
3. **Exact money.** Amounts and prices are strings with at most two decimals, held as integer cents.
   A JSON float anywhere in an event refuses it; `"0.300"` is not an amount.
4. **Out of order is held.** A capture, refund or cancel whose order has not arrived, or a refund
   before its capture, is `held` and applied as soon as its prerequisite is applied (in event time
   order). Held events stay listed until then.
5. **Stock is conserved.** Placing an order reserves stock only if `on_hand - reserved` covers it
   (otherwise `out_of_stock`, nothing reserved); a capture ships it; a cancel releases it; a refund
   restocks at most what that order shipped. Per SKU: `initial = on_hand + shipped - restocked` and
   `reserved` equals the quantity of placed, uncaptured orders. Concurrent ingests are serialised by
   `BEGIN IMMEDIATE`, so they cannot oversell.
6. **Anomalies are named, money stays visible.** `capture_amount_mismatch`, `capture_on_cancelled_order`,
   `order_already_captured`, `refund_exceeds_captured`, `restock_exceeds_shipped`,
   `refund_on_uncaptured_order`, `cannot_cancel_<status>_order`, `out_of_stock`. A capture or refund
   that is not applied is kept as unapplied money in the report, never dropped.

## Commands

```bash
python3 employees/specialized/payments-specialist/payment_ledger.py init --db ledger.db --catalog examples/capabilities/G22/fixtures/catalog.json
python3 employees/specialized/payments-specialist/payment_ledger.py sign --secret-file secret.txt --body-file event.json --t 1790000000
python3 employees/specialized/payments-specialist/payment_ledger.py ingest --db ledger.db --secret-file secret.txt --events stream.jsonl --now 1790000200
python3 employees/specialized/payments-specialist/payment_ledger.py report --db ledger.db --json
python3 employees/specialized/payments-specialist/payment_ledger.py check --db ledger.db
python3 employees/specialized/payments-specialist/payment_ledger.py export-g14 --db ledger.db --out books/ --period-start 2026-09-01T00:00:00Z --period-end 2026-10-01T00:00:00Z
```

Events: `order.placed {order_id, currency, lines:[{sku, qty}]}` (prices come from the catalog),
`payment.captured {order_id, payment_id, amount}` (must equal the order total),
`refund.succeeded {order_id, refund_id, amount, restock:[{sku, qty}]}`, `order.cancelled {order_id}`.
Each event is `{id, type, created, data}` and nothing else. `--crash-after N` exits 70 after N
envelopes (drill); rerunning the whole batch is safe. `check` opens the file read-only and names each
broken invariant (stock identity, stock moves, reservations, order totals, money rows, event states).

`export-g14` writes a G14 package (`employees/leadership/cfo/cash-revenue-reconciliation.md`): one
invoice per captured order (goods ship at capture, so delivery evidence is the capture time), the
captures as payments, and each applied refund as a credit note plus the cash refund it settles.
G14 then reconciles with recognized revenue and net cash equal to the ledger's net cash.

| Exit | Meaning |
|---|---|
| 0 | `ingest`: every event applied or duplicate; `check`: consistent |
| 1 | `ingest`: held events or exceptions are open; `check`: violations |
| 2 | invalid input or file, nothing written |
| 3 | `ingest`: at least one envelope refused (signature, time, malformed or conflicting replay) |
| 70 | deliberate crash drill |

## Limits

One currency per ledger and one capture per order (no partial or multi-capture, no disputes or
chargebacks, no tax or shipping lines). Held events wait forever; there is no expiry or alert. The
signature scheme mirrors common provider schemes but is local; real handlers must use the
provider's verification library and secret rotation. `examples/capabilities/G22/ledger_oracle.py`
judges a ledger against its own reference model; naive and no-op controls sit beside it.
