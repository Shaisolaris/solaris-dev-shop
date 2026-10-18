#!/bin/zsh
# Usage: run_builder_tests_vs_mutants.sh PYTHON CANDIDATE_TREE MUTANT_DIR FIXED_FILE
# Copies the candidate tree (no .git) once per variant, drops the variant's sqlite_recovery.py in,
# and runs the builder's tests/test_g03_capability.py. A mutant "survives" if the tests still pass.
P=$1; C=$2; M=$3; FX=$4; export PYTHONDONTWRITEBYTECODE=1
W=/tmp/m03-tc; rm -rf $W; mkdir -p $W
T=employees/infrastructure/database-administrator/sqlite_recovery.py
one() {
  local name=$1 file=$2 d=$W/$1
  rsync -a --exclude .git $C/ $d/
  cp $file $d/$T
  (cd $d && $P -m unittest tests.test_g03_capability > $W/$name.log 2>&1)
  local rc=$?
  echo "$name: rc=$rc $(grep -E '^(Ran|OK|FAILED)' $W/$name.log | tr '\n' ' ')"
  rm -rf $d
}
one candidate $C/$T
one positive-control-proposed-fix $FX
for m in $M/*(/); do one mutant-${m:t} $m/sqlite_recovery.py; done
