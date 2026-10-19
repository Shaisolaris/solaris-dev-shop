# Incident timeline, SLO and rollback decision (incident_slo.py)

For synthetic or exported records only. `incident_slo.py` reads one incident bundle and writes one
report: the merged timeline, exact SLO and error-budget values for the named service window, the
telemetry it does not have, and a rollback decision whose trace names the service, the window and
the revision. It never deploys, rolls back, opens a socket or writes anything but `--out`.

## Bundle (schema solaris.incident-bundle/1)

```
service      name of the service the SLO belongs to
window       {start, end}: the service window, whole UTC minutes, end exclusive, at most 31 days
slo          {objective (0..1, e.g. 0.99), rollback_burn_rate (default 10), min_coverage (default 0.9)}
telemetry    [{minute, good, total, source?, received_at?}]: request counts per minute and source
events       [{id, at, kind, actor?, detail?, received_at?}]: kind is detected, declared, mitigated,
             resolved, deploy, rollback, status or note
change       optional {revision, previous, deployed_at, migrates_data, data?: {snapshot, databases}}
diagnoses    optional [paths to G10 traces (solaris.net-trace/1)], inside the bundle folder
```

## Command

```bash
T=employees/infrastructure/site-reliability-engineer/incident_slo.py
python3 $T report bundle.json                     # timeline, SLO and decision as text
python3 $T report bundle.json --json --out r.json # JSON report, written atomically
```

Exit codes: 0 analysed; 2 invalid input, nothing written (a previous `--out` stays as it was).

## How records are judged

- **Sources**: `source` names the reporter whose counts add up to the service's traffic (a load
  balancer, region or shard). A minute's value is the sum over its distinct sources, so telemetry split
  across load balancers is measured whole. Records without `source` belong to one unnamed source. Do
  not give a re-delivery or a mirror of the same traffic a different source name: it would be added.
- **Duplicates**: a source delivering a minute again with the same counts is counted once; an event id
  delivered again with the same content is kept once (earliest `received_at`). An event id with two
  different contents refuses the bundle: the tool will not pick a story.
- **Conflicting minutes**: one source reporting two different counts for one minute makes the whole
  minute conflicting; it is labelled and left out (the tool does not pick a count). Different counts from
  different sources are not a conflict: they are summed.
- **Missing telemetry**: minutes with no record are listed as ranges, put on the timeline and left
  out. They are never counted as good. When measured minutes cover less than `min_coverage` of the
  window the SLO status is `insufficient_telemetry`, not met or breached.
- **Late and out-of-order**: records more than 300 s late are labelled `late` and still used; the
  timeline is sorted by time whatever the input order.
- **Values**: availability = good / total over measured minutes; error budget = (1 - objective) x
  total; budget remaining = 1 - bad / budget; burn rate = (bad / total) / (1 - objective). Exact
  rational arithmetic, rendered with six decimals (round half to even).
- **Impact**: the minutes whose error ratio exceeds 1 - objective. Detect, mitigate and resolve times
  are measured from the first of them. A start next to a gap is marked `at_or_before`.

## Rollback decision (in this order)

1. Change outside the window: `not_applicable`.
2. Fewer than `min_coverage` of the minutes since the change measured: `insufficient_evidence`.
3. No budget-burning minute: `do_not_rollback`. Impact began before the change: `do_not_rollback`.
   Impact start hidden by a gap that reaches back past the change: `insufficient_evidence`.
4. Burn rate from the change to the end of the impact below `rollback_burn_rate`: `do_not_rollback`.
5. A G10 trace captured during the impact that places the fault at the dns, route or tls layer
   without the application as a candidate: `do_not_rollback` (rolling back code does not fix it).
6. Change migrated data: `rollback` only when G03 `verify` passes on the named snapshot, and the
   snapshot id is named; otherwise `rollback_blocked`. Otherwise `rollback` (code only).

The decision is a recommendation with its evidence. Executing a rollback stays with the deploy
owner (devops-engineer `local_deploy.py` on local fixtures, the provider tooling elsewhere) and the
human approval it requires.

## Limits

- Request-based availability SLO only; latency SLOs and multi-window alert rules are not computed.
- Telemetry is per minute; finer buckets must be rolled up first.
- The burn rate since the change is measured from the start of the change's minute, so up to 59 s
  before `deployed_at` are included.
- Not run: any live metrics backend, paging system or production rollback.
