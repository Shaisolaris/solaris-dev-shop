# Site Reliability Engineer - Learnings (Pending)

## Pending observations
- **2026-04-24 - Clean build**: Google SRE workbook multi-burn-rate alerting pattern is industry-standard now; codified in alert-design reference.
- **2026-04-24 - Clean build**: "100% reliability is wrong target" - counter-intuitive but defensible core principle. Error budget lets teams ship.
- **2026-06-13 - Depth pass (v0.6.0)**: chaos engineering re-grounded from a real source (chaos-mesh) after v0.4.0 dropped the unsourced claim - the discipline (hypothesis/steady-state/blast-radius/abort) is what's defensible, the K8s tool is optional and agency clients usually need the manual game-day drill instead.
- **2026-06-13 - Depth pass (v0.6.0)**: SLO-as-code (Sloth) is the missing link between "SLO in a doc" (a red flag we already name) and committed alerting rules - the burn-rate thresholds we preach are exactly what it generates, so it operationalizes existing doctrine rather than adding new.
- **2026-06-13 - Source-quality lesson**: dastergon/awesome-sre + awesome-chaos-engineering have huge stars (13k/6.6k) but are ~3.7 years stale; star count alone fails the recency gate. Verified via commits .atom feed + shields.io when the GitHub REST API was rate-limited.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
## 2026-07-24 platform-reliability wave (skill-edl)
- Contract `1.1.0`: plan-dryrun-rollback step; provenance_ledger + partial_or_blocked_note + bounded_plan outputs.
- RUNTIME HARDENING: mutation authority only after plan, dry-run evidence, failure notes, cost/security, and rollback.
- Provider adapters retain default_deny + require_human for deploy/spend/mutate_external.
- Evaluation packet: meta/skill-rotation/evaluations/20260724/platform-reliability/.
## Sources

- Upstream: chaos-mesh/chaos-mesh (Apache-2.0); slok/sloth (Apache-2.0); open-telemetry/opentelemetry-demo (Apache-2.0); grafana/docker-otel-lgtm (Apache-2.0); meirwah/awesome-incident-response (Apache-2.0)
- What was used: methodology absorbed: chaos-mesh/chaos-mesh, slok/sloth; methodology only: open-telemetry/opentelemetry-demo; connected as external reference: open-telemetry/opentelemetry-demo, grafana/docker-otel-lgtm, meirwah/awesome-incident-response
- License notes: absorbed sources permissive (MIT/Apache-2.0); no code vendored
