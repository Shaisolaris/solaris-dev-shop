# G03 recovery oracle

`recovery_oracle.py` drives a recovery command against disposable SQLite datasets and checks
real outcomes: row values read back with `sqlite3`, byte hashes of every dataset file,
outside sentinels, elapsed time under a held lock and leftover files. Exit 0 alone proves
nothing, so a no-op fails.

```bash
PY=python3.12
TOOL=employees/infrastructure/database-administrator/sqlite_recovery.py
$PY examples/capabilities/G03/recovery_oracle.py -- $PY $TOOL
$PY examples/capabilities/G03/recovery_oracle.py -- $PY examples/capabilities/G03/noop_stub.py    # must be REJECTED
$PY examples/capabilities/G03/recovery_oracle.py -- $PY examples/capabilities/G03/naive_stub.py   # must be REJECTED
```

Checks: C1 exact values restored and the replaced file kept; C2 five invalid snapshots
(flipped byte, garbage manifest, link member, forged values with valid structure, truncated)
leave the good target byte-identical; C3 dry run byte- and mtime-identical; C4 crash after
the first rename (target absent, snapshot deleted) rolls forward, a damaged stage rolls back;
C5 crash after install completes; C6 no writes outside the dataset; C7 restore and snapshot
under a held SQLite lock end within bounds; C8 exact missing-database check; C9 explicit
`--confirm` intent; C10 six concurrent restores; C11 8 databases x 25000 rows. POSIX only.
