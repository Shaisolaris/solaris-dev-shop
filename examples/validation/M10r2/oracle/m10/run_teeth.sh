#!/bin/zsh
# Usage: run_teeth.sh PYTHON CANDIDATE_TREE MUTANT_DIR FIXED_FILE ORACLE_DIR OUT_DIR
# m10_oracle, the builder oracle and the builder tests against candidate, positive control, stubs and every mutant.
P=$1; C=$2; M=$3; FX=$4; O=$5; R=$6; export PYTHONDONTWRITEBYTECODE=1
T=employees/infrastructure/network-engineer/netdiag.py; B=examples/capabilities/G10/diagnosis_oracle.py
cd $C
subjects=("candidate:$C/$T" "positive-control-proposed-fix:$FX" "stub-noop:$O/stubs/noop_echo.py" "stub-naive:$O/stubs/naive_first_failure.py" "builder-noop_stub:$C/examples/capabilities/G10/noop_stub.py" "builder-naive_stub:$C/examples/capabilities/G10/naive_stub.py")
for d in $M/*(/); do subjects+=("mutant-${d:t}:$d/netdiag.py"); done
: > $R/oracle-teeth.txt; : > $R/builder-oracle-vs-teeth.txt; : > $R/builder-tests-vs-mutants.txt
for s in $subjects; do n=${s%%:*}; f=${s#*:}
  { echo "=== $n"; $P $O/m10_oracle.py -- $P $f 2>&1 | cut -c1-400; echo; } >> $R/oracle-teeth.txt
  { echo "=== $n"; $P $B -- $P $f 2>&1 | cut -c1-300; echo; } >> $R/builder-oracle-vs-teeth.txt
  case $n in stub-*|builder-*) continue;; esac
  W=/tmp/m10-tc/$n; rm -rf $W; mkdir -p $W; rsync -a --exclude .git $C/ $W/; cp $f $W/$T
  (cd $W && $P -m unittest tests.test_g10_capability > $W.log 2>&1); rc=$?
  echo "$n: rc=$rc $(grep -E '^(Ran|OK|FAILED)' $W.log | tr '\n' ' ')" >> $R/builder-tests-vs-mutants.txt; rm -rf $W
done
echo TEETH-DONE
