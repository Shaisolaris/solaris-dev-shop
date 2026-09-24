# k6 load-test patterns (grafana/mcp-k6)

Absorbed from grafana/mcp-k6 (AGPL-3.0, official Grafana, v0.2.0 @ 2026-06-13). Net-new for performance-engineer: concrete k6 SCRIPTING + execution discipline. The employee already had the load-test STRATEGY (ramp/spike/stress/soak, p50/p95/p99, 1.5x peak, baseline-first); this adds how the scripts are actually written, gated, and run via the MCP.

## MCP tools (the execution loop)
- `validate_script` - dry-run a script at 1 VU / 1 iteration, returns actionable errors. ALWAYS validate before a full run - catch a broken script in seconds, not after a 12h soak.
- `run_script` - execute locally with configurable VUs, duration, stages, options; extracts metrics. The workhorse.
- `list_sections` / `get_documentation` - pull official k6 docs in-context (ground the script in real k6 API, don't recall it).
- `generate_script` - generate a production-ready k6 script from plain-English requirements, following best practices; treat as a starting draft to review, not final.

## Script anatomy + the patterns that matter
- **Executors / load profiles** (map to the existing strategy):
  - `ramping-vus` with `stages` - the ramp 0→peak→down (e.g. stages: [{duration:'2m',target:100},{duration:'5m',target:100},{duration:'2m',target:0}]).
  - `constant-vus` - steady-state.
  - `ramping-arrival-rate` / `constant-arrival-rate` - OPEN model: pin REQUEST RATE (RPS) independent of response time. Use this for capacity tests - closed (VU) models hide throughput collapse because slow responses throttle the load generator itself.
  - `shared-iterations` / `per-vu-iterations` - fixed-work batch tests.
  - Spike = a stage that jumps target steeply; stress-to-failure = stages that keep climbing until thresholds break; soak = long steady-state (12h+) to surface leaks/GC drift.
- **thresholds** = the pass/fail gate (the most important net-new piece). Encode SLOs as machine-checked thresholds so the test EXITS NON-ZERO on breach (CI gate, not eyeballing):
  - `http_req_duration: ['p(95)<500','p(99)<1000']`
  - `http_req_failed: ['rate<0.01']`
  - custom-metric thresholds for business transactions.
- **checks** = per-response assertions (status 200, body contains X). Checks measure correctness-under-load; a high check-failure rate at load is a finding even if latency looks fine.
- **tags / groups** - tag requests by endpoint/journey so percentiles are per-transaction, not blended (blended p99 hides one slow endpoint).

## Doctrine (preserve the employee's existing rigor)
- Validate (1 VU) → baseline run → ramp to 1.5x expected peak → read p50/p95/p99 + error rate + checks, per-tag → bottleneck analysis. Never skip the baseline.
- Run against staging with prod-size data and prod-like topology (existing red flag: never load-test prod; dev-only results don't transfer).
- Thresholds encode the SLO so the run is self-judging; failures hand off to the owning employee (DB → DBA, infra → SRE/cloud-architect) - perf-engineer finds and proves the bottleneck, others fix their layer.

## License (AGPL-3.0 - copyleft, self-host-ok)
mcp-k6 is AGPL-3.0. Self-hosting and running it as a tool is fine. The copyleft obligation triggers on DISTRIBUTING a modified version (incl. over a network service) - do NOT vendor modified mcp-k6 source into a closed Solaris/client product or expose a modified instance as a network service without honoring AGPL. Running unmodified to drive tests carries no distribution obligation. k6 itself is AGPL-3.0 too - same posture.

## Install (host)
Homebrew `brew install mcp-k6` (pulls k6), Linux `.deb`/`.rpm` from releases, or native (Go 1.24.4+, k6 in PATH). xk6 can embed it as a `k6 x mcp` subcommand for a single binary. Cross-ref: qa-engineer CONNECTs mcp-k6 to RUN pre-launch load tests; performance-engineer OWNS these patterns and the analysis.
