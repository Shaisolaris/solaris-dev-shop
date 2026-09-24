# PromQL patterns for SLO + golden-signal queries

Absorbed from pab1it0/prometheus-mcp-server (MIT, ~470 stars, commit main @ 2026-06-13). The server exposes Prometheus to the SRE via five tools - `execute_query` (instant PromQL), `execute_range_query` (range query: start/end/step), `list_metrics`, `get_metric_metadata`, `get_targets`. Net-new vs prior content: the SRE had SLO/burn-rate doctrine but no concrete PromQL to compute SLIs, burn rates, and golden signals. These are the canonical queries it runs through the MCP.

Discovery first: `list_metrics` / `get_metric_metadata` to find the real metric names in THIS stack (never assume); `get_targets` to confirm scrape health before trusting any number (a stale/down target = silent blind spot, not "all green").

## Golden signals (RED for request-driven services)
- **Rate (traffic):** `sum(rate(http_requests_total[5m])) by (service)`
- **Errors (error ratio SLI):** `sum(rate(http_requests_total{code=~"5.."}[5m])) by (service) / sum(rate(http_requests_total[5m])) by (service)` - this ratio IS the availability SLI; 1 − this = success rate.
- **Duration (latency SLI):** `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))` (p99; swap 0.95/0.50). Latency SLI as "fraction fast enough": `sum(rate(http_request_duration_seconds_bucket{le="0.3"}[5m])) by (service) / sum(rate(http_request_duration_seconds_count[5m])) by (service)`.

## USE (for resources - nodes/pods/saturation)
- **Utilization (CPU):** `1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance)`
- **Saturation (mem working set vs limit):** `container_memory_working_set_bytes / container_spec_memory_limit_bytes`
- **Errors (disk/net):** `rate(node_disk_io_errors_total[5m])`, `rate(node_network_receive_errs_total[5m])`

## Error-budget burn rate (the SLO alerting workhorse)
Burn rate = (observed error ratio) / (1 − SLO target). For a 99.9% SLO, budget = 0.001, so:
`( sum(rate(http_requests_total{code=~"5.."}[1h])) / sum(rate(http_requests_total[1h])) ) / 0.001`
- **Multi-window multi-burn-rate** (Google SRE workbook, page-vs-ticket): page when a FAST window AND a SLOW window both breach, to fire fast on big outages without flapping on blips:
  - Page (fast burn): 14.4× over `5m` AND `1h` (burns ~2% of a 30d budget in 1h).
  - Page (slower): 6× over `30m` AND `6h`.
  - Ticket (slow burn): 1× over `6h` AND `3d`.
- Encode these as Prometheus recording + alerting rules; the MCP `execute_query` is for ad-hoc/incident checks, not a substitute for committed alert rules in Git.

## Incident-time ad-hoc checks (run via execute_query/range)
- Spot the bad version: add `by (version)` / `by (pod)` to the error query to localize a bad rollout.
- Confirm recovery: `execute_range_query` the error ratio across the incident window to time MTTR and verify the fix actually held, not just dipped.
- Saturation correlation: range-query CPU/mem alongside latency to separate "overloaded" from "slow dependency".

## Doctrine
- Alerts that wake people live as committed Prometheus alerting rules (Git), not as MCP queries. The MCP is for exploration, incident diagnosis, and validating an SLI definition before you codify it.
- Always sanity-check `get_targets` - a green dashboard over a down scrape target is a false sense of security.

## CONNECT note (host installs)
prometheus-mcp is also wired as a CONNECT for performance-engineer. Host installs the server (Docker image or `uvx`/pip per repo) pointed at the Prometheus endpoint; `PROMETHEUS_DISABLE_LINKS=True` to save context tokens; `TOOL_PREFIX` to run multiple instances against different environments (e.g. `staging_execute_query`).
