#!/bin/zsh
# M08 fresh caller (Grok self-validation): copy of the candidate tree (no .git), env -i with a new HOME, a PATH shim
# mapping python3 to the given Python, then only the commands in examples/capabilities/G08/README.md (Try it). Usage: PY TREE
P=$1; C=$2; F=/tmp/m08r2-fresh; rm -rf $F; mkdir -p $F/home $F/bin; rsync -a --exclude .git --exclude __pycache__ $C/ $F/repo/; ln -s $P $F/bin/python3
cat > $F/caller.sh <<'IN'
set -u; repo=$HOME/../repo
python3 $repo/examples/capabilities/G08/make_world.py $HOME/../g08-demo >/dev/null && cd $HOME/../g08-demo
T=$repo/employees/engineering/devops-engineer/local_deploy.py
x() { want=$1; shift; python3 $T "$@" >/dev/null 2>&1; rc=$?; echo "rc=$rc want=$want $([ $rc = $want ] && echo OK || echo MISMATCH) :: $*"; }
x 2 deploy plan-r1.json
x 0 deploy plan-r1.json --approval approval-r1.json
x 0 deploy plan-r2.json --approval approval-r2.json
x 1 deploy plan-r3-broken.json --approval approval-r3-broken.json
x 75 deploy plan-r3-broken.json --approval approval-r3-broken.json --fail-at migrated
x 2 deploy plan-r2.json --approval approval-r2.json
x 1 recover plan-r2.json
x 0 rollback plan-r2.json --approval approval-rollback-to-r1.json
python3 $T status plan-r2.json --json | python3 -c "import json,sys;d=json.load(sys.stdin);print('live',d['live'],'pending',d['pending'])"
python3 - <<'PY'
import sqlite3;c=sqlite3.connect("env/data/app.db");print("user_version",c.execute("PRAGMA user_version").fetchone()[0],"totals",[r[0] for r in c.execute("select total_cents from orders order by id")])
PY
IN
env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin /bin/bash $F/caller.sh
echo "python3 = $($F/bin/python3 -c 'import sys;print(sys.version.split()[0])'); pycache dirs left in the repo copy:"; find $F/repo -name __pycache__ | sed "s#$F/repo/##"
rm -rf $F
