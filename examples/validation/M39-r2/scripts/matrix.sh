#!/bin/zsh
# M39 r2 matrix (Grok self-validation): on a private copy of the candidate, all four interpreters.
setopt null_glob
N=$1; SRC=/tmp/m39r2-eval; C=$(mktemp -d /tmp/m39r2mx-XXXXXX); rsync -a --exclude .git $SRC/ $C/
O=examples/capabilities/G39
for PY in /usr/bin/python3 <UV>/python/cpython-3.11.16-macos-aarch64-none/bin/python3 <PY312> <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3; do
  V=$($PY -c 'import sys;print(sys.version.split()[0])'); cd $C
  g=$(PYTHONDONTWRITEBYTECODE=1 $PY -m unittest tests.test_g39_capability 2>&1 | tail -3 | tr '\n' ' ')
  PYTHONDONTWRITEBYTECODE=1 $PY -m unittest discover -s tests > $N/results/full-suite-$V.txt 2>&1
  f="$(tail -3 $N/results/full-suite-$V.txt | tr '\n' ' ') $(grep '^FAIL:\|^ERROR:' $N/results/full-suite-$V.txt | tr '\n' ' ')"
  dr=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/drill.py 2>&1 | tail -1)
  bo=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/drill_oracle.py 2>&1 | tail -1)
  bn=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/drill_oracle.py --tool $O/naive_evidence.py 2>&1 | tail -1)
  bz=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/drill_oracle.py --tool $O/noop_evidence.py 2>&1 | tail -1)
  mo=$($PY $N/oracle/m39_oracle.py $C $N/results/oracle-$V.json 2>&1 | tail -1)
  mn=$($PY $N/oracle/m39_oracle.py $C $N/results/oracle-naive-$V.json --tool $C/$O/naive_evidence.py 2>&1 | tail -1)
  mz=$($PY $N/oracle/m39_oracle.py $C $N/results/oracle-noop-$V.json --tool $C/$O/noop_evidence.py 2>&1 | tail -1)
  mc=$($PY $N/oracle/m39r2_contract.py $C $N/results/contract-$V.json 2>&1 | tail -1)
  mcn=$($PY $N/oracle/m39r2_contract.py $C $N/results/contract-naive-$V.json --tool $C/$O/naive_evidence.py 2>&1 | tail -1)
  print -r -- "== $V | m39r2-contract: $mc | contract-naive: $mcn | g39: $g | full: $f | drill: $dr | builder-oracle: $bo | builder-naive: $bn | builder-noop: $bz | m39-oracle: $mo | m39-naive: $mn | m39-noop: $mz"
done
cd /tmp; print -r -- "pycache in copy: $(find $C -name __pycache__ | wc -l | tr -d ' ')"; rm -rf $C
print -r -- "candidate status lines: $(git -C $SRC status --porcelain | wc -l | tr -d ' ')"
