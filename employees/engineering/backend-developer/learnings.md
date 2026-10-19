
## 2026-07-24 engineering-core upstream
- Pin greenfield to Laravel 13 + PHP 8.3-8.5, Node 24 Active LTS, .NET 10 LTS, PostgreSQL 17+.
- Toolchain mismatch fails closed with one `BLOCKED toolchain:` cause before implementation.
- Source pins: laravel.com/docs/13.x/releases, nodejs.org previous-releases, dotnet support policy.
## 2026-10-18 - G19 duplicate-safe API and tenant boundaries
- Idempotency record, effect and audit row in one `BEGIN IMMEDIATE` transaction: 32 concurrent replays made 1 invoice; 16 parallel payments of 300 on 1000 accepted exactly 3.
- `ThreadingHTTPServer` listens with a backlog of 5: bursts of concurrent retries were reset before reaching the handler (the oracle saw status 0). Subclass with `request_queue_size = 128`; setting it on an instance after construction has no effect.
- Store 409 business conflicts with the key, so a replay of a refused overpayment stays refused; do not store auth, validation or 404 answers.
- Reference: duplicate-safe-api.md, ledger_api.py (Workflow I).
## Sources

- Upstream: goldbergyoni/nodejs-testing-best-practices (license not recorded); shieldfy/API-Security-Checklist (license not recorded); zalando/restful-api-guidelines (license not recorded); OWASP/CheatSheetSeries (license not recorded); OWASP/API-Security (license not recorded)
- What was used: methodology absorbed: goldbergyoni/nodejs-testing-best-practices; methodology only: shieldfy/API-Security-Checklist, zalando/restful-api-guidelines, OWASP/API-Security; connected as external reference: OWASP/CheatSheetSeries
- License notes: licenses not recorded in scan for: goldbergyoni/nodejs-testing-best-practices, shieldfy/API-Security-Checklist, zalando/restful-api-guidelines, OWASP/CheatSheetSeries, OWASP/API-Security - verify before reuse; no code vendored
