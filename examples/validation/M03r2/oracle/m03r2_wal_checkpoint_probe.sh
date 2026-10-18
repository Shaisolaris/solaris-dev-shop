#!/bin/zsh
# R1 probe: a WAL database whose committed rows live only in -wal, with no -shm on disk (a file-level
# copy taken while a writer was connected). Does a read-only command (health, snapshot) change the
# live main file? Usage: zsh m03r2_wal_checkpoint_probe.sh PYTHON TOOL
X=$1; S=$2; W=$(mktemp -d /tmp/m03r2wal.XXXX); cd $W
$X -c "import sys,sqlite3; print('python', sys.version.split()[0], 'sqlite', sqlite3.sqlite_version)"
mk() { rm -rf src ds snap; mkdir src ds; $X - <<'PY'
import sqlite3, shutil, os
c = sqlite3.connect('src/app.db'); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA wal_autocheckpoint=0')
c.execute('create table t(id integer primary key, v)'); c.execute("insert into t values (1,'base')"); c.commit()
c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
c.execute("insert into t values (2,'only-in-wal')"); c.commit()
shutil.copy('src/app.db', 'ds/app.db'); shutil.copy('src/app.db-wal', 'ds/app.db-wal')
c.close()
PY
}
st() { echo "  main sha $(shasum -a 256 ds/app.db | cut -c1-16) size $(stat -f %z ds/app.db); files: $(ls ds | tr '\n' ' ')$( [ -e ds/app.db-wal ] && echo "; -wal $(stat -f %z ds/app.db-wal) bytes")"; }
for cmd in health snapshot; do
  mk; echo "== $cmd"; echo " before:"; st
  if [ $cmd = health ]; then $X $S health ds --expect app.db > out.txt 2>&1; else $X $S snapshot ds --out snap > out.txt 2>&1; fi; echo " [exit $?] $(head -2 out.txt | tr '\n' ' ' | cut -c1-160)"
  echo " after:"; st
  [ $cmd = snapshot ] && $X -c "import sqlite3; print('  snapshot copy rows:', sqlite3.connect('file:snap/app.db?mode=ro&immutable=1', uri=True).execute('select * from t order by id').fetchall())"
  $X -c "import sqlite3; print('  rows now visible:', sqlite3.connect('file:ds/app.db?mode=ro&immutable=1', uri=True).execute('select * from t order by id').fetchall(), '(main file alone, immutable)')"
done
cd /; rm -rf $W
