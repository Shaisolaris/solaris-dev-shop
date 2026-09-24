# Top-5 Verified 2026 Sources - Database Administrator

Scout date: 2026-06-13. All facts verified by direct GitHub fetch on 2026-06-13.
Scope: Postgres/MySQL tuning, indexing, replication/HA, backups, migrations, monitoring.
Gate-0 = grep employee's ACTUAL content (SKILL.md / rules.md / references/) for the concept, decide present / content-duplicate / net-new.

---

## 1. NikolayS/postgres_dba - ABSORB (methodology)
- URL: https://github.com/NikolayS/postgres_dba
- Stars: 1.3k | Forks: 144
- License: BSD-3-Clause (permissive, safe)
- Last commit / release: Release 7.0, 2026-02-10 (444 commits, CI green on PG 13-18)
- Maintainer: Nikolay Samokhvalov (postgres.ai founder; well-known Postgres authority)
- What it adds: 34 ready-to-run psql diagnostic reports - bloat estimation (table + b-tree), unused/redundant/invalid indexes, FKs missing indexes, lock trees, vacuum/autovacuum progress, pg_stat_statements slow-query reports, buffer-cache, amcheck corruption checks. The "which query do I run to find X" operational catalog the DBA lacked.
- Gate-0: `pg_stat_statements` named in SKILL.md extensions list; `bloat` only as an autovacuum gotcha. NO diagnostic-query catalog, NO unused/redundant-index report, NO lock-tree query, NO slow-query ranking loop. Net-new OPERATIONAL diagnostics. Not a content-duplicate.
- Tag: ABSORB (methodology - the diagnostic-report catalog + when-to-run mapping; queries themselves are BSD so could be bundled, but per fleet doctrine we absorb the methodology + cite the source rather than vendor SQL).

## 2. github/gh-ost - ABSORB (methodology)
- URL: https://github.com/github/gh-ost
- Stars: 13.4k | Forks: 1.4k
- License: MIT (permissive, safe)
- Last release: GA v1.1.10, 2026-06-04 (1,788 commits; maintained by GitHub DB-infra team)
- Maintainer: GitHub, Inc. (database infrastructure team)
- What it adds: triggerless online MySQL schema migration via binlog stream. Operational methodology: noop -> test-on-replica -> --execute, true throttle/pause, postpone-cut-over flag file, --exact-rowcount, interactive reconfiguration, RBR requirement, cut-over metadata-lock semantics. Turns the bare "gh-ost" name in SKILL.md into a runnable procedure.
- Gate-0: `gh-ost` appears once in SKILL.md as a bare tool name in a list ("pg_repack, pt-online-schema-change, gh-ost"). NO usage flow, NO flags, NO test-on-replica discipline, NO cut-over control. Net-new operational. Not a content-duplicate.
- Tag: ABSORB (methodology - the online-DDL workflow + flag cheatsheet for the MySQL zero-downtime lane).

## 3. pgbackrest/pgbackrest - ABSORB (methodology)
- URL: https://github.com/pgbackrest/pgbackrest
- Stars: 3.7k | Forks: 259
- License: MIT (permissive, safe)
- Last release: v2.58.0, 2026-01-19 (4,796 commits; now sponsored by Supabase)
- Maintainer: David Steele / pgBackRest org. NOTE/FLAG: main repo was briefly archived 2026-04-27 after the Crunchy Data sale; a sponsor coalition (Supabase) revived it 2026-05-18. Currently active - confirm sponsorship health at next scout.
- What it adds: the canonical Postgres backup/restore operational layer - full/diff/incremental + block-level, PITR via WAL archive (push/get async + parallel), delta restore, multi-repo retention, S3/Azure/GCS object store, encrypted repos, page-checksum validation during backup, backup-resume. Operationalizes the bare "PITR" bullet + "tested restore" rule.
- Gate-0: `PITR` named in SKILL.md + listed as a red flag in rules.md ("No PITR on production DB"); "quarterly restore tests" is a rule. NO tool, NO WAL-archive workflow, NO delta-restore, NO retention-policy mechanics, NO restore-verification command loop. Net-new operational. Not a content-duplicate.
- Tag: ABSORB (methodology - the Postgres backup/PITR/restore-test operational loop; aligns with the existing "untested backup = no backup" hard rule).

## 4. patroni/patroni - CONNECT/METHODOLOGY
- URL: https://github.com/patroni/patroni
- Stars: 8.5k | Forks: 1k
- License: MIT (permissive, safe)
- Last release: v4.1.3, 2026-05-05
- Maintainer: Patroni org (originated at Zalando; used by GitLab, Zalando, etc.)
- What it adds: Postgres HA template - automatic leader election + failover via a DCS (etcd / Consul / ZooKeeper / Kubernetes), planned switchover, split-brain avoidance (single-leader guarantee through the DCS), bootstrap, synchronous-mode config. Operationalizes the bare "Patroni" name + "split-brain mitigation" bullet.
- Gate-0: `Patroni` named once in SKILL.md ("Automatic failover (Patroni, RDS multi-AZ, Cloud SQL HA)"); "split-brain mitigation" is a bare bullet. NO DCS choice rule, NO sync-vs-async-with-failover config, NO switchover-vs-failover distinction, NO fencing. Net-new operational. Not a content-duplicate.
- Tag: METHODOLOGY (absorb the self-managed-HA decision rules + DCS/split-brain doctrine; the daemon itself is host-installed per-engagement, so also a CONNECT note - not bundled).

## 5. dhamaniasad/awesome-postgres - METHODOLOGY (CONNECT/index)
- URL: https://github.com/dhamaniasad/awesome-postgres
- Stars: 10k+ (curated-list class; widely forked, the canonical Postgres awesome-list)
- License: NOASSERTION (FLAG - awesome-list, typically CC-style but no SPDX-detectable license file; treat as reference-only, do NOT vendor text)
- Last commit: actively maintained (community PRs ongoing 2026)
- Maintainer: Asad Dhamani + community
- What it adds: a curated index of the Postgres tool ecosystem (backup, replication, HA, monitoring, extensions, GUIs, pooling) - useful as a per-engagement lookup when a client's stack needs a tool the employee has not yet absorbed.
- Gate-0: no equivalent ecosystem index in the employee. Net-new, but it is a pointer list, not a technique. Not a content-duplicate.
- Tag: METHODOLOGY / CONNECT note only (FLAG NOASSERTION - cite as a lookup index, never copy entries; lowest-priority of the five).

---

## Verdict summary
| # | Source | Stars | License | Last commit | Gate-0 | Tag |
|---|--------|-------|---------|-------------|--------|-----|
| 1 | NikolayS/postgres_dba | 1.3k | BSD-3-Clause | 2026-02-10 | net-new diagnostics | ABSORB |
| 2 | github/gh-ost | 13.4k | MIT | 2026-06-04 | net-new MySQL online-DDL flow | ABSORB |
| 3 | pgbackrest/pgbackrest | 3.7k | MIT (FLAG: archive scare Apr-May 2026, revived) | 2026-01-19 | net-new backup/PITR loop | ABSORB |
| 4 | patroni/patroni | 8.5k | MIT | 2026-05-05 | net-new self-managed HA | METHODOLOGY + CONNECT |
| 5 | dhamaniasad/awesome-postgres | 10k+ | NOASSERTION (FLAG) | active 2026 | net-new index | METHODOLOGY (cite-only) |

All five: established, >=1.3k stars, commit within ~6mo of 2026-06-13, no GPL/AGPL. Flags: pgBackRest archive-then-revived governance risk; awesome-postgres NOASSERTION (cite-only, no text vendored).
