#!/bin/zsh
# Usage: zsh run_teeth_r2.sh PYTHON CANDIDATE_TREE MUTANT_DIR R1_FILE ORACLE_DIR OUT_DIR
# m03_oracle, the builder oracle (recovery_oracle.py) and the builder tests against the r2 candidate,
# the r1 tool, four stubs, the 15 M03 mutants and the builder's 8 r2 mutants.
P=$1; C=$2; M=$3; R1=$4; O=$5; R=$6; export PYTHONDONTWRITEBYTECODE=1
T=employees/infrastructure/database-administrator/sqlite_recovery.py; B=examples/capabilities/G03/recovery_oracle.py
cd $C
subjects=("candidate:$C/$T" "r1-7c63297:$R1" "stub-noop:$O/stubs/noop_echo.py" "stub-naive:$O/stubs/naive_copier.py" "builder-noop_stub:$C/examples/capabilities/G03/noop_stub.py" "builder-naive_stub:$C/examples/capabilities/G03/naive_stub.py")
for d in $M/*(/); do subjects+=("mutant-${d:t}:$d/sqlite_recovery.py"); done
: > $R/oracle-teeth.txt; : > $R/builder-oracle-vs-teeth.txt; : > $R/builder-tests-vs-mutants.txt
for s in $subjects; do n=${s%%:*}; f=${s#*:}
  { echo "=== $n"; $P $O/m03_oracle.py -- $P $f 2>&1 | cut -c1-400; echo; } >> $R/oracle-teeth.txt
  { echo "=== $n"; $P $B -- $P $f 2>&1 | grep -E "^(PASS|FAIL|SKIP|SUMMARY|[0-9]+/[0-9]+)" | cut -c1-300; echo; } >> $R/builder-oracle-vs-teeth.txt
  case $n in stub-*|builder-*) continue;; esac
  W=/tmp/m03r2-tc/$n; rm -rf $W; mkdir -p $W; rsync -a --exclude .git $C/ $W/; cp $f $W/$T
  (cd $W && $P -m unittest discover -s tests -p test_g03_capability.py > $W.log 2>&1); rc=$?
  echo "$n: rc=$rc $(grep -E '^(Ran|OK|FAILED)' $W.log | tr '\n' ' ')" >> $R/builder-tests-vs-mutants.txt; rm -rf $W $W.log
done
echo TEETH-DONE
