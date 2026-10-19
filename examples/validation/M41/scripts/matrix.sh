#!/bin/zsh
# M41 matrix (Grok self-validation): a private copy of the candidate, all four interpreters.
setopt null_glob
N=$1; SRC=/tmp/m41-eval; C=$(mktemp -d /tmp/m41mx-XXXXXX); rsync -a --exclude .git $SRC/ $C/
O=examples/capabilities/G41
for PY in /usr/bin/python3 <UV>/python/cpython-3.11.16-macos-aarch64-none/bin/python3 <PY312> <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3; do
  V=$($PY -c 'import sys;print(sys.version.split()[0])'); cd $C
  g=$(PYTHONDONTWRITEBYTECODE=1 $PY -m unittest tests.test_g41_capability 2>&1 | tail -1)
  PYTHONDONTWRITEBYTECODE=1 $PY -m unittest discover -s tests > $N/results/full-suite-$V.txt 2>&1
  f="$(tail -3 $N/results/full-suite-$V.txt | tr '\n' ' ') $(grep '^FAIL:\|^ERROR:' $N/results/full-suite-$V.txt | tr '\n' ' ')"
  bo=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/inventory_oracle.py 2>&1 | tail -1)
  bn=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/inventory_oracle.py --tool $O/naive_inventory.py 2>&1 | tail -1)
  bz=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/inventory_oracle.py --tool $O/noop_inventory.py 2>&1 | tail -1)
  mo=$($PY $N/oracle/m41_oracle.py $C $N/results/oracle-$V.json 2>&1 | tail -1)
  print -r -- "== $V | g41: $g | full: $f | builder-oracle: $bo | builder-naive: $bn | builder-noop: $bz | m41-oracle: $mo | pycache in copy: $(find $C -name __pycache__ | wc -l | tr -d ' ') | build/egg-info in copy: $(ls -d $C/build $C/*.egg-info | wc -l | tr -d ' ')"
done
cd /tmp; rm -rf $C
print -r -- "candidate status lines: $(git -C $SRC status --porcelain | wc -l | tr -d ' ')"
