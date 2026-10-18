# M03 validation oracle for G03 (recovery without data loss)

Grok self-validation material for candidate `7c63297d626ab2ac5929080e57c9ae66e7c905bc`
(branch `review/grok-g03-recovery`, base `02ba9c571b10ad1dba792d2ac5534bcad3171e67`).
This is not independent review. It was written separately from the builder's
`examples/capabilities/G03/recovery_oracle.py` and tests, from the G03/M03 acceptance text and the
documented CLI in `employees/infrastructure/database-administrator/sqlite-recovery.md`. Python 3.12
standard library, synthetic data, disposable temp directories only. Verdict and findings: `VALIDATION.md`.

| File | Purpose |
|---|---|
| `oracle/m03_oracle.py` | 12 black-box checks (k1 to k12): exact values, 13 invalid snapshots, byte-identical dry runs, SIGKILL in both rename gaps plus forced roll-back, killed recover, outside writes, finite timeout, exact missing-DB check, 6x8 concurrent restores, value fidelity (sqlite-prefixed tables, header pragmas), equal-count changes, external flock. Values are read from private copies, never from tool output; nothing skips. |
| `oracle/inject/sitecustomize.py` | Fault injector on `PYTHONPATH`: SIGKILL at the Nth rename/unlink or write-open under a root. Patches the standard library only. |
| `oracle/stubs/` | Negative controls: a no-op that claims success, and a naive copier. |
| `oracle/make_mutants.py`, `oracle/run_teeth.sh`, `oracle/run_builder_tests_vs_mutants.sh` | 15 broken copies of `sqlite_recovery.py` (each replacement applies exactly once) and runners. |
| `oracle/m03_adversarial.py` | 17 unseen cases (forged journals, symlinked lock/DB, sidecars, open readers, odd timeouts, write-open kills). |
| `oracle/m03_operational.py` | Drill at every N, random external SIGKILL of restore and of recover, 8 DBs x 50,000 rows. |
| `oracle/m03_fresh_caller.sh` | `env -i`, new HOME, only the documented commands. |
| `oracle/m03_finding_repros.sh` | One reproduction per finding (F1 to F7). |
| `oracle/m03_*probe*.py`, `oracle/m03_py39_wal_repro.sh` | Stdlib-only probes isolating the Apple SQLite 3.54.0 WAL behaviour (F3). |
| `oracle/proposed-fix.patch` | Demonstration fix for F1/F2 used as a positive control; not applied to the candidate. |
| `raw/` | Run logs, including rejected and superseded runs. Local paths are replaced by placeholders. |

Run from the repository root at the candidate commit:

```sh
PY=python3.12; T=employees/infrastructure/database-administrator/sqlite_recovery.py; V=examples/validation/M03/oracle
$PY $V/m03_oracle.py -- $PY $T
$PY $V/m03_oracle.py -- $PY $V/stubs/noop_echo.py      # must REJECT
python3 $V/make_mutants.py $T /tmp/m03-mutants
for m in /tmp/m03-mutants/*/; do $PY $V/m03_oracle.py -- $PY "$m/sqlite_recovery.py"; done
$PY $V/m03_adversarial.py -- $PY $T
$PY $V/m03_operational.py --rounds 60 -- $PY $T
zsh $V/m03_finding_repros.sh $(command -v $PY) "$PWD" /usr/bin/python3
```
