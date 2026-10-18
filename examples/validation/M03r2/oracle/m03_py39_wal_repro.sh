#!/bin/zsh
# Repro for the G03 WAL snapshot portability failure. Usage: m03_py39_wal_repro.sh PYTHON TOOL
X=$1; S=$2; T=$(mktemp -d /tmp/m03wal.XXXX); cd $T; mkdir ds
$X -c "import sys,sqlite3; print('python', sys.version.split()[0], 'sqlite', sqlite3.sqlite_version)"
$X - <<'PY'
import sqlite3, subprocess, sys, json
S = sys.argv[0]
c = sqlite3.connect('ds/app.db'); c.execute('PRAGMA journal_mode=WAL'); c.execute('create table customers(id integer primary key, name)')
c.execute("insert into customers values (1,'original')"); c.commit(); c.close()
holder = sqlite3.connect('ds/app.db'); holder.execute("insert into customers values (2,'in-wal')"); holder.commit()
import os; tool = os.environ['TOOL']
p = subprocess.run([sys.executable, tool, 'snapshot', 'ds', '--out', 'snap', '--json'], capture_output=True, text=True)
print('snapshot rc', p.returncode, json.loads(p.stdout).get('messages'))
holder.close()
p = subprocess.run([sys.executable, tool, 'verify', 'snap'], capture_output=True, text=True)
print('verify rc', p.returncode, p.stdout.strip())
print('snap files', sorted(os.listdir('snap')))
PY
cd /; rm -rf $T
