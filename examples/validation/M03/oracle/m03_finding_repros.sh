#!/bin/zsh
# Exact repros for M03 findings. Usage: m03_finding_repros.sh PYTHON CANDIDATE_TREE [SYSTEM_PYTHON]
# Run from anywhere; works in a throwaway directory; exit codes captured via files, not pipes.
P=$1; C=$2; SP=${3:-/usr/bin/python3}; T=$C/employees/infrastructure/database-administrator/sqlite_recovery.py
W=$(mktemp -d /tmp/m03rep.XXXX); cd $W
x() { echo "\$ $*" | sed "s#$W#<tmp>#g"; "$@" > out.txt 2>&1; local rc=$?; sed "s#$W#<tmp>#g; s#/private<tmp>#<tmp>#g" out.txt | head -8; echo "[exit $rc]"; }
q() { $P -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute(sys.argv[2]).fetchall())" "$@"; }
fresh() { rm -rf ds snap snap2; mkdir ds; $P -c "
import sqlite3; c=sqlite3.connect('ds/app.db')
c.executescript(\"create table orders(id integer primary key, item); insert into orders(item) values ('a'),('b');\")
c.commit(); c.close()"; }

echo "### F1 user tables whose names match LIKE 'sqlite_%' are invisible to compare/health/restore"
fresh; q ds/app.db "select 1" >/dev/null
$P -c "import sqlite3; c=sqlite3.connect('ds/app.db'); c.executescript(\"create table sqlitedata(k,v); insert into sqlitedata values ('plan','GOOD'); create table SQLiteLog(m); insert into SQLiteLog values ('x');\"); c.commit()"
SID=$($P $T snapshot ds --out snap --json | $P -c "import json,sys; print(json.load(sys.stdin)['snapshot_id'])")
$P -c "import sqlite3; c=sqlite3.connect('ds/app.db'); c.executescript(\"update sqlitedata set v='LIVE-CHANGED'; delete from SQLiteLog;\"); c.commit()"
x $P $T health ds --expect app.db --snapshot snap
x $P $T restore ds --snapshot snap --confirm $SID
echo "sqlitedata after restore: $(q ds/app.db 'select * from sqlitedata')   SQLiteLog rows: $(q ds/app.db 'select count(*) from SQLiteLog')   (snapshot had GOOD / 1)"

echo; echo "### F2 user_version / application_id changes are not detected or restored"
fresh; SID=$($P $T snapshot ds --out snap --json | $P -c "import json,sys; print(json.load(sys.stdin)['snapshot_id'])")
$P -c "import sqlite3; c=sqlite3.connect('ds/app.db'); c.execute('pragma user_version=9'); c.execute('pragma application_id=77'); c.commit()"
x $P $T health ds --expect app.db --snapshot snap
x $P $T restore ds --snapshot snap --confirm $SID
echo "user_version/application_id after restore: $(q ds/app.db 'pragma user_version') $(q ds/app.db 'pragma application_id')  (snapshot had 0 0)"

echo; echo "### F3 stock macOS python3 (links Apple /usr/lib/libsqlite3 3.54.0): WAL databases cannot be snapshotted usably"
$SP -c "import sys,sqlite3; print('interpreter', sys.version.split()[0], 'sqlite', sqlite3.sqlite_version)"
echo "-- F3a quiescent WAL database (journal_mode=WAL, no open connection, so no -wal/-shm on disk)"
fresh; $SP -c "import sqlite3; c=sqlite3.connect('ds/app.db'); c.execute('pragma journal_mode=WAL'); c.close()"
echo "dataset: $(ls -A ds | tr '\n' ' ')"
x $SP $T snapshot ds --out snapA
x $SP $T health ds --expect app.db
echo "-- F3b WAL database with a live writer holding committed rows in -wal (the G03 test test_wal_source_and_sidecars_are_handled)"
fresh; $SP -c "
import sqlite3, subprocess, sys
c = sqlite3.connect('ds/app.db'); c.execute('pragma journal_mode=WAL'); c.close()
h = sqlite3.connect('ds/app.db'); h.execute(\"insert into orders(item) values ('in-wal')\"); h.commit()
subprocess.run([sys.executable, '$T', 'snapshot', 'ds', '--out', 'snapB'], stdout=subprocess.DEVNULL)
h.close()"
echo "snapshot dir: $(ls -A snapB | tr '\n' ' ')"
x $SP $T verify snapB
SID=$($SP -c "import json; print(json.load(open('snapB/manifest.json'))['snapshot_id'])")
x $SP $T restore ds --snapshot snapB --confirm $SID --dry-run
echo "-- control: the same two cases on the stated Python 3.12 (bundled SQLite 3.53.1)"
fresh; $P -c "import sqlite3; c=sqlite3.connect('ds/app.db'); c.execute('pragma journal_mode=WAL'); c.close()"
x $P $T snapshot ds --out snapC
echo; echo "### F4 health without --snapshot calls a 0-byte or emptied expected DB healthy"
fresh; : > ds/app.db; x $P $T health ds --expect app.db
fresh; $P -c "import sqlite3; c=sqlite3.connect('ds/app.db'); c.execute('drop table orders'); c.commit()"; x $P $T health ds --expect app.db

echo; echo "### F5 health --snapshot tracebacks on a manifest entry without 'tables' (verify/restore refuse cleanly)"
fresh; SID=$($P $T snapshot ds --out snap --json | $P -c "import json,sys; print(json.load(sys.stdin)['snapshot_id'])")
$P -c "import json; m=json.load(open('snap/manifest.json')); del m['databases']['app.db']['tables']; json.dump(m, open('snap/manifest.json','w'))"
x $P $T verify snap
x $P $T health ds --expect app.db --snapshot snap

echo; echo "### F6 the first documented command fails when snapshots/ does not exist yet"
fresh; x $P $T snapshot ds --out snapshots/2026-10-18 --json

echo; echo "### F7 cosmetic: --lock-timeout nan accepted; health on a locked DB reports 'unreadable as SQLite'"
fresh; SID=$($P $T snapshot ds --out snap --json | $P -c "import json,sys; print(json.load(sys.stdin)['snapshot_id'])")
x $P $T restore ds --snapshot snap --confirm $SID --dry-run --lock-timeout nan
$P -c "import sqlite3,time; c=sqlite3.connect('ds/app.db', isolation_level=None); c.execute('BEGIN EXCLUSIVE'); print('held', flush=True); time.sleep(12)" > held.txt &
HP=$!; sleep 1; x $P $T health ds --expect app.db; kill $HP 2>/dev/null; wait $HP 2>/dev/null
cd /; rm -rf $W
