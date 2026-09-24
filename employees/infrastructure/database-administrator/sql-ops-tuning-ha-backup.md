# SQL operational layer - diagnostics, online DDL, backup/PITR, self-managed HA

Methodology absorbed 2026-06-13 from four verified 2026 sources. No third-party code is bundled; these are the operational loops + decision rules + the host-install / connect notes. Index discipline mirrors the relational rules already in rules.md (index before scale, ESR for compound, drop unused, let data drive decisions).

Sources: NikolayS/postgres_dba (BSD-3-Clause), github/gh-ost (MIT), pgbackrest/pgbackrest (MIT), patroni/patroni (MIT). All grep-verified net-new operational layers over the prior concept-only coverage.

---

## 1. Postgres diagnostic loop (postgres_dba - BSD-3-Clause, methodology)
The DBA had the concepts (bloat, unused indexes, slow queries) as gotchas but no catalog of WHICH query answers WHICH question. This is that catalog. postgres_dba ships 34 psql reports; the operationally important ones and when to reach for each:

- **"Where is time going?"** -> slowest queries by total time + workload-by-query-type (needs `pg_stat_statements` in `shared_preload_libraries`). Start every slow-DB investigation here, not with a single suspect query.
- **"Is an index missing?"** -> FKs with missing indexes; this is the #1 silent slow-write/slow-delete cause and matches the existing red flag "Missing indexes on foreign keys."
- **"Are indexes wasting writes?"** -> unused / rarely-used indexes + redundant indexes + invalid indexes. Drop unused/redundant (they tax every write) - matches the "audit unused indexes quarterly" gotcha. Generate the cleanup DDL (with an UNDO script) before dropping.
- **"Is the table bloated?"** -> table bloat + b-tree bloat estimation (fast estimate first; `pgstattuple` exact only when the estimate is alarming - it is expensive). Bloat -> schedule pg_repack / pg_squeeze, never VACUUM FULL on a live table.
- **"Why are queries blocking?"** -> lock trees (PG14+ shows wait times). Read top-down: the root holder is the one to kill or wait out.
- **"Is vacuum keeping up?"** -> vacuum current activity + autovacuum progress/queue. A growing queue on hot tables = tune per-table autovacuum (matches the standing gotcha).
- **"Is the data corrupt?"** -> amcheck quick index check (AccessShareLock, prod-safe) first; the heavier parent/heapallindexed checks (ShareLock) only on a clone. Run after a glibc/collation upgrade.

Host install (read-only diagnostics, no daemon): `git clone`, add `\set dba` to `~/.psqlrc`, connect via psql 10+, type `:dba`. Works with the `pg_monitor` role - superuser only needed for the corruption checks. Posture: diagnostics are read-only; any DDL the reports generate (index drops) goes through the migration framework + change control, never hand-run on prod.

## 2. MySQL online schema change (gh-ost - MIT, methodology)
The MySQL zero-downtime lane. SKILL.md named gh-ost; this is how to run it. gh-ost is triggerless: it tails the binlog (Row-Based Replication required) into a ghost table, then does a brief cut-over metadata lock. Lower master load + true pause vs trigger-based pt-online-schema-change.

Operational flow (always in this order):
1. **noop** - validate the migration is well-formed, do nothing else.
2. **--test-on-replica** - run the full flow on a replica without swapping; checksum the result to build trust. GitHub does this continuously across its fleet.
3. **--execute** - the real migration on the master (gh-ost prefers running through a replica to discover topology).

Operational flags that matter:
- `--exact-rowcount` for accurate progress/ETA.
- `--postpone-cut-over-flag-file` - hold the cut-over until office hours / low traffic, then remove the file to trigger the swap. This is the key control for "never cut over blind."
- Interactive socket (unix/TCP) - reconfigure throttling, force-throttle, or query status mid-run.
- Throttle = true pause: it ceases row-copy AND event processing, returning the master to its native workload.

Decision rule: gh-ost when the table is large + on MySQL with RBR and you want decoupled, pausable, testable DDL. pt-online-schema-change (trigger-based, synchronous) when RBR/binlog access is unavailable. Either way this is the MySQL counterpart to pg_repack on the Postgres side. On RDS/Aurora MySQL and Azure MySQL there are documented modes - check the topology-discovery limitations first.

## 3. Postgres backup + PITR + restore-test (pgBackRest - MIT, methodology)
Operationalizes the bare "PITR" bullet and the "untested backup = no backup" hard rule. pgBackRest is the canonical Postgres backup tool.

The backup/restore operational loop:
- **Strategy:** full + differential + incremental (block-level where supported - copies only changed parts). Set retention per full + per diff so any required recovery window is covered. WAL archive retained for the backups it makes consistent.
- **PITR mechanics:** continuous WAL archiving via `archive-push` (async + parallel for high write volume); recovery replays from a base backup + WAL up to a target time/LSN/named restore point. `archive-get` keeps a local decompressed WAL queue to maximize replay speed (matters most on S3-backed repos).
- **Multi-repo:** a local repo with short retention for fast restores + a remote/object-store repo (S3/Azure/GCS) with long retention for DR. This satisfies "cross-region replication for DR."
- **Integrity:** per-file checksums rechecked on restore/verify; page-checksum validation during backup catches corruption early (warns, does not abort). Run `verify` on the repo on a schedule.
- **Delta restore:** on restore, checksums let pgBackRest skip files that already match - dramatically faster re-restores onto an existing cluster (use for the quarterly restore test).
- **Encryption:** encrypt the repo at rest; aligns with the PII-encryption hard rule.

Restore-test discipline (the part most shops skip): quarterly, do a real `restore` (delta restore to a scratch host is cheapest) + bring Postgres up + run a sanity query. A backup chain that has never been restored is not a backup.

Host install: pgBackRest on the PG host + repo host; TLS/SSH between them so the repo host never needs direct PG access. FLAG: the main repo was archived 2026-04-27 (Crunchy sale) and revived 2026-05-18 under a Supabase-led sponsor coalition - it is active again but re-confirm sponsorship health before standardizing on it for a new client; Barman is the fallback if governance regresses.

## 4. Self-managed Postgres HA (Patroni - MIT, methodology + CONNECT)
Operationalizes the bare "Automatic failover (Patroni...)" + "split-brain mitigation" bullets. Use ONLY when the client is NOT on a managed HA flavor (RDS Multi-AZ / Cloud SQL HA / Aurora already give you this - prefer them per the "vertical/managed first" doctrine). Patroni is for self-hosted Postgres that needs automatic failover.

Doctrine + decision rules:
- **A DCS is mandatory.** Patroni stores cluster state + does leader election in a distributed consensus store: etcd (default recommendation), Consul, ZooKeeper, or the Kubernetes API. The DCS - not Postgres - guarantees a single leader, which is how split-brain is avoided. No DCS quorum = no failover; size the DCS for quorum (3 or 5 nodes across failure domains).
- **Switchover vs failover:** switchover is planned (you pick the moment, zero data loss); failover is automatic on primary loss. Both go through the DCS lock. Schedule maintenance as a switchover, never a hard kill.
- **Sync vs async with failover:** async replication means a failover can lose the last unreplicated transactions (matches the "async has lag - plan for it" rule). For zero-RPO requirements, run synchronous_mode so Patroni only promotes a replica that is caught up; accept the write-latency cost. Document the RPO/RTO target up front.
- **Fencing:** ensure the demoted/old primary cannot accept writes after a failover (watchdog / `nofailover` tags / DCS TTL expiry). An un-fenced old primary is the classic split-brain.
- **Connection routing:** clients reach the current leader via HAProxy + Patroni's REST health endpoint (or a K8s service). The app never hardcodes a node - this composes with the existing "always pool, never direct-to-prod" rule (PgBouncer in front of the HAProxy-routed leader).

CONNECT/host-install note: Patroni is a host-installed Python daemon per node + a DCS cluster; not bundled. Activate per-engagement for self-managed Postgres HA. On Kubernetes, the Zalando postgres-operator or CloudNativePG wrap Patroni-style failover - prefer an operator over hand-rolling on K8s.

## 5. Ecosystem index (awesome-postgres - NOASSERTION, cite-only)
For any Postgres tool need not yet covered here, consult dhamaniasad/awesome-postgres (https://github.com/dhamaniasad/awesome-postgres) as a curated lookup index across backup / replication / HA / monitoring / extensions / pooling / GUIs. FLAG: NOASSERTION license - use as a pointer index only, never copy entries verbatim into employee files.

---

## Cross-references
- Diagnostic index/bloat findings feed the existing rules.md indexing + autovacuum gotchas.
- gh-ost is the MySQL twin of pg_repack (Postgres) named in SKILL.md.
- pgBackRest realizes the SKILL.md "PITR" + "cross-region replication for DR" + the "untested backup = no backup" hard rule.
- Patroni realizes the SKILL.md "Automatic failover" + "split-brain mitigation" bullets for the self-hosted case; defer to managed HA when available.
- NoSQL operational admin lives in references/mongodb-nosql-admin.md; this file is the SQL operational twin.
