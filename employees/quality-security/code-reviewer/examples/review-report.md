## 🚨 Blockers
- src/api/orders.ts:142 - SQL built by string concatenation with request input
  (`"SELECT * FROM orders WHERE status = '" + req.query.status + "'"`) - SQLi.
  Fix: parameterize - `db.query("SELECT * FROM orders WHERE status = $1", [status])`
  and add a regression test hitting `status=' OR '1'='1`. Why it matters: the
  endpoint is internet-facing; an attacker reads or drops the orders table -
  data-loss class, blocks merge per the severity taxonomy.

## Verdict
Request-changes - 1 Blocker, 1 Important. Re-review after the SQLi fix + test land.

## Coverage + security + perf assessment
Lane: Full PR Review (all 7 steps). All 9 changed files opened in full; tests
reviewed first. NOT reviewed: payments module (outside the diff). Deps:
`npm audit --production` run - 0 CVEs; express 1 major behind (P2, tracked).
Secrets: working tree + git history clean.

Gate: passed
