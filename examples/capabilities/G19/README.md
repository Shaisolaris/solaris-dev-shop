# G19 boundary oracle

`boundary_oracle.py` starts a candidate local API on 127.0.0.1 with its own seeded synthetic
principals (four tenants), drives it with its own HTTP client and compares every answer and listing
with what it asked for. It does not use the shipped probe. A candidate is any command that accepts

```
<cmd> serve --db FILE --principals FILE --port 0 --ready-file FILE [--fault-plan FILE]
```

and serves the endpoints in `employees/engineering/backend-developer/duplicate-safe-api.md`.

```bash
PY=python3
API=employees/engineering/backend-developer/ledger_api.py
$PY examples/capabilities/G19/boundary_oracle.py --server "$PY $API"                                  # must pass 10/10
$PY examples/capabilities/G19/boundary_oracle.py --server "$PY examples/capabilities/G19/vulnerable_stub.py"  # must fail
$PY examples/capabilities/G19/boundary_oracle.py --server "$PY examples/capabilities/G19/noop_stub.py"        # must fail
```

Checks: o1 clean control with exact values; o2 32 concurrent replays of one create; o3 payment
replays and a 16-way overspend race; o4 cross-tenant reads, lists, cursors and paging; o5
cross-tenant pay/void and tenant smuggling; o6 per-tenant keys and key reuse; o7 exact 401/403;
o8 transient failure, crash after commit and crash before commit retried across a restart; o9
shuffled duplicate-laden load over four tenants (`--scale`, default 2000 requests); o10 invalid
input (non-loopback host, bad principals, bad bodies) makes nothing. `--seed` changes the tenants'
data and the load order.

- `vulnerable_stub.py`: a deliberately broken API (ignores the key on lookups, trusts `tenant_id`
  in the body, no idempotency, read-modify-write without a transaction). Synthetic, loopback only.
- `noop_stub.py`: answers every call but stores nothing.
- `fixtures/principals.json`: synthetic local keys for two tenants (northwind, harbor), each with an
  editor and a viewer. They grant nothing anywhere else.

The probe for auditors is `employees/quality-security/security-auditor/boundary_probe.py`.
Nothing here contacts a host other than 127.0.0.1. POSIX, Python 3.9+.
The oracle sends canonical single `Authorization` and `Idempotency-Key` headers only; repeated-header
handling and anything behind a proxy are outside what it checks (see duplicate-safe-api.md, Boundaries).
