# AI-driven RCA investigation playbook

Methodology reference adapted from robusta-dev/holmesgpt, "The CNCF SRE Agent"
(Apache-2.0; CNCF sandbox; created by Robusta.Dev with major Microsoft contributions).
Patterns only; no tool code is bundled and Claude does not run HolmesGPT. This is the
REACTIVE counterpart to the existing references: chaos-and-slo-as-code.md is proactive
(prove reliability before incidents) and promql-patterns.md is a query cookbook. Neither
gives a structured loop for going from a firing alert to a named root cause to a runbook.
This file does.

## What is net-new (Gate-0)

Prior content: SLO/burn-rate doctrine, chaos experiment lifecycle, golden-signal +
burn-rate PromQL, ad-hoc incident checks. What was missing: a defensible
ALERT -> EVIDENCE -> ROOT-CAUSE -> RUNBOOK investigation methodology that gathers
evidence across signals systematically rather than relying on the on-call's intuition.
That investigation loop is the absorption here.

## The agentic RCA loop

The model is an agentic loop: given a symptom (an alert), iteratively pull live
observability data from multiple sources and converge on the root cause, instead of
running one query and guessing. Each pass: form the current best hypothesis, decide the
single most discriminating piece of evidence that would confirm or kill it, fetch
exactly that, update the hypothesis, repeat until a root cause is supported by evidence
(not asserted).

Four phases:

### 1. Alert intake (start from the symptom, not a blank page)
- Pull the firing alert with its full context: which SLI/rule fired, severity, the
  labels (service, version, pod, region), the time it started, the runbook link in the
  alert annotation (the SLO-as-code specs in chaos-and-slo-as-code.md already attach
  runbook + team annotations - this is where they pay off).
- Restate the symptom precisely: "checkout 5xx ratio breached the 14.4x fast-burn
  page threshold at 14:02 UTC, isolated to service=checkout version=v231." A vague
  symptom yields a vague investigation.
- Sanity-check the signal is real before investigating: confirm scrape targets are up
  (the get_targets discipline from promql-patterns.md) so you are not chasing a
  monitoring artifact.

### 2. Evidence gathering (systematic, multi-signal, breadth then depth)
Walk the signal types in order, pulling the narrowest useful slice of each. The point is
COVERAGE so a real cause is not missed, then DEPTH on the lead that emerges:
- **Metrics** - golden signals for the affected service, sliced by the alert's labels
  (by version / by pod) to localize. Reuse the PromQL recipes; add `by (version)` to
  spot a bad rollout fast.
- **Logs** - error logs for the affected resource around the start time; grep for the
  first new error class, not the loudest one.
- **Events / state** - recent deploys, config changes, scaling events, restarts,
  OOMKills, crash loops, pending pods. "What changed just before T0" is the highest-yield
  question in RCA.
- **Traces** - for latency/dependency symptoms, find the slow span to separate "our code
  is slow" from "a downstream dependency is slow."
- **Dependencies** - DB health/slow-queries, queue lag/partitions, cache, upstream
  service health. A symptom in service A is often a cause in service B.
- **Change history** - the deploy/PR/merge timeline. Correlate T0 against the last
  change to the affected component.

Discipline: gather evidence read-only. RCA is investigation, not remediation - never
mutate production state while diagnosing.

### 3. Root-cause synthesis (evidence-backed, ranked)
- State the root cause as a causal chain: trigger -> mechanism -> symptom (e.g. "v231
  raised the DB connection-pool ceiling -> pool exhausted under peak -> checkout requests
  blocked on connection acquire -> 5xx ratio breached"). Every link must cite the
  evidence that supports it (the deploy event, the pool-saturation metric, the log line).
- Rank competing hypotheses by evidential support; explicitly note what was ruled OUT and
  why (kills the "it was probably the network" hand-wave).
- Distinguish proximate cause (what to fix to recover now) from contributing/root cause
  (what to fix so it does not recur) - both go in the writeup.

### 4. Runbook + handback
- Map the root cause to the matching runbook. Runbooks are a first-class evidence source,
  not an afterthought: pull them from where they live (internal docs/knowledge base,
  the alert's runbook annotation, or public/community docs for known failure modes).
- If a runbook exists, follow/cite it. If none exists, the investigation's output IS the
  seed of a new runbook - write it (this is the chaos game-day "every gap becomes a
  runbook fix" loop, now fed by real incidents too).
- Write findings back to where the incident lives (the alert, the ticket, the incident
  channel) so the next responder inherits the chain of reasoning, not just a verdict.

## Operator / continuous mode (proactive RCA)
Beyond reacting to a page, the same loop can run on a schedule or as a post-deploy gate:
- **Deployment verification** - after a release, run a health check that investigates the
  new version's signals and confirms it is healthy before declaring the rollout good. This
  is the RCA loop wired to chaos-and-slo-as-code.md's steady-state definition - the
  post-deploy proof, automated.
- **Scheduled health checks** - periodically investigate key services to catch
  regressions before a customer or a page does.
For a Solaris agency client on a plain VPS/WordPress/Laravel stack (no Kubernetes), this
degrades to a scheduled scripted check (HTTP synthetic + error-rate + cert-expiry +
disk/db health) whose FAILURE triggers the same alert->evidence->cause->runbook loop.

## Context discipline for large observability data
Observability payloads are huge; the RCA loop must not blow the window:
- Filter server-side before pulling (time-bound, label-bound, top-N), never "fetch all
  logs then think."
- Pull the narrowest discriminating slice per step; transform/summarize large outputs to
  the few lines that move the hypothesis.
- This mirrors the context-manager paging doctrine: keep the hot evidence in-context,
  leave the bulk on disk behind a query.

## Safety
- Read-only by default; respect RBAC/least-privilege on every data source. Investigation
  must be safe to run against production.
- Remediation (scaling, rollback, restart) is a SEPARATE, human-gated step - the playbook
  produces the diagnosis and the recommended fix; a human (or an explicitly sanctioned
  remediation path) applies it. Never auto-mutate client production.

## CONNECT note (host installs)
HolmesGPT itself is a host-installed/operated agent (CLI or Kubernetes operator) that
ingests alerts from AlertManager/PagerDuty/OpsGenie/Jira and connects to data sources
(Prometheus/Grafana/Datadog/Loki/Tempo/SQL/etc., many via MCP). The SRE recommends and
reasons with this methodology; the host runs the tool with read-only credentials. This
playbook is the methodology; it does not require HolmesGPT to be installed - the loop is
runnable by hand against the same data sources (e.g. the prometheus-mcp already wired in
promql-patterns.md).

---
Source: robusta-dev/holmesgpt (Apache-2.0, ~2.6k stars, CNCF sandbox; Robusta.Dev +
Microsoft). README read 2026-06-15. Methodology absorbed (agentic alert->evidence->
root-cause->runbook investigation loop, operator/continuous-verification mode, large-data
context discipline, read-only safety); the HolmesGPT tool is not bundled or run. No
em-dashes.
