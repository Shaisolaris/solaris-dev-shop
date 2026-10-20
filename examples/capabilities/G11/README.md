# G11 incident timeline, SLO and rollback decision: oracle and fixtures

`fixtures/` holds 7 synthetic bundles for
`employees/infrastructure/site-reliability-engineer/incident_slo.py`: service `checkout-api`, window
2026-10-18T09:00Z to 10:00Z, objective 0.99, rollback burn threshold 5, change r41 -> r42 at 09:20:30Z.
Telemetry is shuffled, with re-delivered minutes, late rows and a re-delivered page event.

| Fixture | SLO status | Decision |
|---|---|---|
| 01 clean control | met, availability 0.998638 | do_not_rollback (no budget-burning minute) |
| 02 regression from 09:22 to 09:40 | breached, 0.969345, burn 3.065517 | rollback, code only (burn 8.924194 since the change) |
| 03 same, G10 trace at 09:30 shows NXDOMAIN | breached | do_not_rollback (G10 places the fault at dns) |
| 04 impact from 09:12, before the change | breached | do_not_rollback |
| 05 telemetry missing 09:25 to 09:35 | insufficient_telemetry (coverage 0.833333) | insufficient_evidence |
| 06 regression, change migrated data, no snapshot | breached | rollback_blocked |
| 07 two conflicting minutes at 09:50 | breached, conflicting minutes left out | rollback |

`traces/dns-nxdomain-0930.json` is the G10 fixture 02 trace with its capture time set to 09:30.

```bash
T=employees/infrastructure/site-reliability-engineer/incident_slo.py
python3 $T report examples/capabilities/G11/fixtures/02-deploy-regression.json        # exit 0
python3 $T report examples/capabilities/G11/fixtures/03-dns-fault-during-impact.json  # exit 0
python3 $T report examples/capabilities/G11/fixtures/05-gap-after-change.json --json  # exit 0
python3 $T report examples/capabilities/G11/README.md                                 # exit 2
```

`incident_oracle.py` generates its own bundles from a seed (other services, windows and counts),
computes the expected values with decimal arithmetic and reads the JSON, so exit 0 alone proves
nothing:

```bash
PY=python3.12
$PY examples/capabilities/G11/incident_oracle.py -- $PY $T                                  # ACCEPTED 13/13
$PY examples/capabilities/G11/incident_oracle.py -- $PY examples/capabilities/G11/naive_stub.py  # REJECTED
$PY examples/capabilities/G11/incident_oracle.py -- $PY examples/capabilities/G11/noop_stub.py   # REJECTED
```

Checks: o1 clean control exact; o2 regression after a change (exact SLO, impact, response times,
rollback naming service, window and revision); o3 re-import doubled and shuffled gives the same
SLO, timeline and decision, rerun byte-identical; o4 gaps labelled with exact ranges, a gap after the
change gives no decision, low coverage is insufficient; o5 conflicting minutes left out, an event id
with two contents refused with the previous report kept; o6 a G10 dns fault during the impact stops a
code rollback while an application fault or an earlier dns trace does not; o7 impact before the
change, a gap hiding the impact start, and a slow burn below the threshold; o8 a migrating change needs a G03-verified snapshot (none
and damaged are blocked, a real one is named); o9 late records labelled and still scored; o10 seven
invalid bundles exit 2, then a valid run recovers; o11 a 30-day window (86 000+ records, doubled and
shuffled) with exact values and identical parallel runs; o12 no network use under a socket-denying
guard and the bundle folder byte-identical; o13 telemetry split across two load balancers is summed per
minute (the only error minute, whose shares differ, breaches the SLO), equal counts from two sources both
count, and one source reporting two counts for a minute is a conflict. o14 expected sources: a load balancer silent for 30 of 60 minutes leaves those minutes out and blocks met with a per-source label; a declared source that never reports makes every minute partial; names match trimmed and case-folded and two spellings of one name are refused; a source silent after a change blocks a do_not_rollback.

The fixtures' re-delivered telemetry rows carry the source that first reported the minute: a re-delivery is
the same source again, not a second load balancer.
