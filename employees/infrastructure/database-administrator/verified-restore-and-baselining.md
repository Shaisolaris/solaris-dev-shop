# Verified-restore discipline + longitudinal baselining

Methodology adapted from two verified sources (patterns only; no third-party code is
bundled and Claude does not run these tools):
- **Databasus** (Apache-2.0, ~7.4k stars) - restore-VERIFICATION discipline:
  test-restore into a throwaway container with a per-table row-count correctness report,
  GFS retention, PITR orchestration. README/docs read 2026-06-15.
- **pgwatch** (BSD-3-Clause, by Cybertec) - continuous-baseline-then-tune monitoring:
  collect metrics over time, establish a baseline, tune against the trend rather than a
  point-in-time snapshot.

This extends sql-ops-tuning-ha-backup.md, which already has a pgBackRest backup/PITR loop
with a quarterly restore-TEST and a postgres_dba point-in-time diagnostic catalog. The
net-new here is (1) restore VERIFICATION as a scheduled, automated, correctness-checked
loop, and (2) LONGITUDINAL baselining as the precondition for tuning.

## Gate-0: what is net-new vs the existing file

Existing coverage: pgBackRest full/diff/incremental, WAL archiving + PITR, multi-repo,
per-file checksums + scheduled `verify`, and a quarterly "real restore to a scratch host
+ bring PG up + run a sanity query" discipline; plus postgres_dba SNAPSHOT diagnostics.
NOT previously covered:
- Restore verification as a SCHEDULED, AUTOMATED loop into a THROWAWAY CONTAINER with a
  CORRECTNESS report (per-table row counts, schema/table counts, restored size, restore
  exit code) - the existing test is a manual quarterly smoke query, not an automated
  correctness comparison.
- The explicit argument for why checksums + exit codes are insufficient.
- GFS (grandfather-father-son) named retention tiers.
- Continuous longitudinal baselining (collect-over-time, baseline, tune-against-trend) -
  the existing diagnostics are all point-in-time.

## 1. Verified-restore discipline (Databasus methodology)

Core doctrine, sharpening the existing "untested backup = no backup" hard rule: a backup
that finishes without error is NOT a backup you can restore. The only proof is to restore
it AND check the result is correct.

### Why checksums + exit codes are not enough
- A **checksum** catches bit-rot on the archive file but says nothing about whether the
  dump is complete or semantically valid.
- A **dump exit code** says the dump command ran; it does NOT catch a backup role missing
  read permission on some objects, a missing extension on the source, or a tablespace
  mismatch - any of which silently SKIPS or STRIPS objects from the dump. The backup
  looks green and is partial.
- **Restore verification** runs the archive through the database's native restore tool and
  counts rows per table. It is the only check that catches all of the above - you find out
  before a disaster, not during one.

### The verification loop (scheduled, automated)
1. **Pull the latest backup.**
2. **Restore into a throwaway database container** of the matching major version
   (Docker-spun, ephemeral, isolated from production - never restore-test onto anything
   live). Size the host for backup-file-size + raw-DB-size + a safety gap.
3. **Sanity-check restored vs source** and capture a CORRECTNESS report, not just "it
   came up": restore exit code, restored DB size, schema count, table count, and a
   **per-table row-count breakdown**. A row-count delta against the source is the signal
   that objects were silently dropped.
4. **Tear the container down** (clean slate every run).
5. **Report the outcome** - success/failure to the team's notifier; most shops alert on
   FAILURE only to avoid fatigue.

### Cadence
- **After-backup** is the strongest guarantee: verify every successful backup the moment
  it finishes. If verifications fall behind backups, cancel the stale pending verification
  when a fresh backup arrives - only the most recent backup waits in line (never restore-
  verify a backup you would never actually restore from).
- Or hourly/daily/weekly/monthly/cron for lower-cost cadences.
- Keep at least the existing quarterly FULL DR rehearsal too - automated row-count
  verification proves restorability continuously; the quarterly drill still rehearses the
  human runbook + RTO. Both, not either.

### GFS retention (grandfather-father-son)
Keep hourly, daily, weekly, monthly, and yearly backups as INDEPENDENT tiers so
fine-grained recent history and long-term history both exist without keeping everything:
- recent: dense (hourly/daily) for fast, low-RPO recovery,
- mid: weekly/monthly for the common "restore last month" ask,
- long: yearly for compliance/retention windows.
Backups outside every tier's policy are pruned automatically. This is a sharper retention
model than the existing "retention per full + per diff" - map the client's RPO + legal
retention onto explicit GFS tiers and document which tier satisfies which requirement.

### PITR orchestration
PITR via incremental/WAL so recovery can target any second between backups (restore base
+ replay to a target time/LSN). This corroborates the existing pgBackRest PITR mechanics;
the addition is treating PITR as an ORCHESTRATED, verified capability - the restore-
verification loop should periodically prove a PITR target restore, not only a
latest-full restore, so the WAL chain itself is proven replayable.

### Deployment posture (host-installed, two modes)
- **Remote/logical mode** - connect over the network, logical backups, no agent; fits
  cloud-managed DBs (RDS/Aurora/Cloud SQL/Supabase) where you cannot run an agent.
- **Agent mode** - lightweight agent beside the DB, physical backups + continuous WAL
  archiving + PITR.
The verification AGENT is a separate small binary on a host you control with Docker, spare
CPU/RAM/disk, and outbound HTTPS. It is host-installed/operated per engagement, never
bundled here, and runs against a scratch host, never production. Supports PostgreSQL,
MySQL, MariaDB, MongoDB (Postgres-first).

## 2. Continuous baseline-then-tune (pgwatch methodology)

Doctrine: you cannot tune what you have not baselined. The existing postgres_dba reports
answer "what is wrong RIGHT NOW"; pgwatch answers "what is NORMAL for this database, and
what is drifting." Tune against the trend, not a single bad moment.

### The baseline-then-tune loop
1. **Collect continuously.** Gather PG-specific metrics over time (throughput/TPS,
   latency, cache hit ratio, connection counts, lock waits, replication lag, table/index
   bloat growth, autovacuum activity, WAL volume, top queries via pg_stat_statements)
   into a time-series store, visualized on dashboards (Grafana-style).
2. **Establish the baseline.** Let it run long enough to capture the real daily/weekly
   workload shape (peak hours, batch windows, end-of-month spikes). The baseline is the
   band of "normal," not a single number.
3. **Tune against the trend.** When investigating, compare current behavior to the
   baseline: is this latency abnormal for this hour, or is this just Monday 9am? Is bloat
   GROWING or stable? Did cache-hit ratio step down after a deploy? Trend deltas localize
   the cause far better than an isolated snapshot.
4. **Validate the change with the same series.** After a tuning change (index, autovacuum
   setting, config), watch the SAME longitudinal metric to confirm the trend actually
   improved and held - not just that one query got faster once.

### How it composes with existing diagnostics
- pgwatch = the longitudinal layer (what is normal / what is drifting over days-weeks).
- postgres_dba = the point-in-time deep-dive (which query/index/lock is the problem right
  now). Use pgwatch to NOTICE drift and pick the moment, then drop into postgres_dba for
  the specific culprit. They are complementary, not redundant.
- Feeds the SRE relationship: longitudinal DB baselines are the SLI inputs the SRE's
  golden-signal/burn-rate alerting reasons over (cross-reference the SRE's
  promql-patterns.md).

### Host-install posture
pgwatch is a host-installed monitoring stack (agent + config/metrics DB + Grafana,
Docker-deployable; needs `pg_stat_statements` and a `pg_monitor`-role connection on each
monitored DB). CONNECT per engagement; not bundled. Read-only monitoring - it observes,
it never tunes; the DBA reads the trend and proposes the change through change control.

## Cross-references
- Sharpens the "untested backup = no backup" hard rule and the pgBackRest PITR/verify
  section in sql-ops-tuning-ha-backup.md with automated correctness verification + GFS.
- Longitudinal baselining feeds the postgres_dba snapshot diagnostics (notice drift here,
  diagnose the culprit there) and the SRE's SLI/alerting inputs.
- Prefer managed-HA/managed-backup where available (vertical/managed-first doctrine);
  these methodologies apply most to self-managed or cloud-managed-without-native-DR cases.

---
Sources: Databasus (Apache-2.0, ~7.4k stars; databasus.com restore-verification docs read
2026-06-15) - verified-restore-into-throwaway-container + per-table row-count report, GFS
retention, PITR orchestration, why-checksums-miss argument, remote/agent modes. pgwatch
(BSD-3-Clause, Cybertec; README read 2026-06-15) - continuous-baseline-then-tune,
PG-specific time-series metrics + Grafana, pg_stat_statements/pg_monitor. Methodology
absorbed; no code bundled or run; both host-installed/read-only per engagement.
No em-dashes.
