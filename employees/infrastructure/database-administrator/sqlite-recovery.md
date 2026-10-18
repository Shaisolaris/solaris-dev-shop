# Local SQLite recovery (sqlite_recovery.py)

For local, prototype or synthetic SQLite datasets: a directory with `*.db`, `*.sqlite` or
`*.sqlite3` files plus other files. Not for production databases, remote hosts or real
customer data without the owner's explicit approval. Stdlib Python 3.12, POSIX only.

```bash
T=employees/infrastructure/database-administrator/sqlite_recovery.py
python3 $T snapshot data/ --out snapshots/2026-10-18 --json     # prints snapshot_id
python3 $T verify snapshots/2026-10-18 --expect app.db --expect audit.db
python3 $T health data/ --expect app.db --expect audit.db [--snapshot snapshots/2026-10-18]
python3 $T restore data/ --snapshot snapshots/2026-10-18 --dry-run
python3 $T restore data/ --snapshot snapshots/2026-10-18 --confirm <snapshot_id>
python3 $T recover data/                                        # after a crash or kill
```
Exit 0 ok, 1 failed/unhealthy/busy, 2 refused or invalid. Add `--json` for the full result.

## What it guarantees
- **Explicit intent.** Restore runs only with `--confirm <snapshot_id>`. The plan (also shown
  by `--dry-run`) lists tables that differ and how many rows exist only in the live files.
  Freshness is never guessed from row counts.
- **Known good data kept.** Each replaced file and its `-wal`/`-shm`/`-journal` sidecars are
  renamed to `NAME.pre-restore-<snapshot_id>-<run>`, never deleted. A database whose values, schema and
  integrity already match the snapshot (and has no sidecar) is left in place. Other files in
  the dataset are untouched.
- **Verify before touch.** The snapshot directory must hold only regular, single-link files
  named in `manifest.json`; sha256, `integrity_check`, schema and per-table value digests must
  match. Symlinks, hard links, extra members, unsafe names and forged values are refused
  before any write. Verification opens copies read-only and immutable; nothing is extracted.
- **Dry run writes nothing**, not even a lock file.
- **One operation at a time.** snapshot, restore and recover hold an flock on
  `.solaris-recovery.lock`; the kernel releases it if the process dies.
- **Bounded waits.** `--lock-timeout` (default 5 s) bounds waits on a locked source or target;
  a busy database is reported, nothing changes.
- **Crash recovery.** Restore journals its renames in `.solaris-recovery.json`. `recover`
  reads the files actually present, then rolls forward when every staged copy verifies or
  rolls back to the original files. It does not need the snapshot. If the state cannot be
  explained it changes nothing and says so. `health` fails while a journal is open.
- **Repeatable.** Each run tags its renamed copies with a fresh run id, so restoring the same
  snapshot twice keeps both earlier copies.

## Drill
`restore ... --simulate-crash-after N` exits with code 137 right after the Nth rename, leaving
the real interrupted state; then run `health` (fails) and `recover`. Use only on disposable data.

## Limits
- Manifest hashes detect damage, not a determined forger with write access to the snapshot.
- Stop writers before restoring: a process that keeps an old file open keeps writing to the
  renamed copy. The lock probe refuses while another connection holds the database.
- Snapshot and restore of a WAL database may create `-wal`/`-shm` files next to the source.
- Single host, single filesystem per dataset (renames are not atomic across filesystems).
