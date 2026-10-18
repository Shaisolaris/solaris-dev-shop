#!/bin/zsh
# Fresh caller: a copy of the candidate tree (no .git), env -i with a new HOME, a PATH shim mapping
# python3 to the stated Python 3.12, and only the commands printed in sqlite-recovery.md.
# Usage: m03_fresh_caller.sh PYTHON CANDIDATE_TREE
P=$1; C=$2
F=/tmp/m03-fresh; rm -rf $F; mkdir -p $F/home $F/bin; rsync -a --exclude .git $C/ $F/repo/
ln -s $P $F/bin/python3
cat > $F/caller.sh <<'IN'
set -u
cd "$HOME/../repo"
T=employees/infrastructure/database-administrator/sqlite_recovery.py
echo "python3 = $(python3 -c 'import sys; print(sys.version.split()[0])'); HOME=$HOME; env vars: $(env | wc -l | tr -d ' ')"
mkdir -p data
python3 -c "
import sqlite3
c = sqlite3.connect('data/app.db'); c.execute('create table orders(id integer primary key, item text, qty int)')
c.executemany('insert into orders(item, qty) values (?,?)', [('apple', 1), ('pear', 2)]); c.commit(); c.close()
c = sqlite3.connect('data/audit.db'); c.execute('create table ev(id integer primary key, what)'); c.execute(\"insert into ev(what) values ('boot')\"); c.commit(); c.close()"
x() { echo "\$ $*"; "$@"; echo "[exit $?]"; }
echo "\$ python3 $T snapshot data/ --out snapshots/2026-10-18 --json   (literal doc command)"
python3 $T snapshot data/ --out snapshots/2026-10-18 --json; echo "[exit $?]"
echo "DEVIATION: the doc does not say the parent must exist; creating it: mkdir -p snapshots"
mkdir -p snapshots
python3 $T snapshot data/ --out snapshots/2026-10-18 --json > snap.json; echo "[exit $?]"; cat snap.json
SID=$(python3 -c "import json; print(json.load(open('snap.json'))['snapshot_id'])")
x python3 $T verify snapshots/2026-10-18 --expect app.db --expect audit.db
x python3 $T health data/ --expect app.db --expect audit.db --snapshot snapshots/2026-10-18
python3 -c "import sqlite3; c=sqlite3.connect('data/app.db'); c.execute(\"update orders set qty=99 where item='apple'\"); c.execute(\"insert into orders(item,qty) values ('mistake',0)\"); c.commit()"
x python3 $T health data/ --expect app.db --expect audit.db --snapshot snapshots/2026-10-18
x python3 $T restore data/ --snapshot snapshots/2026-10-18 --dry-run
x python3 $T restore data/ --snapshot snapshots/2026-10-18
x python3 $T restore data/ --snapshot snapshots/2026-10-18 --confirm $SID
x python3 $T health data/ --expect app.db --expect audit.db --snapshot snapshots/2026-10-18
echo "values now: $(python3 -c "import sqlite3; print(sqlite3.connect('data/app.db').execute('select item,qty from orders order by id').fetchall())")"
echo "dataset: $(ls -A data | tr '\n' ' ')"
echo "-- drill from the doc"
python3 -c "import sqlite3; c=sqlite3.connect('data/app.db'); c.execute(\"update orders set qty=7\"); c.commit()"
x python3 $T restore data/ --snapshot snapshots/2026-10-18 --confirm $SID --simulate-crash-after 1
x python3 $T health data/ --expect app.db --expect audit.db
x python3 $T recover data/
x python3 $T health data/ --expect app.db --expect audit.db --snapshot snapshots/2026-10-18
echo "values now: $(python3 -c "import sqlite3; print(sqlite3.connect('data/app.db').execute('select item,qty from orders order by id').fetchall())")"
echo "dataset: $(ls -A data | tr '\n' ' ')"
IN
env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin /bin/zsh -f $F/caller.sh 2>&1
rm -rf $F
