# Duplicate-safe API and tenant boundaries (local, synthetic)

`ledger_api.py` is a small working invoice API that shows the two server rules most often broken
in client work, and proves them by running:

1. **One intended effect per request.** Every write needs an `Idempotency-Key`. The key, the effect
   and the audit row are written in one SQLite transaction (`BEGIN IMMEDIATE`), so a retried,
   replayed or concurrent duplicate gets the first answer back (`Idempotent-Replayed: true`)
   instead of a second invoice or payment. A key reused for a different request is refused.
2. **Tenant scope comes from the caller's key, never from the request.** Every lookup includes the
   tenant. Another tenant's invoice answers exactly like a missing one (404 `not_found`, no data).
   A `tenant_id` in the body is refused; tenant headers are ignored.

It is a local demonstration, not a hosted service: it binds to a loopback address only (any other
`--host` exits 2), uses Python 3.9+ stdlib only and never makes an outbound call. Callers and keys
come from a principals file (`solaris.ledger-principals/1`); the shipped
`examples/capabilities/G19/fixtures/principals.json` holds synthetic local keys only.

## Run it

```bash
python3 employees/engineering/backend-developer/ledger_api.py serve --db <ledger.db> --principals <principals.json> --ready-file <ready.json> &
until [ -s <ready.json> ]; do sleep 0.1; done
PORT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["port"])' <ready.json>)
curl -s -X POST http://127.0.0.1:$PORT/api/v1/invoices -H 'Authorization: Bearer <editor-key>' -H 'Idempotency-Key: <key>' -d '{"customer": "<customer>", "amount_cents": 1000, "currency": "USD"}'
curl -s -X POST http://127.0.0.1:$PORT/api/v1/invoices -H 'Authorization: Bearer <editor-key>' -H 'Idempotency-Key: <key>' -d '{"customer": "<customer>", "amount_cents": 1000, "currency": "USD"}'
curl -s http://127.0.0.1:$PORT/api/v1/invoices -H 'Authorization: Bearer <editor-key>'
curl -s http://127.0.0.1:$PORT/api/v1/invoices -H 'Authorization: Bearer <other-tenant-key>'
python3 employees/quality-security/security-auditor/boundary_probe.py --base-url http://127.0.0.1:$PORT --principals <principals.json>
kill %1
python3 employees/engineering/backend-developer/ledger_api.py check --db <ledger.db>
```

The second POST repeats the first and returns the same invoice; the owner's list holds it once,
the other tenant's list does not hold it at all, the probe reports 0 findings and `check` says
`consistent`. `--port 0` (the default) picks a free port and writes it to the ready file.

## Endpoints

This is the complete list. `ROUTES` in `ledger_api.py` is the source of truth and
`tests/test_g19_capability.py` fails if this table and the code disagree.

| Method | Path | Auth | Idempotency-Key | Success | Errors |
|---|---|---|---|---|---|
| GET | /api/v1/health | none | no | 200 `{ok, version}` | |
| POST | /api/v1/invoices | editor | required | 201 invoice + `Location` | 400, 401, 403, 413, 422 |
| GET | /api/v1/invoices | viewer or editor | no | 200 `{data, next_after}` | 401, 422 |
| GET | /api/v1/invoices/{id} | viewer or editor | no | 200 invoice | 401, 404 |
| POST | /api/v1/invoices/{id}/payments | editor | required | 201 invoice | 400, 401, 403, 404, 409, 422 |
| POST | /api/v1/invoices/{id}/void | editor | required | 200 invoice | 400, 401, 403, 404, 409, 422 |

- Auth: `Authorization: Bearer <key>`. Missing or unknown key: 401 `unauthenticated`. A viewer
  writing: 403 `forbidden`.
- Create body: `{"customer": 1-80 chars, "amount_cents": integer 1..10^12, "currency": "EUR"|"GBP"|"USD"}`.
  Payment body: `{"amount_cents": integer}`. Void body: `{}` or `{"reason": up to 200 chars}`.
  Unknown fields: 422 `unknown_field`; `tenant`, `tenant_id`, `owner`, `created_by`: 422
  `tenant_is_server_derived`. Booleans and floats are not amounts (422 `invalid_amount`).
- Invoice: `{id, tenant, customer, amount_cents, currency, paid_cents, balance_cents, status
  (open|paid|void), version}`. Ids are random (`inv_` + 16 hex), not sequential.
- List: `?limit=1..100` (default 20) and `?after=<id of the last row>`; `next_after` is null on the
  last page. A cursor from another tenant is 422 `invalid_cursor`, the same as a made-up one.
- Errors always use `{"error": {"code", "message"}}`; no stack traces or SQL. Other codes:
  400 `invalid_json` (also duplicate JSON keys), `idempotency_key_required`,
  `invalid_idempotency_key` (1-128 of `A-Z a-z 0-9 . _ : -`); 404 `no_route`; 405
  `method_not_allowed`; 409 `exceeds_balance`, `invoice_not_open`, `cannot_void`; 411; 413
  `body_too_large` (over 16 KiB); 503 `transient_failure` or `storage_busy` (rolled back, retry
  with the same key).

## Idempotency rules

- Keys are scoped per tenant. Two tenants using the same key get their own results.
- The stored answer is replayed only for the same request (method, endpoint, invoice id and body).
  A different request with a used key: 422 `idempotency_key_reused`, nothing changes.
- Successful writes and 409 business conflicts are stored, so a replay of a refused overpayment
  stays refused even if the balance changes later. Auth, validation and 404 answers are not stored:
  nothing happened, so the key stays usable once the request is fixed.
- Concurrent payments with different keys are serialised by the write transaction, so an invoice
  can never be overpaid (16 parallel payments of 300 on 1000: exactly 3 accepted).

## Restart and retry drill

`--fault-plan FILE` (`solaris.ledger-fault-plan/1`) makes named keys fail on purpose:
`{"schema": "solaris.ledger-fault-plan/1", "fail_before_commit": {"<key>": 1}, "crash_before_commit": ["<key>"], "crash_after_commit": ["<key>"]}`.
`fail_before_commit` rolls back and answers 503; `crash_*` kill the process (exit 70) before or
after the commit, so the client sees a dropped connection. Restart the server on the same `--db`
without the plan and retry with the same key: a crash before commit makes the effect once, a crash
after commit replays the stored answer. Either way there is exactly one effect. Use the plan for
drills only.

## Check stored state

`ledger_api.py check --db FILE [--json]` opens the database read-only and verifies that every
invoice's `paid_cents` equals its payments, statuses match amounts, every payment belongs to its
invoice's tenant, and every stored effect has exactly one audit row (the audit table is
append-only by trigger). Exit 0 consistent, 1 violations (each named), 2 unusable file.

## Probe it (security-auditor)

`employees/quality-security/security-auditor/boundary_probe.py` runs checks B1-B10 (replay,
overspend race, cross-tenant read/list/write, tenant smuggling, key scope, key reuse, 401/403)
against a local instance and writes findings with CWE, severity and evidence. It refuses any base
URL that is not loopback before sending a request, and it writes synthetic records, so point it only
at a disposable instance. Exit 0 no findings, 1 findings, 2 refused, 3 inconclusive (the target did
not behave like a working API).

## Boundaries of the demo

- **Canonical headers only.** A request is expected to carry exactly one `Authorization: Bearer <key>`
  and, on writes, exactly one `Idempotency-Key`. Repeated headers are not refused: the server reads the
  first of each and ignores the rest (two `Authorization` headers act as the first caller; two
  `Idempotency-Key` headers store the effect under the first key only, so a retry that sends only the
  second key makes a second effect). The tenant and duplicate guarantees above hold for canonical
  single-header requests. Anything that merges, reorders or adds these headers (a proxy, gateway or
  client library) is outside what was tested.
- **Loopback demo only.** The server binds to a loopback address only (127.0.0.0/8 or ::1), the probe
  refuses any other base URL, the G19 oracle connects to 127.0.0.1 only, and all keys and records are
  synthetic. It was not run behind a proxy or on a network, and it makes no
  production, hosted-service or security-certification claim.

## Limits

One SQLite file and one process; writes are serialised, which is the point here but caps write
throughput. No rate limiting, TLS, key rotation or migrations framework; keys live in a local file.
Idempotency records are kept forever (no expiry). This is the reference behaviour for client work,
not a framework to deploy.
