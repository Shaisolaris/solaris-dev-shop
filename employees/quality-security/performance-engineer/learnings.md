# Performance Engineer - Learnings (Pending)

## Pending observations
- **2026-05-18 - Clean build**: "Measure before optimizing" is the universal rule. Codified as first core principle (rules.md).
- **2026-06-04 - v0.4.0**: The performance-profiler skill ABSORBED (static scanner + before/after template + quick-wins checklist) folded into rules.md.
- **2026-06-13 - v0.5.0**: grafana/mcp-k6 load-test patterns absorbed -> references/k6-load-test-patterns.md (AGPL self-host note); prometheus-mcp CONNECT (PromQL lives in SRE).
- **2026-06-13 - v0.6.0 deepen pass**: five lanes the employee named but never operationalized got methodology (references/perf-observability-patterns.md): Locust (Python load lane), Pyroscope (continuous prod profiling, AGPL), OTel Collector (vendor-neutral telemetry), Unlighthouse (site-wide CWV + CI budget), pgBadger (Postgres slow-log). Observation: every load/CWV gate should be a non-zero-exit CI step, SHA-pinned per fleet doctrine - promoted into rules.md "Perf CI gates".
- **2026-06-13**: Observation - a single quick measurement is legitimate for prototypes; full audit rigor should not block a "is this obviously slow?" question. Promoted into rules.md "Small-task / prototype lane".

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| 2026-05-18 | Measure before optimizing (cardinal rule) | rules.md Core principles |
| 2026-06-04 | Profile -> confirm -> fix -> re-measure -> verify; before/after PR template | rules.md Performance Profiler absorption |
| 2026-06-13 | k6 thresholds as machine-checked SLO gate (non-zero exit) | rules.md Load-test execution + references/k6-load-test-patterns.md |
| 2026-06-13 | Perf CI gates must be SHA-pinned Actions | rules.md Perf CI gates |
| 2026-06-13 | Small-task / prototype light lane (flag quick reads) | rules.md Small-task / prototype lane |
## 2026-07-24 platform-reliability wave (skill-edl)
- Contract `1.1.0`: plan-dryrun-rollback step; provenance_ledger + partial_or_blocked_note + bounded_plan outputs.
- RUNTIME HARDENING: mutation authority only after plan, dry-run evidence, failure notes, cost/security, and rollback.
- Provider adapters retain default_deny + require_human for deploy/spend/mutate_external.
- Evaluation packet: meta/skill-rotation/evaluations/20260724/platform-reliability/.
## Sources

- Upstream: locustio/locust (license not stated: 27.8k); grafana/pyroscope (license not stated: ~10k (7.2k @ 2023 acquisition, grew since; 2.0 GA)); open-telemetry/opentelemetry-collector (license not stated: ~5k core (+4.6k contrib)); harlan-zw/unlighthouse (license not stated: 4.5k); darold/pgbadger (license not stated: ~4k)
- What was used: methodology only: locustio/locust, grafana/pyroscope, harlan-zw/unlighthouse, darold/pgbadger; noted: open-telemetry/opentelemetry-collector
- License notes: licenses not recorded in scan for: locustio/locust, grafana/pyroscope, open-telemetry/opentelemetry-collector, harlan-zw/unlighthouse, darold/pgbadger - verify before reuse; no code vendored
