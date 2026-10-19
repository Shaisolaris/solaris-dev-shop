#!/bin/zsh
# M33 matrix (Grok self-validation): on a private copy of the candidate, all four interpreters.
setopt null_glob
N=$1; SRC=/tmp/m33-eval; C=$(mktemp -d /tmp/m33mx-XXXXXX); rsync -a --exclude .git $SRC/ $C/
O=examples/capabilities/G33
for PY in /usr/bin/python3 <UV>/python/cpython-3.11.16-macos-aarch64-none/bin/python3 <PY312> <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3; do
  V=$($PY -c 'import sys;print(sys.version.split()[0])'); cd $C
  g=$(PYTHONDONTWRITEBYTECODE=1 $PY -m unittest tests.test_g33_capability 2>&1 | tail -3 | tr '\n' ' ')
  f=$(PYTHONDONTWRITEBYTECODE=1 $PY -m unittest discover -s tests 2>&1 | tail -3 | tr '\n' ' ')
  bo=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/evidence_oracle.py 2>&1 | tail -1)
  bn=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/evidence_oracle.py --tool $O/naive_decision.py 2>&1 | tail -1)
  bz=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/evidence_oracle.py --tool $O/noop_decision.py 2>&1 | tail -1)
  mo=$($PY $N/oracle/m33_oracle.py $C $N/results/oracle-$V.json 2>&1 | tail -1)
  mn=$($PY $N/oracle/m33_oracle.py $C $N/results/oracle-naive-$V.json --tool $C/$O/naive_decision.py 2>&1 | tail -1)
  mz=$($PY $N/oracle/m33_oracle.py $C $N/results/oracle-noop-$V.json --tool $C/$O/noop_decision.py 2>&1 | tail -1)
  print -r -- "== $V | g33: $g | full: $f | builder-oracle: $bo | builder-naive: $bn | builder-noop: $bz | m33-oracle: $mo | m33-naive: $mn | m33-noop: $mz"
done
cd /tmp; print -r -- "pycache in copy: $(find $C -name __pycache__ | wc -l | tr -d ' ')"; rm -rf $C
print -r -- "candidate status lines: $(git -C $SRC status --porcelain | wc -l | tr -d ' ')"
