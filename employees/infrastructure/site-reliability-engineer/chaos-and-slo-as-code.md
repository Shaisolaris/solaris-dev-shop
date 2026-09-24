# Chaos engineering + SLO-as-code

Methodology only (no tool code bundled). Absorbed 2026-06-13 from two verified, fresh, permissively-licensed sources:
- **chaos-mesh/chaos-mesh** (Apache-2.0, 7.7k stars, last commit 2026-06-12, CNCF incubating) - chaos-engineering experiment lifecycle and fault catalogue.
- **slok/sloth** (Apache-2.0, 2.5k stars, last commit 2026-05-26, maintainer slok) - SLO-as-code generator that emits Prometheus recording + multi-window multi-burn-rate alerting rules from one spec.

Both are net-new vs prior content: the v0.4.0 rebuild explicitly dropped the unsourced chaos-engineering competency, and the SLO doctrine said "encode as recording + alerting rules" without ever shipping a generator. This file gives the SRE a defensible practice for both, sourced.

Self-host note: chaos-mesh and sloth are tools the SRE recommends and reasons about, not things the coding agent runs directly. The host installs them (chaos-mesh into the target Kubernetes cluster via Helm; sloth as a CLI / Prometheus-operator controller). For a Solaris agency client on plain VPS/WordPress without Kubernetes, chaos-mesh does not apply - use the manual game-day drill below instead.

## Chaos engineering - the discipline (not the tooling)
Chaos engineering is experimentation to build confidence that the system withstands turbulent conditions in production. It is the empirical counterpart to the reliability patterns the SRE already recommends (circuit breakers, retries with backoff, bulkheads) - you inject the failure to prove the pattern actually fires.

**Preconditions (do NOT run a chaos experiment without these):**
1. Observability mature enough to measure the result (golden signals live, SLO dashboard, alerting wired). A fault injection you cannot observe teaches nothing.
2. A defined steady state - a measurable output that says "the system is healthy" (e.g. error ratio < 0.1%, p99 < 300ms, checkout success rate baseline).
3. A blast-radius plan and an abort button before you start.

**Experiment lifecycle (5 steps):**
1. **Hypothesis** - "Under condition X, the steady state holds." Write it before injecting. No hypothesis = not an experiment.
2. **Define steady state** - the metric(s) and the acceptable band, measured on both the control and the experiment population.
3. **Inject a real-world fault, smallest blast radius first** - one pod, one AZ, one dependency, a fraction of traffic. Widen only after the small case passes.
4. **Observe** - did the steady state hold? Compare control vs experiment. Watch the SLO budget burn in real time.
5. **Abort + learn** - automatic abort if the steady state breaks past a guardrail; every experiment produces either a confirmed assumption or a reliability ticket.

**Fault catalogue to draw experiments from (chaos-mesh fault types):**
- Pod faults: kill, failure, container-kill (tests restart/replica/self-healing).
- Network: latency, packet loss, partition, bandwidth throttle, DNS failure (tests timeouts, retries, circuit breakers).
- IO: latency, fault, attribute override (tests slow-disk degradation).
- Stress: CPU / memory pressure (tests saturation handling, load shedding).
- Time: clock skew (tests cert/token/leader-election sensitivity).
- Kernel / HTTP fault injection for finer-grained chaos.

**Game day = a scheduled, rehearsed chaos experiment with the on-call present.** It doubles as runbook validation and incident-command practice. Run the actual incident process (declare a fake SEV, name an IC, post a status update to a test channel) so the muscle memory is real. After-action: every gap found becomes a runbook fix or an automation ticket.

**Agency edition (no Kubernetes):** a "game day" on a client WordPress/Laravel/VPS stack is a manual tabletop + controlled drill - block the DB port for 60s, kill the app process, let the SSL cert near-expiry alert fire in staging, simulate the hosting provider being down by pointing DNS at a dead IP in a staging zone. Same discipline (hypothesis, observe, abort, learn), no chaos platform required.

## SLO-as-code (Sloth) - operationalizing the burn-rate doctrine
The SRE already preaches multi-window multi-burn-rate alerting (14.4x / 6x / 1x). Sloth is how that doctrine becomes committed Git artifacts instead of hand-written, drift-prone PromQL. You author one SLO spec; Sloth generates the recording rules and the multi-window multi-burn-rate alerting rules for you, consistently across every service.

**Spec shape (conceptual - the SRE reasons about this, host runs the generator):**
- `service` + a list of `slos`, each with: `name`, `objective` (e.g. 99.9), and two SLI queries - `error_query` (events that count against the budget) and `total_query` (all events). Plus an `alerting` block: page + ticket annotations and labels (severity, runbook link, team).
- Sloth expands that into: SLI recording rules at multiple windows, error-budget + burn-rate recording rules, and alerting rules with the page/ticket multi-window pairs already wired (fast: 5m AND 1h; slower: 30m AND 6h; ticket: 6h AND 3d) - exactly the thresholds in rules.md and references/promql-patterns.md.
- OpenSLO support: the same spec can be written in the vendor-neutral OpenSLO format. Prometheus-operator support: run Sloth as a controller with a PrometheusServiceLevel CRD so SLOs live next to the service manifest.

**Why this matters for the SRE doctrine:** it closes the gap between "we have an SLO in a doc" (a red flag in rules.md) and "the SLO is enforced as alerting rules in Git." The generated rules are the committed alerting rules; the Prometheus MCP / `execute_query` stays for ad-hoc incident exploration only (per references/promql-patterns.md doctrine).

**Alternative noted:** litmuschaos/litmus (Apache-2.0, 5.4k stars) is the other CNCF chaos platform - K8s-native, ChaosHub experiment library, has an MCP server as of late 2025. chaos-mesh was chosen here for the broader fault catalogue; litmus is the equally-valid swap if the client already runs it.

## CONNECT note (host installs)
- chaos-mesh: Helm install into the target cluster; experiments authored as YAML or via the dashboard; always set a `duration` and use the built-in scheduler's abort. Never run an unscheduled chaos experiment against client production without the client's explicit sign-off and a steady-state guardrail.
- sloth: CLI (`sloth generate`) in CI to compile specs to rules at build time, or the Kubernetes controller for live CRD reconciliation. Generated rules are reviewed in PR like any other alert rule.
