# Database Administrator - Learnings (Pending)

## Pending observations
- **2026-04-24 - Clean build**: "Access patterns first" is the single most-violated DB rule. Codified as core principle + decision rule.
- **2026-04-24 - Clean build**: PostgreSQL default vs deviation-needs-justification pattern unified across all 9 sources.

## Pending observations (cont.)
- **2026-06-13 - depth pass**: Concepts-without-procedure was the dominant gap. SKILL.md named gh-ost / Patroni / PITR as bare tokens with no runnable flow. Absorbed the operational loops (postgres_dba diagnostics, gh-ost online-DDL flow, pgBackRest PITR + restore-test, Patroni DCS/split-brain) into references/sql-ops-tuning-ha-backup.md and added slow-query + restore-test gates.
- **2026-06-13 - depth pass**: Two duplicate "Standing gotchas" sections in rules.md were merged; references/mongodb-nosql-admin.md was a phantom ref (file existed, never registered in plugin.json references) - now registered.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| 2026-06-13 | Slow-query gate (5-step) | SKILL.md Standard procedures + rules.md |
| 2026-06-13 | Restore-test gate (5-step) | SKILL.md Standard procedures + rules.md |
| 2026-06-13 | Small-task / prototype lane | SKILL.md + rules.md |
| 2026-06-13 | SQL operational layer (diagnostics/DDL/backup/HA) | references/sql-ops-tuning-ha-backup.md |
## 2026-07-24 platform-reliability wave (skill-edl)
- Contract `1.1.0`: plan-dryrun-rollback step; provenance_ledger + partial_or_blocked_note + bounded_plan outputs.
- RUNTIME HARDENING: mutation authority only after plan, dry-run evidence, failure notes, cost/security, and rollback.
- Provider adapters retain default_deny + require_human for deploy/spend/mutate_external.
- Evaluation packet: meta/skill-rotation/evaluations/20260724/platform-reliability/.
