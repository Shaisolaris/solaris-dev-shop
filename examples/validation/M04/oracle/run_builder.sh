#!/bin/zsh
# M04 builder-suite runner (Grok self-validation): per interpreter, on a no-.git copy of the candidate, G04 tests, full suite, builder oracle and controls.
R=$1; C=$2; shift 2; export PYTHONDONTWRITEBYTECODE=1; mkdir -p $R
for py in $@; do v=$($py -c 'import sys;print(sys.version.split()[0])'); f=$R/builder-$v.txt; S=/tmp/m04-suite-$v; rm -rf $S; rsync -a --exclude .git $C/ $S/; cd $S
  echo "== builder $v $(date '+%F %T %Z')" > $f
  for pat in test_g04_capability.py 'test*.py'; do $py -m unittest discover -s tests -p "$pat" > $S.log 2>&1; echo "suite $pat: rc=$? $(grep -E '^(Ran|OK|FAILED)' $S.log | sed -E 's/ in [0-9.]+s//' | tr '\n' ' ')" >> $f; done
  $py examples/capabilities/G04/handoff_oracle.py --help > $S.h 2>&1; echo "--- oracle help: $(head -3 $S.h | tr '\n' ' ')" >> $f
  $py examples/capabilities/G04/handoff_oracle.py > $S.o 2>&1; echo "--- builder oracle rc=$?" >> $f; tail -3 $S.o >> $f
  cd /tmp; rm -rf $S $S.log $S.h $S.o
done; echo BUILDER-DONE
