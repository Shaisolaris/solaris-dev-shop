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

Checks: C1 exact values restored and the replaced file kept; C2 six invalid snapshots
(flipped byte, garbage manifest, link member, forged values with valid structure, truncated,
an extra database member)
leave the good target byte-identical; C3 dry run byte- and mtime-identical; C4 crash after
the first rename (target absent, snapshot deleted) rolls forward, a damaged stage previews and
does a roll back;
C5 crash after install completes; C6 no writes outside the dataset; C7 restore and snapshot
under a held SQLite lock end within bounds; C8 exact missing-database check; C9 explicit
`--confirm` intent; C10 six concurrent restores; C11 8 databases x 25000 rows. Added in r2 (from M03 self-validation): C12 a symlinked
database fails health and is not snapshotted, and health fails while a finished swap still
has its journal; C13 an external flock on `.solaris-recovery.lock` makes restore and dry run
refuse with the dataset unchanged; C14 a restore killed after staging is discarded, not
rolled forward, with no leftover files; C15 a change to a table named `sqlitedata`, to
`user_version` or to `application_id` each fails health and restore brings it back. C14
patches `os.replace` through a `sitecustomize.py` on `PYTHONPATH`, so it needs a Python
candidate that writes `.solaris-recovery.json` with `os.replace`; any other candidate fails
it with a message that says so. POSIX only.
