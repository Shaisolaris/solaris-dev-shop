# Performance observability + extended-stack patterns

Methodology only - no third-party code is bundled here (HARD RULE). Each tool is run/self-hosted by the host; this file captures HOW the employee uses it. Sources verified 2026-06-13 (see TOP5-CANDIDATES.md for stars/license/last-commit/Gate-0).

This deepens four lanes the employee named but never operationalized: Python-native load testing, continuous (prod) profiling, vendor-neutral telemetry, site-wide Core Web Vitals, and Postgres slow-log analysis.

---

## 1. Locust - Python-native load testing [MIT, locustio/locust]
The Python counterpart to the already-absorbed k6 (JS) patterns. Reach for Locust when the app + team are Python, when tests want to import the app's own client libraries, or when the protocol is not plain HTTP.

- **When Locust over k6:** team writes Python; non-HTTP protocol needs a custom client (gRPC/WebSocket/SQL/Kafka - subclass `User`, implement `client`); load tests want to live next to app code and reuse fixtures/factories.
- **Shape the load, not just the count:** `LoadTestShape` for custom ramp/spike/step profiles (the k6 executors equivalent); `constant_pacing`/`between` for think-time so VUs model real users, not a tight loop.
- **Open vs closed model caveat (same as k6):** Locust's user model is closed (a slow response throttles the generator). For a fixed-RPS capacity test use `constant_pacing` per task or pin throughput with a custom shape - do not read "users" as "RPS".
- **CI:** `--headless -u <users> -r <ramp> -t <dur> --csv=out --exit-code-on-error 1` then fail the build on the CSV's p95/fail-rate (Locust has no built-in threshold gate like k6 - assert on the CSV in a post-step). Distribute with `--master`/`--worker` when one box can't generate the load.
- **Doctrine carries over:** validate small -> baseline -> ramp to 1.5x peak -> read per-endpoint (`name=` to group) p50/p95/p99 + error rate -> prove bottleneck -> hand the fix to the owning layer. Never load-test prod; staging with prod-size data.
- Cross-ref: qa-engineer may RUN load tests; performance-engineer OWNS the load-test patterns + analysis (same split as k6).

## 2. Pyroscope - continuous profiling [AGPL-3.0 - FLAG, grafana/pyroscope]
Closes the gap between one-shot local profiling (clinic/py-spy/pprof, already covered) and always-on prod profiling. Use when "it's slow in prod but I can't reproduce locally" or to attribute a post-deploy regression to a function.

- **What it gives:** always-on low-overhead profiles (CPU, alloc/heap, lock/block, goroutines) stored as a queryable timeseries; **flamegraph diff** between two time windows or two deploys -> the exact function that got slower/fatter.
- **Two collection modes:** eBPF auto-instrumentation (no app change, system-wide, Linux) for a quick prod read; SDK push (per-language) when you want labeled profiles tagged by endpoint/tenant/version.
- **Workflow:** label profiles by `service`+`version`+`endpoint` -> after a deploy, diff new-version flamegraph vs old -> if a function regressed, that's the bottleneck (no guessing). Correlate the profile timeline with the APM latency curve and the k6/Locust load-test window.
- **AGPL self-host note (no code bundled):** Pyroscope is AGPL-3.0 copyleft. Self-hosting and running it as a tool carries no distribution obligation. Do NOT vendor modified Pyroscope source into a closed Solaris/client product, and do NOT expose a modified instance as a network service, without honoring AGPL. Same posture as the absorbed mcp-k6. Host: self-hosted OSS server or Grafana Cloud Profiles.
- Memory-scope note (fleet doctrine): profiles are labeled per service/version - when storing them for a multi-client Solaris setup, scope the storage by `org_id`/`app_id` so one client's profiles never surface in another's view (cross-tenant leakage = Security Auditor finding).

## 3. OpenTelemetry Collector - vendor-neutral telemetry [Apache-2.0, open-telemetry/opentelemetry-collector]
Frees "APM interpretation" from being Datadog/New-Relic-specific. Instrument the app ONCE with OTel; route traces/metrics/logs to any backend via the Collector (receivers -> processors -> exporters).

- **Why it matters for perf work:** **exemplars** link a latency-metric spike directly to a representative trace (metric -> trace in one click); **span metrics** processor derives RED metrics (rate/errors/duration) from spans so you get p95 per endpoint without separate instrumentation; **tail-based sampling** keeps the slow/errored traces and drops the boring fast ones (the ones a perf engineer actually wants).
- **CONNECT, not lock-in:** the Collector is the portable substrate UNDER whichever APM the client already pays for - swap the exporter, keep the instrumentation. Good default when a client has no APM yet or wants to avoid vendor lock.
- **Cross-ref:** the SRE/observability layer owns the deployment + PromQL pattern library (solaris/employees/infrastructure/site-reliability-engineer/references/promql-patterns.md). Performance-engineer CONNECTs to read perf-relevant signals (latency histograms, exemplars, span metrics) during/after a load test; does not own the pipeline config.

## 4. Unlighthouse - site-wide Core Web Vitals + CI budget [MIT, harlan-zw/unlighthouse]
Extends the single-page Lighthouse + CrUX concept to a whole-site sweep with a regression gate. Use for a site-wide CWV audit and to stop perf regressions in CI.

- **What it gives:** crawls the site, runs Lighthouse on every page (smart sampling to avoid re-scanning templated pages), one aggregated UI report ranking the worst offenders by category (perf/a11y/SEO/best-practices).
- **CI budget gate (the net-new piece):** run in CI with per-category/per-metric budgets; non-zero exit on regression -> a CWV gate that fails the build, the lab-side analog of the k6 threshold gate. Pair lab budgets with field CrUX so a passing lab score that users still feel slow gets caught.
- **Workflow:** baseline full-site scan -> set budgets at current p75 (LCP<2.5s, INP<200ms, CLS<0.1) -> wire the CI gate SHA-pinned (see CI snippet in rules.md) -> triage the ranked worst pages first (Amdahl: the worst-LCP template usually repeats across many URLs).

## 5. pgBadger - Postgres slow-log analysis [PostgreSQL License - permissive, darold/pgbadger]
The log-side complement to live EXPLAIN. Where `pg_stat_statements`/EXPLAIN answer "what does THIS query do", pgBadger answers "what is ACTUALLY eating prod time across the whole workload".

- **What it gives:** parses Postgres logs (stderr/csvlog/jsonlog) into a detailed HTML report - top time-consuming queries by total + mean time, normalized query fingerprints (so `WHERE id=1` and `WHERE id=2` aggregate), temp-file usage (under-provisioned `work_mem`), lock waits, checkpoint pressure, hourly traffic histograms.
- **Prereq:** enable `log_min_duration_statement` (e.g. log statements > 100ms) and the csvlog/jsonlog format; pgBadger reads the resulting logs offline - zero load on the live DB.
- **Workflow:** collect a representative window of prod logs -> pgBadger report -> the top-N by total time are the real bottlenecks (a fast query run a million times beats a slow query run twice) -> for each, EXPLAIN (ANALYZE, BUFFERS) to confirm the plan -> hand index/rewrite to the DBA. Partner with DBA for deep DB work (existing hand-off rule).
