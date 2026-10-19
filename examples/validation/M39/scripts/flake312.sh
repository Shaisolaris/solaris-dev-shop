#!/bin/zsh
# M39: try to reproduce the open 3.12 one-off suite failure under load. 4 parallel full-suite runs per round,
# each in its own rsync copy of the candidate, full unittest output kept.
N=<D>/grok-output/M39
P312=<PY312>
ROUNDS=${1:-2}
for r in $(seq 1 $ROUNDS); do
  for i in 1 2 3 4; do
    d=/tmp/m39fl-$r-$i; rm -rf $d; rsync -a --exclude .git /tmp/m39-eval/ $d/
    ( cd $d && PYTHONDONTWRITEBYTECODE=1 $P312 -m unittest discover -s tests > $N/results/flake/py312-r$r-$i.txt 2>&1; echo "exit $?" >> $N/results/flake/py312-r$r-$i.txt; rm -rf $d ) &
  done
  wait
done
echo FLAKE-DONE
