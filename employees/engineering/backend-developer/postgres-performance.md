# Postgres performance: deterministic tuning + health (postgres-mcp Pro)

Absorbed from crystaldba/postgres-mcp ("Postgres MCP Pro", MIT, ~2.4k★, verified 2026-06-13) - the perf/index/EXPLAIN/health *methodology*. The MCP server is host-installed (Docker `crystaldba/postgres-mcp` or `pipx install postgres-mcp`); this file is how the backend uses it well.

The employee already knew the generic moves (EXPLAIN ANALYZE on >100ms, add indexes deliberately, kill N+1). What's net-new here is **doing it deterministically instead of by LLM guess** - classical algorithms + real planner simulation, not vibes.

## Core doctrine: deterministic tools beat gen-AI guessing
An LLM writing ad-hoc health queries and eyeballing indexes is unrepeatable and often wrong. Postgres MCP Pro pairs the LLM with proven algorithms: a real index-tuning search and PgHero-derived health checks. **When a deterministic tool exists for a DB task, use it; reserve the LLM for the ambiguous/reasoning parts (which query matters to the business, what tradeoff to accept).**

## Prerequisite extensions (say this to the host before tuning)
- `CREATE EXTENSION IF NOT EXISTS pg_stat_statements;` - per-query runtime/resource stats; the input to "what's actually slow".
- `CREATE EXTENSION IF NOT EXISTS hypopg;` - hypothetical indexes: simulate a planner's behavior *with an index that doesn't exist yet*, no write, no bloat.
On RDS/Azure/Cloud SQL these are usually available (just `CREATE EXTENSION`). Self-managed needs `pg_stat_statements` in `shared_preload_libraries` and a restart; `hypopg` may need OS-level install. No extensions → index tuning and top-query analysis are blind.

## Index tuning - the right order (don't hand-pick indexes blind)
1. **Find the targets, don't guess them.** Use top-queries-by-time (`pg_stat_statements`) - slow per-execution OR heavy in aggregate. Normalize so queries from one template count once (cheap workload compression).
2. **Generate candidates from the SQL**, not intuition: columns used in filters / joins / GROUP BY / ORDER BY, including multicolumn combinations.
3. **Simulate, don't deploy-and-pray.** Use `hypopg` "what-if" to get the planner's real cost estimate for each candidate against the actual cost model.
4. **Greedy search to an optimum** (Anytime-algorithm style): best 1-index solution → best index to add for a 2-index solution → stop when the time budget is spent or a round yields <10% gain.
5. **Cost-benefit, not max-performance.** Trade storage against speed: the default bar is roughly "up to 10x more space is worth a 100x speedup" (configurable). A faster plan that doubles disk for a 5% win is rejected.
6. **Show the before/after plans** for each chosen index so the decision is auditable, not a black box.

## Query plans
- `explain_query` with **hypothetical indexes** answers "would this index actually help?" *before* you write the migration - this is the upgrade over plain EXPLAIN ANALYZE.
- For normalized queries with stripped constants, feed realistic constants sampled from table stats so the plan is representative (Postgres 16 generic-plan EXPLAIN has `LIKE`-clause gaps this avoids).

## Database health checks (deterministic, PgHero-derived) - run periodically, not just when on fire
- **Index health:** unused indexes (drop them - write cost with no read benefit), duplicate indexes, bloated indexes (autovacuum reclaims dead tuples but doesn't compact pages).
- **Buffer cache hit rate:** low rate = too much disk I/O; investigate before it degrades app latency.
- **Connection health:** count + utilization; watch for connection exhaustion and idle/blocked pile-ups.
- **Vacuum health:** the one that bites hardest - transaction-ID wraparound can stop the DB accepting writes. Surface tables needing vacuum to freeze old XIDs.
- **Replication health:** primary↔replica lag, slot usage.
- **Constraint health:** invalid constraints (can appear after bulk loads / recovery).
- **Sequence health:** sequences approaching their max value.

## Safe SQL execution against real data
- Two access modes: **unrestricted** (full read/write - dev only, recreatable data) and **restricted** (read-only transactions + execution-time caps - for prod / untrusted data). Default to restricted against anything you care about.
- Read-only is enforced via a read-only transaction on a read-write connection, with the SQL **parsed (pglast) and rejected if it contains `COMMIT`/`ROLLBACK`** - closes the `ROLLBACK; DROP TABLE users;` escape. Don't enable unsafe stored-procedure languages on a DB you run restricted mode against; they can bypass it.
- Prompt-injection note: results are wrapped, but always review tool calls before executing against real data - same discipline as any DB-connected LLM.

## When to reach for this MCP
- "App is slow / this query is slow" → top-queries → hypopg simulate → recommend index with before/after plans + cost-benefit.
- Pre-deploy or periodic ops → run `analyze_db_health` and act on index/vacuum/connection findings.
- Designing a schema change → simulate the index impact before writing the migration, then loop in DBA per the existing >3-column / new-index review rule.
