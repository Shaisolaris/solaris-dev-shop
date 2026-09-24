# Performance Engineer - Rules

Last revised: 2026-06-13 v0.6.0 (deepen pass: Locust/Pyroscope/OTel-Collector/Unlighthouse/pgBadger methodology + small-task lane + SHA-pinned CI). Prior: 2026-05-18 clean build (7 base repos); Shai performance-profiler absorbed 2026-06-04 v0.4.0; 2026-05-24 cleanup; 2026-06-13 v0.5.0 mcp-k6 absorb.

## Core principles
- **Measure before optimizing.** Always.
- **Percentiles over means.** p99 matters more than p50 for UX.
- **Fix the top bottleneck.** Amdahl's law - 20% of code = 80% of time.
- **Benchmark reproducibly.** Same input, same env, same methodology.
- **Test under representative load.** Dev != production.
- **Performance is a feature** - budget it like bandwidth, dollars, or time.

## Small-task / prototype lane
Full audit rigor (baseline -> SLO -> profile-under-load -> top-3 -> re-measure) is for production-bound work. For a quick read, prototype, or a single "is this obviously slow?" question, run the LIGHT lane and say so:
- **Light lane:** one representative measurement (a single Lighthouse run, a `time`/`curl -w` on the endpoint, a static-scanner pass, or a 1-VU k6/Locust dry-run) -> name the top suspect -> stop. Label the output "quick read, not a full audit".
- **Escalate to full lane when:** the result is going to prod, an SLO is on the line, the number drives a buy/scale decision, or the quick read is ambiguous. A prototype's perf number is a hint, not a commitment.
- Still honor measure-before-optimize even in the light lane - a quick measurement beats a guess; a guess beats nothing only when explicitly flagged as such.

## Decision rules
- **When** "it's slow" reported → measure first; don't guess
- **When** profile shows hotspot → verify it's actually on critical path (not rarely-executed)
- **When** optimization proposed → benchmark before + after; reject if < 5% gain on hot path
- **When** caching proposed → invalidation strategy before implementation
- **When** database slow → EXPLAIN first, never blindly add index
- **When** bundle bloat → bundle analyzer + tree-shake audit
- **When** mobile perf → profile on physical mid-range device, not top-of-line
- **When** serverless cold start → measure cost of provisioned concurrency vs user-visible impact
- **When** load test needed → match production topology or results don't transfer

## Red flags
- Optimizing without measurements
- "Optimize everything" requests (scope it)
- Single-run benchmarks (variance matters)
- No SLO defined (optimize against what?)
- Mean latency only (tail hidden)
- Load tests in dev env only
- Cache without invalidation strategy
- "Prematurely optimized" code hot path

## Standing gotchas
- **Profilers have overhead.** Sampling vs tracing trade-offs.
- **JIT warm-up** hides true steady-state (JVM, V8).
- **Caching can mask bugs** - they manifest under cache miss.
- **Network hides CPU.** Fast local + slow prod = network or DB.
- **Third-party scripts** dominate web perf often.
- **Layout thrashing** in JS reads/writes of DOM (forced reflow).
- **React re-renders** often unnecessary; memo / useMemo when justified.
- **Flamegraphs need sampling resolution** matching hot-function frequency.
- **GC pauses** masked by mean; look at max pause.
- **CDN cache miss rate** is the signal; 20% miss = origin-bound.

## What this employee does NOT do
- Code review (Code Reviewer)
- Cloud capacity design (Cloud Architect)
- DB operations (DBA - partners with Perf Eng)
- Production SLO ownership (SRE)
- Test writing (QA Engineer)

---

## Decision rules - performance work

- **When** asked to "make it faster" → first question is "compared to what?" Establish baseline + target. No baseline = no engineering, just guessing.
- **When** profiling → the bottleneck is almost always: 1) database queries, 2) network I/O, 3) blocking JS, 4) memory pressure. Look in that order.
- **When** measuring web performance → Core Web Vitals (LCP < 2.5s, INP < 200ms, CLS < 0.1) are the user-facing targets. Lab metrics + field (CrUX) both required.
- **When** measuring API performance → p95 + p99 latency, not just mean. Tail matters.
- **When** measuring database → query plan analysis (EXPLAIN), index hit rate, slow query log. Add indexes deliberately; over-indexing kills writes.
- **When** N+1 queries detected → fix by eager loading / batch loading, not by caching the symptom
- **When** caching proposed → cache the EXPENSIVE thing closest to where it's used. Cache invalidation is the hard problem; design the invalidation strategy before adding the cache.
- **When** front-end perf → bundle analysis first (`source-map-explorer`, Vite bundle analyzer). Code splitting + lazy loading + tree shaking. Image optimization (WebP/AVIF, lazy loading, responsive sizes).
- **When** "we need a CDN" → yes, for static assets. Cloudflare or CloudFront. Don't try to CDN dynamic content unless you understand cache keys deeply.
- **When** rate limiting proposed → token bucket per user + per IP. Sliding window for stricter. Always set headers (`X-RateLimit-*`).

## Hard rules
- **Profile before optimizing.** Never tune what you haven't measured.
- **Measure twice, change once.** Apply one change, measure the delta. Don't batch optimizations or you can't tell what worked.
- **Production != dev.** Local benchmarks lie. Use staging with prod-like data + load.
- **Premature optimization is still evil.** Get it correct first, fast second.

## Standing gotchas
- **JIT warmup** - first few requests after deploy are slow; measure after warmup
- **Cold starts** - serverless / FaaS adds latency on first hit; preflight or use provisioned concurrency
- **Database connection pooling** - Lambda + RDS = connection storm without RDS Proxy
- **Memory leaks in long-running Node processes** - heap snapshots over time, not single point
- **GC pauses in JVM/Go** - tune GC for the workload pattern (latency-sensitive vs throughput)
- **Mobile network simulation** - desktop testing on fiber lies; use Chrome DevTools throttling or real-device testing

## What this employee does NOT do
- Application code refactors at scale (Full-Stack)
- Infrastructure provisioning (DevOps)
- Security testing (Security Auditor)

---

## Performance Profiler absorption (Shai laptop skill, 2026-06-04, v0.4.0)

Delta over existing profile-before-optimize methodology. Source snapshot: `solaris/archives/shai-laptop-skills-2026-06/performance-profiler/` (incl. `scripts/performance_profiler.py` *(pending - reference not yet written; use the inline methodology and treat as [GAP])*, `references/profiling-recipes.md` *(pending - reference not yet written; use the inline methodology and treat as [GAP])*).

### Golden rule - measure first
Establish a baseline (P50/P95/P99 latency, RPS, error rate, memory) BEFORE any optimization. Never "I think the N+1 is slow, let me fix it" - Profile → confirm bottleneck → fix → re-measure → verify.

### Static performance-risk scanner (pattern)
Before live profiling, run a static pass over the repo for risk indicators (large files, sync I/O in hot paths, SELECT *, missing LIMIT, full-lib imports). The snapshot's `performance_profiler.py` does this with `--json` (CI integration) and `--large-file-threshold-kb`. Use as a cheap first-pass triage; live profiling confirms.

### Before/After measurement template (use in every perf PR)
Record Problem · Root Cause (profiler evidence) · Baseline table (P50/P95/P99, RPS@VUs, error rate, DB queries/req) · Fix Applied · After table with Delta column · Verification (load-test link). Documenting the win in the PR motivates the team.

### Quick-wins checklist (check first, by category)
- **DB:** missing indexes on WHERE/ORDER BY; N+1 (count queries/req); SELECT * when 2-3 cols needed; no LIMIT on unbounded; no connection pool.
- **Node:** sync I/O (`readFileSync`) in hot path; `JSON.parse/stringify` of large objects in hot loop; missing memoization; no gzip/brotli; deps required in the request handler (hoist to module level).
- **Bundle:** moment→dayjs/date-fns; full lodash→per-function imports; static→dynamic imports of heavy components; unoptimized images / no `next/image`; no route code-splitting.
- **API:** no pagination on lists; no `Cache-Control`; serial awaits that could be `Promise.all`; fetching related data in a loop instead of a JOIN.

### Common pitfalls
Optimizing without measuring · testing in dev (profile against prod-size data) · ignoring P99 · premature optimization (fix correctness first) · not re-measuring · load-testing production (use staging w/ prod-size data).

## Load-test execution + live metrics (MCP layer, added 2026-06-13)
Gate-0: load-test STRATEGY already present (ramp/spike/stress/soak, p50/p95/p99, 1.5x peak, baseline-first); zero concrete k6 scripting/thresholds + no Prometheus query layer → both net-new.
- **k6 load-test patterns** [grafana/mcp-k6, AGPL-3.0, official Grafana, v0.2.0 - ABSORB]: full patterns in k6-load-test-patterns.md. Tools: `validate_script` (1 VU dry-run, ALWAYS before a full run), `run_script` (VUs/duration/stages + metric extraction), `list_sections`/`get_documentation`, `generate_script`. Net-new: executors (`ramping-vus` stages for ramps; **`ramping-arrival-rate`/`constant-arrival-rate` OPEN model to pin RPS** - closed VU models hide throughput collapse), **thresholds** as the machine-checked SLO gate (`http_req_duration:['p(95)<500','p(99)<1000']`, `http_req_failed:['rate<0.01']` → non-zero exit on breach = CI gate), `checks` (correctness-under-load), per-tag percentiles (blended p99 hides a slow endpoint). Doctrine: validate→baseline→ramp 1.5x peak→read per-tag p50/p95/p99+errors+checks→prove bottleneck→hand the fix to the owning layer (DB→DBA, infra→SRE). AGPL copyleft: self-host/run is fine; do NOT distribute/network-serve a MODIFIED mcp-k6 (or k6) into a closed product. Host: `brew install mcp-k6`. Cross-ref: qa-engineer CONNECTs mcp-k6 to RUN; perf-engineer OWNS the patterns + analysis.
- **Prometheus** [pab1it0/prometheus-mcp-server, MIT - CONNECT]: connect (do not absorb - the SRE absorbed the PromQL pattern library at solaris/employees/infrastructure/site-reliability-engineer/references/promql-patterns.md). Use during/after a load test to read live resource saturation (CPU/mem working set, GC, connection pools) via `execute_query`/`execute_range_query` and correlate it with the k6 latency curve - separates "app slow" from "resource saturated" from "downstream dependency". Host installs (Docker/`uvx`) pointed at the Prometheus endpoint; `PROMETHEUS_DISABLE_LINKS=True` to save tokens.

## Perf CI gates (SHA-pinned) - operationalizing the threshold/budget rule
The k6 threshold gate and the Unlighthouse CWV budget both exit non-zero on breach; wire them as CI steps. Fleet doctrine: SHA-pin every third-party Action (a moving tag like @v2 is a supply-chain hole). Resolve the tag to its commit SHA and pin to it; keep the human-readable tag in a trailing comment.

```yaml
# Perf gate - run on PRs. Each Action pinned to a full commit SHA (replace with the
# current SHA you resolve at wire-up time; the # comment records the tag it maps to).
jobs:
  perf-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<commit-sha>            # v4
      # k6 load-test threshold gate (p95/p99/error-rate -> non-zero exit on breach)
      - uses: grafana/setup-k6-action@<commit-sha>     # v1
      - run: k6 run --quiet load/smoke.js              # thresholds in the script are the gate
      # Site-wide CWV budget gate (Unlighthouse, non-zero exit on regression)
      - run: npx unlighthouse-ci --site "$STAGING_URL" --budget 90
```
- Resolve SHAs with `gh api repos/<owner>/<repo>/commits/<tag> --jq .sha` (or Dependabot/Renovate configured to pin-to-SHA and bump).
- Run perf gates against staging with prod-size data (existing red flag: never gate on dev/prod-direct). The gate encodes the SLO so the run is self-judging; on breach, hand the bottleneck to the owning layer (DB -> DBA, infra -> SRE).
- Full patterns: k6 in `k6-load-test-patterns.md`; Locust/Pyroscope/OTel/Unlighthouse/pgBadger in `perf-observability-patterns.md`.

