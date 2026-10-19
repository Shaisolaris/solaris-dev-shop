# G39 cross-employee delivery and recovery drill

One synthetic customer delivery (the Lakeside Clinic portal) composed from tools that already exist, with a
forced interruption, another worker resuming and a review invalidated by a changed output. The only new tool
is `employees/product-project/delivery-lead/delivery_evidence.py` (see `delivery-evidence.md` beside it): it
records that each specialist tool actually ran and checks the delivery claim against those records, the files
on disk and the G04 work order. It does not schedule or launch workers.

| Contribution | Existing tool | Goal |
|---|---|---|
| work order, crash drill, resume by another worker | `infrastructure/fleet-dispatcher/handoff.py` | G04 |
| project activation (run inside the work order) | `product-project/project-onboarding/activate.py` | G02 |
| monthly revenue reconciliation | `data/data-engineer/csv_reconcile.py` | G13 |
| duplicate and tenant-boundary probe of the invoice API | `engineering/backend-developer/ledger_api.py` probed by `quality-security/security-auditor/boundary_probe.py` | G19 |
| snapshot of the API database | `infrastructure/database-administrator/sqlite_recovery.py` | G03 |
| output digests and stale-review states | `quality-security/assurance/quality_os.py` | G05 |

## Run it

```bash
python3 examples/capabilities/G39/drill.py                                                       # DRILL PASSED
python3 examples/capabilities/G39/drill_oracle.py                                                # ACCEPTED 14/14
python3 examples/capabilities/G39/drill_oracle.py --tool examples/capabilities/G39/naive_evidence.py  # REJECTED 9/14
python3 examples/capabilities/G39/drill_oracle.py --tool examples/capabilities/G39/noop_evidence.py   # REJECTED 0/14
```

The drill: ana starts the work order and it crashes after delivering but before its receipt (exit 75); ana
records the reconciliation; a verify then is NO_GO; ben probes the API, snapshots its database and resumes
the order (the duplicate delivery is suppressed); verify is GO. The reconciliation report is then edited:
verify is NO_GO with the data-engineer contribution stale; cy re-runs it and verify is GO again. The outbox
holds exactly one delivery.

The oracle builds a fresh folder per check and reads the ledger and files itself: o1 clean GO with true
digests, o2 real exit codes, o3 unevidenced claim, o4 the dirty G13 September drop (exit 1 blocks unless the
caller accepts it), o5 changed output, o6 changed tool script, o7 edited and removed records, o8 cut-short
last line, o9 recorder killed mid-run, o10 eight concurrent recorders, o11 invalid input and a credential
never written, o12 work order stopped or crashed, o13 symlinked output, o14 the full drill.
`naive_evidence.py` is the real tool with three shortcuts (trust recorded digests, no chain check, any
delivery counts); `noop_evidence.py` records nothing and answers GO.

Not run: workers on different machines or a network folder (local `fcntl` locks only), a live customer,
any external service. Worker names are plain-text claims. POSIX, Python 3.9+.
