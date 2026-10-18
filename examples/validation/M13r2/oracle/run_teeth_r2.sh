#!/bin/zsh
# Usage: zsh run_teeth_r2.sh PYTHON CANDIDATE_TREE MUTANT_DIR ORACLE_DIR OUT_DIR   (M13 run_teeth.sh without a positive control: no P1/P2 fix in M13 r2)
# m13_oracle, the builder oracle and the builder tests against candidate, positive control, stubs and every mutant.
P=$1; C=$2; M=$3; O=$4; R=$5; export PYTHONDONTWRITEBYTECODE=1
T=employees/data/data-engineer/csv_reconcile.py; B=examples/capabilities/G13/reconcile_oracle.py
cd $C
subjects=("candidate:$C/$T" "stub-noop:$O/stubs/noop_fake_clean.py" "stub-naive:$O/stubs/naive_sum.py" "builder-noop_stub:$C/examples/capabilities/G13/noop_stub.py" "builder-naive_stub:$C/examples/capabilities/G13/naive_stub.py")
for d in $M/*(/); do subjects+=("mutant-${d:t}:$d/csv_reconcile.py"); done
: > $R/oracle-teeth.txt; : > $R/builder-oracle-vs-teeth.txt; : > $R/builder-tests-vs-mutants.txt
for s in $subjects; do n=${s%%:*}; f=${s#*:}
  { echo "=== $n"; $P $O/m13_oracle.py -- $P $f 2>&1 | cut -c1-500; echo; } >> $R/oracle-teeth.txt
  { echo "=== $n"; $P $B --tool "$P $f" 2>&1 | grep -E "^(PASS|FAIL|[0-9]+/[0-9]+ checks)" | cut -c1-300; echo; } >> $R/builder-oracle-vs-teeth.txt
  case $n in stub-*|builder-*) continue;; esac
  W=/tmp/m13r2-tc/$n; rm -rf $W; mkdir -p $W; rsync -a --exclude .git $C/ $W/; cp $f $W/$T
  (cd $W && $P -m unittest tests.test_g13_capability > $W.log 2>&1); rc=$?
  echo "$n: rc=$rc $(grep -E '^(Ran|OK|FAILED)' $W.log | tr '\n' ' ')" >> $R/builder-tests-vs-mutants.txt; rm -rf $W $W.log
done
echo TEETH-DONE
