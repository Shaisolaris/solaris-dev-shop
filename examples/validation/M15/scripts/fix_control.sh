#!/bin/zsh
# Positive control of the proposed fix (Grok self-validation): apply the patch to a fresh copy (never to the candidate),
# then run the documented commands, the builder tests, builder oracle and the M15 oracle on 3.9.6 and 3.13.15.
N=$1; C=$(mktemp -d /tmp/m15fc-XXXXXX); rsync -a --exclude .git /tmp/m15-eval/ $C/; cd $C && git apply $N/proposed-fix-allocation-drift.patch || { print -r -- "PATCH FAILED"; rm -rf $C; exit 1; }; print -r -- "patch applied: $(cd $C && grep -c allocation_by_week employees/data/data-scientist/experiment_readout.py) refs"
cd $C; T=employees/data/data-scientist/experiment_readout.py; O=examples/capabilities/G15
for PY in /usr/bin/python3 <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3; do
  V=$($PY -c 'import sys;print(sys.version.split()[0])')
  fx=""; for f in clean-aa retention-lift sample-ratio-mismatch; do fx="$fx $f=$(PYTHONDONTWRITEBYTECODE=1 $PY $T analyse $O/fixtures/$f/package.json --json | $PY -c 'import json,sys;d=json.load(sys.stdin);print(d["outcome"])')"; done
  g=$(PYTHONDONTWRITEBYTECODE=1 $PY -m unittest tests.test_g15_capability 2>&1 | tail -1); f=$(PYTHONDONTWRITEBYTECODE=1 $PY -m unittest discover -s tests 2>&1 | tail -1)
  bo=$(PYTHONDONTWRITEBYTECODE=1 $PY $O/readout_oracle.py -- $PY $T 2>&1 | tail -1)
  mo=$($PY $N/oracle/m15_oracle.py $C $N/results/fix-oracle-$V.json 2>&1 | grep -E 'X13|ORACLE' | cut -c1-260 | tr '\n' ' ')
  print -r -- "== $V | fixtures:$fx | g15: $g | full: $f | builder-oracle: $bo | m15: $mo"
done
cd /tmp; rm -rf $C
