#!/bin/zsh
# M34 (Grok self-validation): builder suite, oracle and controls on a no-.git copy per interpreter. Usage: TREE OUTDIR PY...
T=$1; OUT=$2; shift 2; mkdir -p $OUT
for py in "$@"; do v=$($py -c 'import platform;print(platform.python_version())'); S=/tmp/m34-suite-$v; rm -rf $S; rsync -a --exclude .git $T/ $S/; cd $S
 { echo "=== $v $(date '+%H:%M:%S %Z')"
   echo "\$ diag_oracle.py"; $py examples/capabilities/G34/diag_oracle.py 2>&1 | tail -3; echo "[exit $pipestatus[1]]"
   echo "\$ unittest tests.test_g34_capability"; $py -m unittest tests.test_g34_capability 2>&1 | tail -3
   echo "\$ full suite"; $py -m unittest discover -s tests -p 'test*.py' 2>&1 | tail -3
   echo "snapshot tree unchanged: $(git -C $T diff --quiet de76fae -- examples/capabilities/G34 && echo yes)"; } > $OUT/builder-$v.txt 2>&1
 cd /tmp; rm -rf $S; done; echo BUILDER-DONE
