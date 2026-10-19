#!/bin/zsh
# M08 single-deployer probe (Grok self-validation): r2 live, then the live data's schema version is changed outside the tool
# (as a stray writer would); does a repeat deploy of r2 report success without a health check? Usage: PY TREE
P=$1; C=$2; W=/tmp/m08-rep/w; rm -rf /tmp/m08-rep; export PYTHONDONTWRITEBYTECODE=1
$P $C/examples/capabilities/G08/make_world.py $W >/dev/null; cd $W; T=$C/employees/engineering/devops-engineer/local_deploy.py
$P $T deploy plan-r1.json --approval approval-r1.json >/dev/null; $P $T deploy plan-r2.json --approval approval-r2.json >/dev/null; echo "r2 deployed rc=$?"
$P -c "import sqlite3;c=sqlite3.connect('env/data/app.db');c.execute('PRAGMA user_version=3');c.commit()"
$P $T preflight plan-r2.json --approval approval-r2.json >/dev/null 2>&1; echo "preflight r2 rc=$? (health should fail)"
$P $T deploy plan-r2.json --approval approval-r2.json; echo "repeat deploy r2 rc=$?"
$P $T deploy plan-r2.json; echo "repeat deploy r2 with NO approval rc=$?"
$P $T status plan-r2.json --json | $P -c "import json,sys;d=json.load(sys.stdin);print('status live',d['live'],'pending',d['pending'])"
cd /tmp; rm -rf /tmp/m08-rep
