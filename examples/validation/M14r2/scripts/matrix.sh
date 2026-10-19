#!/bin/zsh
# M14 r2 matrix (Grok self-validation): on a private copy of the candidate, all four interpreters.
setopt null_glob
N=$1; SRC=/tmp/m14r2-eval; C=$(mktemp -d /tmp/m14r2mx-XXXXXX); rsync -a --exclude .git $SRC/ $C/
T=employees/leadership/cfo/cash_revenue_reconcile.py; O=examples/capabilities/G14
for PY in /usr/bin/python3 <UV>/python/cpython-3.11.16-macos-aarch64-none/bin/python3 <PY312> <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3; do
  V=$($PY -c 'import sys;print(sys.version.split()[0])'); cd $C
  g=$(PYTHONDONTWRITEBYTECODE=1 $PY -m unittest tests.test_g14_capability 2>&1 | tail -3 | tr '\n' ' ')
  f=$(PYTHONDONTWRITEBYTECODE=1 $PY -m unittest discover -s tests 2>&1 | tail -3 | tr '\n' ' ')
  bo=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/cash_oracle.py -- $PY $T 2>&1 | tail -1)
  bn=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/cash_oracle.py -- $PY $O/naive_stub.py 2>&1 | tail -1)
  bz=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/cash_oracle.py -- $PY $O/noop_stub.py 2>&1 | tail -1)
  mo=$($PY $N/oracle/m14_oracle.py $C $N/results/oracle-$V.json 2>&1 | tail -1)
  mn=$($PY $N/oracle/m14_oracle.py $C --tool $C/$O/naive_stub.py $N/results/oracle-naive-$V.json 2>&1 | tail -1)
  mz=$($PY $N/oracle/m14_oracle.py $C --tool $C/$O/noop_stub.py $N/results/oracle-noop-$V.json 2>&1 | tail -1)
  ng=$($PY $N/oracle/m14r2_negative.py $C $N/results/negative-$V.json 2>&1 | tail -1)
  nn=$($PY $N/oracle/m14r2_negative.py $C $N/results/negative-naive-$V.json --tool $C/$O/naive_stub.py 2>&1 | tail -1)
  print -r -- "== $V | g14: $g | full: $f | builder-oracle: $bo | builder-naive: $bn | builder-noop: $bz | m14-oracle: $mo | m14-naive: $mn | m14-noop: $mz | negative: $ng | negative-naive: $nn"
done
cd /tmp; print -r -- "pycache in copy: $(find $C -name __pycache__ | wc -l | tr -d ' ')"; rm -rf $C
print -r -- "candidate status lines: $(git -C $SRC status --porcelain | wc -l | tr -d ' ')"
