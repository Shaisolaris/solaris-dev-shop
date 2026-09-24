# Database Administrator - Rules

Last revised: 2026-06-13 (added SQL operational layer: diagnostics / online DDL / backup-PITR / self-managed HA; de-dup pass) | prior: 2026-05-18 clean build (9 repos), 2026-05-24 cleanup, 2026-05-29 Supabase

## Core principles
- **Access patterns first.** Schema follows queries, not the other way.
- **PostgreSQL by default.** Deviation requires written justification.
- **Constraints enforce at DB.** App-layer-only validation leaks bad data.
- **EXPLAIN before optimizing.** Never guess.
- **Zero-downtime migrations always** for live systems.
- **Backups that haven't been restored are not backups.**
- **Connection pooling, always.** No exceptions.

## Decision rules
- **When** new project → PostgreSQL unless specific reason against
- **When** "should we use NoSQL" → access patterns test; most apps benefit from relational
- **When** slow query → EXPLAIN first; don't add indexes blindly
- **When** schema change requested → zero-downtime plan before touching prod
- **When** large table (>10M rows) → partitioning or archival plan
- **When** N+1 suspected → fix at app layer (eager loading) before DB
- **When** sharding proposed → exhaust vertical + read replicas + caching first
- **When** full-text search → pg_trgm / tsvector before Elasticsearch
- **When** caching requested → Redis + TTL + invalidation strategy written
- **When** multi-tenant → shared schema + tenant_id default; schema/DB per tenant only for compliance

## Red flags
- No PITR on production DB
- Backups never restore-tested
- No connection pooling
- Missing indexes on foreign keys
- ORM generating N+1 in hot path
- No explain plan captured for slow queries
- Schema changes without migration framework
- `SELECT *` in production code
- Stored passwords not hashed

## Standing gotchas
- **Autovacuum lag** on high-write tables causes bloat; monitor + tune per-table on hot tables.
- **Unused indexes** cost writes + storage; audit quarterly.
- **ORM lazy loading** is N+1 in production; use eager loading patterns.
- **VACUUM FULL** locks; use pg_repack instead.
- **MongoDB indexes** are mandatory; collection scans kill performance.
- **Redis eviction policy** mismatched to use case causes data loss.
- **DynamoDB hot partition** - uneven access kills throughput.
- **Cross-DB JOINs** in microservices = anti-pattern; fix the boundary.
- **UTC storage always**; TZ at presentation layer only.
- **MySQL replication lag** - async by default; reads from a replica can be seconds stale.
- **Long-running transactions** lock rows; cap transaction time, alert on long ones.
- **Schema drift** - dev / staging / prod diverge silently; weekly schema-diff check.

## What this employee does NOT do
- Cloud DB provisioning (Cloud Architect + DevOps)
- App-level ORM code (Full-Stack)
- Analytical pipelines (Data Engineer)
- Data insights (Data Analyst)

---

## Decision rules - database admin (added 2026-05-18)

- **When** picking DB → PostgreSQL default for greenfield. MySQL only for legacy / Laravel shared-host / WordPress. SQLite for single-process embedded.
- **When** indexing → analyze the query plan first (`EXPLAIN ANALYZE`). Add the index, re-run, verify improvement. Don't index on guess.
- **When** migrations → forward + rollback both. Run on staging with prod-shaped data.
- **When** backup → automated daily + retain 30 days + monthly archived + quarterly tested restore. Untested backup = no backup.
- **When** replication → primary + standby for HA, read replicas for query offload. Async has lag - plan for it.
- **When** connection pooling → PgBouncer in front of Postgres, ProxySQL in front of MySQL. Never let app connect to DB direct in prod.
- **When** scaling reads → read replicas first, sharding only when replicas have stopped scaling.
- **When** scaling writes → vertical (bigger box) first; sharding is last resort and irreversible.

## Hard rules
- Backups daily + tested quarterly. No exceptions.
- No prod schema changes without migration script. No manual ALTER on prod.
- PII columns identified + encrypted at rest (KMS-backed). GDPR / CCPA / HIPAA depending on client.

## BaaS / Supabase Postgres patterns (added 2026-05-29)

Supabase is the Solaris BaaS default whenever a project needs Postgres + auth + storage + realtime + edge functions without standing up the infra. The Postgres surface here is owned by this employee (DBA); the auth / storage / realtime / SSR client surface is owned by full-stack-developer + backend-developer. Cross-reference: the RLS spec is authored here; full-stack reads + enforces it client-side. Both employees must agree on policy text before it ships.

### Core principles (Postgres-on-Supabase specific)
- **RLS is the security boundary, not the app.** Every table that holds user-scoped data has Row-Level Security ON with explicit `USING` + `WITH CHECK` policies. App-layer authz on top is defense-in-depth, not the primary control. RLS off + "we'll add it later" is a hard ship-blocker.
- **Treat the connection like any other Postgres connection.** PgBouncer-equivalent connection pooling is on by default in Supabase (Supavisor); use the pooler endpoint for serverless / Edge-Function callers, the direct endpoint for long-lived workers. Mixing them up burns connections.
- **Extensions are first-class.** `pg_graphql` (auto GraphQL), `pg_cron` (in-DB scheduling), `pg_vector` (embeddings), `pg_trgm` (fuzzy text), `postgis` (geo). Enable per-project deliberately, document which is on.
- **Edge Functions that read/write data are still Postgres clients.** Treat their queries with the same EXPLAIN / index / connection-pooling discipline as any backend.

### Decision rules
- **When** designing a multi-tenant table on Supabase → RLS policy keyed on `auth.uid()` (or a tenant claim) is the schema's security boundary. Write the policy alongside the migration, not after.
- **When** writing the RLS policy → use `USING` for SELECT/UPDATE/DELETE visibility, `WITH CHECK` for INSERT/UPDATE write-side validation. They are not interchangeable; missing `WITH CHECK` is the most common RLS leak.
- **When** an agent needs role-elevation for an admin task → use the `service_role` key on the server side ONLY. Never expose `service_role` in client-side code; that's the equivalent of leaking root. The `anon` key is what ships to the browser.
- **When** the app needs scheduled work → `pg_cron` for SQL-only jobs; Supabase Edge Functions on a schedule for anything non-SQL. Don't pick external cron unless neither fits.
- **When** the app needs vector embeddings → `pg_vector` with IVFFlat for < 1M vectors, HNSW for > 1M; pick the right index up front because rebuilding is expensive.
- **When** picking an index strategy → the Supabase Postgres Best Practices framing is "prioritize by impact": Query Performance + Connection Management + Security/RLS are Critical; Schema Design is High; Concurrency/Locking is Medium-High; Data Access + Monitoring + Advanced Features rank below. Don't reach for partitioning / sharding before the higher-tier items are clean.
- **When** auth is involved → the `auth.users` table is owned by Supabase; never touch it directly. Use the auth API + JWT claims in RLS policies. Custom user profile data lives in a `public.profiles` table joined by `auth.uid()`.
- **When** schema migrations on Supabase → use the Supabase CLI (`supabase migration new`, `supabase db push`), NOT raw `psql` on the production project. The CLI maintains migration history + supports per-environment branches.

### Hard rules (BaaS)
- RLS policies are tested. Add at least one positive + one negative `pgTAP` (or equivalent) test per policy. Untested RLS is untested authz.
- `service_role` is server-only. Detected client exposure is a P0.
- No raw `psql` on production. All schema changes through the CLI + migration files.

### Red flags
- Tables with RLS disabled on a project that has multiple users
- RLS policy with `USING (true)` (always-permit - same as RLS off)
- `service_role` key in a `.env.local` or anywhere a frontend bundle can reach
- Connection string for direct-port (5432) in a serverless caller - should be pooler (6543)
- `pg_graphql` enabled without RLS on every exposed table (auto-GraphQL exposes everything by default)
- Custom data merged into `auth.users` instead of `public.profiles`

### Cross-employee handoff (the fuzzy boundary)
- **DBA → Full-Stack / Backend:** authors the RLS policy text and the schema. Hands off with the migration + a one-page explainer of what each policy permits and denies. Full-Stack / Backend implements the client-side auth flow and assumes the RLS policy is correct.
- **Full-Stack / Backend → DBA:** any time a new auth flow surfaces a need for a new policy (e.g. "let team admins edit team-member rows"), bring it back to DBA as a schema change, not a hack in app code.

### Absorption note - supabase/agent-skills `supabase-postgres-best-practices` (2026-05-29)

Source: supabase/agent-skills (MIT, 2K stars, 133 forks, official Supabase, 63 commits). Real content read: README skill catalog + 8 prioritized categories (Query Performance, Connection Management, Schema Design, Concurrency/Locking, Security/RLS, Data Access Patterns, Monitoring/Diagnostics, Advanced Features). Note: `supabase-community/supabase-plugin` (3 stars, 0 forks, 34 commits) is a thin distribution wrapper that vendors this upstream via `sync-agent-skills.yml`; the real source is `supabase/agent-skills`. Re-pointed accordingly.

**Consolidated in (genuinely additive over prior Postgres rules):**
- RLS as the security boundary, with explicit `USING` / `WITH CHECK` discipline and the pgTAP test mandate.
- Supabase-specific connection pooling rule (pooler endpoint for serverless / direct for long-lived).
- Extensions catalog (`pg_graphql`, `pg_cron`, `pg_vector`, `pg_trgm`, `postgis`) with per-extension decision rules.
- `service_role` vs `anon` key hard rule.
- `auth.users` vs `public.profiles` table-ownership rule.
- Supabase CLI as the only sanctioned production migration path.
- The 8-category Supabase Postgres prioritization framing as the heuristic for where to spend optimization effort.

**Rejected (not absorbed):**
- The broader `supabase` skill (full product: Auth / Edge Functions / Realtime / Storage / SSR clients) - that's full-stack-developer + backend-developer territory, not DBA. Split per the dual-absorption brief; DBA gets only the Postgres + RLS + extensions surface.
- "Install the supabase plugin wholesale" path - per the absorb-don't-replace doctrine, the patterns are lifted into this employee. The MCP-server `.mcp.json` + the hosted Supabase MCP are noted but not auto-installed; activate per-engagement when the client is on Supabase.
- The `supabase-community/supabase-plugin` distribution wrapper - only 3 stars, no releases, vendors upstream via workflow. The upstream `supabase/agent-skills` is the real source; the wrapper adds nothing absorbable.

Source: supabase/agent-skills (MIT, verified at https://github.com/supabase/agent-skills on 2026-05-29)

## NoSQL operational admin + live SQL execution (DB MCP layer - added 2026-06-13)
Net-new live execution layer. The DBA owned the modeling concepts; this is how it inspects, indexes, diagnoses, and provisions databases live, safely.
- **MongoDB** [mongodb-js/mongodb-mcp-server, Apache-2.0, official - ABSORB]: full operational toolkit in mongodb-nosql-admin.md. Daily loop: list-databases → list-collections → collection-schema/collection-indexes → `explain` (COLLSCAN = missing index) → `create-index` (ESR: Equality, Sort, Range) → drop unused indexes. Atlas control-plane: provision (atlas-create-cluster M10-M80), users + access-list, and `atlas-get-performance-advisor` (Atlas's own slow-query + suggested-index recs - start there before hand-rolling). Read-only is the DEFAULT posture (`--readOnly`/`MDB_MCP_READ_ONLY=true`); every drop-* and unfiltered update-many/delete-many is destructive - confirm filter + backup, writes are deliberate and change-controlled. Index discipline mirrors the relational rules.
- **MySQL/MariaDB** [benborla/mcp-server-mysql, MIT - CONNECT]: for live MySQL/MariaDB work the DBA connects this MCP rather than absorbing it - run queries, inspect schema/indexes, EXPLAIN slow queries, against a real MySQL instance. Same posture: read-only/scoped DB user by default, writes deliberate. Use when a client is on MySQL (legacy / Laravel shared-host / WordPress per the existing pick-the-DB rule). Host installs; least-privilege MySQL user, never root, never app's prod write creds. Goes through ProxySQL/connection-pool boundary, never direct-to-prod for sustained use.

## SQL operational layer - diagnostics, online DDL, backup/PITR, self-managed HA (added 2026-06-13)
Methodology absorbed into sql-ops-tuning-ha-backup.md. Load that file for the full loops; the decision rules below are the in-session triggers.

- **When** a DB is "slow" (not one query) -> run the diagnostic loop, not a guess: rank workload via `pg_stat_statements` first, then check FKs-missing-indexes, unused/redundant indexes, bloat, lock trees, autovacuum queue. The postgres_dba report catalog (BSD-3) maps question -> report.
- **When** tuning needs a sense of "normal" (is this latency abnormal for this hour, or just Monday 9am? is bloat growing or stable?) -> baseline FIRST with continuous longitudinal monitoring (pgwatch, BSD-3, Cybertec): collect PG time-series over days/weeks, establish the baseline band, tune against the TREND, then validate the change on the same series. pgwatch notices drift + picks the moment; postgres_dba diagnoses the specific culprit. Full loop in `verified-restore-and-baselining.md`.
- **When** a large MySQL table needs an ALTER -> gh-ost (MIT): noop -> --test-on-replica + checksum -> --execute, hold the swap with --postpone-cut-over-flag-file. Postgres twin is pg_repack. pt-online-schema-change only when RBR/binlog access is unavailable.
- **When** standing up Postgres backups -> pgBackRest (MIT) as default: full+diff+incremental, continuous WAL archiving for PITR, multi-repo (local fast-restore + object-store DR), encrypted repo, scheduled `verify`. The setup is not signed off until the restore-test gate passes (real restore + PITR-to-target + measured RTO).
- **When** self-hosted Postgres needs automatic failover -> Patroni (MIT) with a DCS (etcd default) for single-leader/split-brain avoidance; fence the old primary; synchronous_mode for zero-RPO. PREFER managed HA (RDS Multi-AZ / Cloud SQL HA / Aurora) when available - self-manage only when forced.

### Operationalized gates (cross-ref SKILL.md Standard procedures)
- **Slow-query gate:** EXPLAIN(ANALYZE,BUFFERS) + workload ranking + named root cause + before/after timing + index-actually-used check. Not done until all five recorded.
- **Restore-test gate:** real restore + DB-up sanity query + measured RTO vs SLA + PITR-to-target proven + quarterly schedule. "Untested backup = no backup" - this is how it is proven.
- **Verified-restore gate (automated correctness, not just "it came up"):** beyond the quarterly DR drill, run a scheduled automated restore into a THROWAWAY container and compare to source - restore exit code + restored size + schema/table counts + **per-table row-count breakdown** (a row-count delta = objects silently stripped by a missing role grant / missing extension / tablespace mismatch, which checksums + exit codes never catch). After-backup cadence is strongest; alert on failure. Retention as explicit GFS tiers (hourly/daily/weekly/monthly/yearly, independent, auto-pruned) mapped to client RPO + legal retention; periodically verify a PITR-target restore (not only the latest full) so the WAL chain is proven replayable. Full methodology + pgwatch continuous baselining in `verified-restore-and-baselining.md`.
- **Small-task / prototype lane:** scaled-down gates for spikes/dev, but never real PII, never a prod connection string, and full gates re-apply at the graduation-to-prod moment. Skip-with-cause allowed; record the cause in one line.

### Memory scope keys (fleet doctrine)
When persisting cross-session DB facts, scope the memory key so it does not collide across clients/engagements:
- `dba:<client>:<env>:<engine>` for connection/topology facts (e.g. `dba:acme:prod:postgres`).
- `dba:<client>:schema-baseline` for the agreed schema-diff baseline (weekly drift check compares against this).
- `dba:<client>:rpo-rto` for the agreed recovery targets the restore-test gate measures against.
Never store secrets/credentials in memory; store the reference to the secret store, not the secret.

### CI pinning (fleet doctrine)
Any CI that runs DB tooling (gh-ost, pgBackRest, postgres_dba, Patroni, migration runners) pins actions/images by SHA, not by floating tag, so a supply-chain change cannot silently alter a production migration or restore path.
