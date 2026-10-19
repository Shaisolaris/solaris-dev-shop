#!/bin/zsh
# M11 r3 matrix (Grok self-validation): on a private copy of the candidate, all four interpreters.
setopt null_glob
N=$1; SRC=/tmp/m11r3-eval; C=$(mktemp -d /tmp/m11r3mx-XXXXXX); rsync -a --exclude .git $SRC/ $C/
T=employees/infrastructure/site-reliability-engineer/incident_slo.py; O=examples/capabilities/G11
for PY in /usr/bin/python3 <UV>/python/cpython-3.11.16-macos-aarch64-none/bin/python3 <PY312> <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3; do
  V=$($PY -c 'import sys;print(sys.version.split()[0])'); cd $C
  g=$(PYTHONDONTWRITEBYTECODE=1 $PY -m unittest tests.test_g11_capability 2>&1 | tail -3 | tr '\n' ' ')
  f=$(PYTHONDONTWRITEBYTECODE=1 $PY -m unittest discover -s tests 2>&1 | tail -3 | tr '\n' ' ')
  bo=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/incident_oracle.py -- $PY $T 2>&1 | tail -1)
  bn=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/incident_oracle.py -- $PY $O/naive_stub.py 2>&1 | tail -1)
  bz=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/incident_oracle.py -- $PY $O/noop_stub.py 2>&1 | tail -1)
  mo=$($PY $N/oracle/m11_oracle.py $C $N/results/oracle-$V.json 2>&1 | tail -1)
  mn=$($PY $N/oracle/m11_oracle.py $C --tool $C/$O/naive_stub.py $N/results/oracle-naive-$V.json 2>&1 | tail -1)
  mz=$($PY $N/oracle/m11_oracle.py $C --tool $C/$O/noop_stub.py $N/results/oracle-noop-$V.json 2>&1 | tail -1)
  so=$($PY $N/oracle/m11r2_sources.py $C $N/results/sources-$V.json 2>&1 | tail -1)
  sn=$($PY $N/oracle/m11r2_sources.py $C $N/results/sources-naive-$V.json --tool $C/$O/naive_stub.py 2>&1 | tail -1)
  to=$($PY $N/oracle/m11r3_sources.py $C $N/results/r3sources-$V.json 2>&1 | tail -1)
  tn=$($PY $N/oracle/m11r3_sources.py $C $N/results/r3sources-naive-$V.json --tool $C/$O/naive_stub.py 2>&1 | tail -1)
  tz=$($PY $N/oracle/m11r3_sources.py $C $N/results/r3sources-noop-$V.json --tool $C/$O/noop_stub.py 2>&1 | tail -1)
  print -r -- "== $V | g11: $g | full: $f | builder-oracle: $bo | builder-naive: $bn | builder-noop: $bz | m11-oracle: $mo | m11-naive: $mn | m11-noop: $mz | sources: $so | sources-naive: $sn | r3-sources: $to | r3-sources-naive: $tn | r3-sources-noop: $tz"
done
cd /tmp; print -r -- "pycache in copy: $(find $C -name __pycache__ | wc -l | tr -d ' ')"; rm -rf $C
print -r -- "candidate status lines: $(git -C $SRC status --porcelain | wc -l | tr -d ' ')"
