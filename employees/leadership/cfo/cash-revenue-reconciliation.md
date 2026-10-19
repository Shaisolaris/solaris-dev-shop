# Recognized revenue versus cash (cash_revenue_reconcile.py)

For synthetic or exported books on local files. It reconciles invoices, payments, credit notes and
refunds for one period, per currency, to the cent, and keeps everything it cannot use visible. It does
not post journals, convert currencies, file taxes or replace the accounting system of record.

## Package (schema solaris.cash-revenue/1)

```
timezone   IANA zone for times without an offset (default UTC)
period     {start, end}: end exclusive
as_of      optional cutoff: rows loaded after it are late; rows without loaded_at are excluded and named
invoices   invoices.csv: invoice_id, customer_id, currency, amount, issued_at, delivered_at, status (issued|void), loaded_at
payments   payments.csv: payment_id, invoice_id, currency, amount, received_at, loaded_at
credits    credits.csv: credit_id, invoice_id, kind (credit_note|refund), currency, amount, issued_at, loaded_at
bank       optional bank.csv: currency, cash_in, cash_out (period totals from the statement)
```

Each table may add `header_aliases`, `thousands_separator` and `delimiter`. Parsing, typed values and
row rejects come from the G13 data-engineer reader (`data-engineer/csv_reconcile.py`).

## Command

```bash
T=employees/leadership/cfo/cash_revenue_reconcile.py
python3 $T reconcile package.json                   # summary per currency
python3 $T reconcile package.json --json --out r.json
```

Exit codes: 0 reconciled with no exceptions and controls matching; 1 reconciled with exceptions or a
control difference (each listed); 2 invalid package or input, nothing written.

## Rules

- **Currencies are never combined.** Every figure is per currency; no FX conversion. A payment in a
  currency other than its invoice's stays unapplied cash in its own currency (`currency_mismatch`).
- **Revenue is not cash.** An invoice is recognized when `delivered_at` evidences delivery. A credit note
  after delivery is contra-revenue in its period; before delivery it reduces deferred revenue. Delivery
  before the invoice is issued creates unbilled revenue until it is. Payments and refunds move cash and
  receivables only.
- **Balances** as at the period start and end: receivables net, split into amounts owed and customer
  credit balances (overpayment), deferred, unbilled and unapplied cash.
- **Checks that must close to the cent**: AR roll-forward (opening + billed - credit notes - applied
  payments + applied refunds = closing), revenue-to-cash bridge (revenue - net cash = change in AR -
  change in deferred + change in unbilled - change in unapplied), and the cash ledger.
- **Nothing silently dropped**: rejected rows (with line and reason), late rows, rows without loaded_at,
  conflicting versions of one id (all excluded), unapplied payments and refunds, unlinked credit notes,
  invoices without delivery evidence. Exact repeats of a row count once.
- **Reason values** (exactly as emitted in `exceptions.unapplied[].reason` and
  `exceptions.unlinked_credits[].reason`): `no_invoice_reference`, `unknown_invoice`, `currency_mismatch`,
  and `invoice_<why>` when the invoice itself was excluded: `invoice_void`, `invoice_late`,
  `invoice_no_loaded_at`, `invoice_conflicting_versions`, `invoice_missing_value`, `invoice_bad_amount`,
  `invoice_bad_status`. Unlinked credit notes can also carry `credit_note_before_invoice`. Rejected rows
  use `missing_value`, `bad_amount`, `bad_status`, `bad_kind` (plus the G13 reader's own reasons).
- **Negative transactions are challenged**: refunds applied to an invoice above the payments applied to
  it (`exceptions.over_refunded`: paid, refunded, excess) and credit notes above the invoice amount
  (`exceptions.over_credited`: invoice amount, credit notes, excess) are listed and give exit 1. The
  arithmetic is still reported as booked (revenue can go negative, the excess shows as AR owed); the
  exception is what tells the reader it needs an explanation. Equal amounts are not challenged. Totals are
  taken over every included row known by as_of, including rows dated after the period end, so a refund
  dated before the payment it returns is not challenged once that payment is in the book.
- **Bank control**: per currency, statement cash in and out against the ledger; differences and
  currencies present on one side only are reported, never forced.

## Limits

- Point-in-time recognition on delivery; ratable (over-time) recognition, tax, FX and write-offs are not
  modelled. Two-decimal amounts only.
- Not run: any accounting system, bank feed or payment provider.
