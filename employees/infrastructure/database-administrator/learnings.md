# Database Administrator - Learnings (Pending)

## Pending observations
- **2026-04-24 - Clean build**: "Access patterns first" is the single most-violated DB rule. Codified as core principle + decision rule.
- **2026-04-24 - Clean build**: PostgreSQL default vs deviation-needs-justification pattern unified across all 9 sources.

## Pending observations (cont.)
- **2026-06-13 - depth pass**: Concepts-without-procedure was the dominant gap. SKILL.md named gh-ost / Patroni / PITR as bare tokens with no runnable flow. Absorbed the operational loops (postgres_dba diagnostics, gh-ost online-DDL flow, pgBackRest PITR + restore-test, Patroni DCS/split-brain) into references/sql-ops-tuning-ha-backup.md and added slow-query + restore-test gates.
- **2026-06-13 - depth pass**: Two duplicate "Standing gotchas" sections in rules.md were merged; references/mongodb-nosql-admin.md was a phantom ref (file existed, never registered in plugin.json references) - now registered.

- **2026-10-18 - G03 recovery**: A rejected local recovery candidate showed four failure shapes: journal recovery ran before the lock, dry-run and backup checks; a crash between swap renames left the target absent and deleted the verified stage; unfiltered archive extraction followed a link outside; a row-count heuristic authorized losing newer rows. The replacement uses plain snapshot directories (no archives), explicit `--confirm <snapshot_id>`, value digests, an flock on every write path, and a recover step that models the renames from the files present.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| 2026-06-13 | Slow-query gate (5-step) | SKILL.md Standard procedures + rules.md |
| 2026-06-13 | Restore-test gate (5-step) | SKILL.md Standard procedures + rules.md |
| 2026-06-13 | Small-task / prototype lane | SKILL.md + rules.md |
| 2026-06-13 | SQL operational layer (diagnostics/DDL/backup/HA) | references/sql-ops-tuning-ha-backup.md |
| 2026-10-18 | Local SQLite recovery lane (restore-test gate step 6) | SKILL.md + sqlite-recovery.md + sqlite_recovery.py |
| 2026-10-18 | SQLite recovery r2: escape `_` in internal-table LIKE, compare user_version/application_id, WAL on Apple SQLite, exact health | sqlite-recovery.md + sqlite_recovery.py |
| 2026-10-18 | SQLite recovery r3: never open databases (or use the sidecar-creating fallback) while a restore journal exists; snapshot makes its folder only under the lock; test a lock with a second real run, not only an external flock | sqlite-recovery.md + sqlite_recovery.py |
## 2026-07-24 platform-reliability wave (skill-edl)
- Contract `1.1.0`: plan-dryrun-rollback step; provenance_ledger + partial_or_blocked_note + bounded_plan outputs.
- RUNTIME HARDENING: mutation authority only after plan, dry-run evidence, failure notes, cost/security, and rollback.
- Provider adapters retain default_deny + require_human for deploy/spend/mutate_external.
- Evaluation packet: meta/skill-rotation/evaluations/20260724/platform-reliability/.
## Sources

- Upstream: NikolayS/postgres_dba (BSD-3-Clause (permissive, safe)); github/gh-ost (MIT (permissive, safe)); pgbackrest/pgbackrest (MIT (permissive, safe)); patroni/patroni (MIT (permissive, safe)); dhamaniasad/awesome-postgres (NOASSERTION (FLAG - awesome-list, typically CC-style but no SPDX-detectable license file)
- What was used: methodology absorbed: NikolayS/postgres_dba, github/gh-ost, pgbackrest/pgbackrest; methodology only: patroni/patroni, dhamaniasad/awesome-postgres; connected as external reference: patroni/patroni, dhamaniasad/awesome-postgres
- License notes: dhamaniasad/awesome-postgres: NOASSERTION (FLAG - awesome-list, typically CC-style but no SPDX-detectable license file
