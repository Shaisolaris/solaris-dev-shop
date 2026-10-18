#!/bin/zsh
# Usage: zsh run_pyversions_r2.sh ORACLE_DIR RAW_DIR TREE MUTANT_DIR PY39 PY311 PY312 PY313
O=$1; R=$2; C=$3; M=$4; S=$5; P11=$6; P=$7; P13=$8; export PYTHONDONTWRITEBYTECODE=1
T=employees/infrastructure/database-administrator/sqlite_recovery.py; B=examples/capabilities/G03/recovery_oracle.py; cd $C
: > $R/oracle-pyversions.txt
for py in $S $P11 $P13; do echo "=== m03_oracle on $($py -c 'import sys,sqlite3;print(sys.version.split()[0],"sqlite",sqlite3.sqlite_version)')" >> $R/oracle-pyversions.txt
  $py $O/m03_oracle.py -- $py $C/$T >> $R/oracle-pyversions.txt 2>&1; echo "[exit $?]" >> $R/oracle-pyversions.txt; done
echo "=== builder oracle on 3.9.6" >> $R/oracle-pyversions.txt; $S $B -- $S $C/$T 2>&1 | grep -E "^(PASS|FAIL|SUMMARY)" >> $R/oracle-pyversions.txt
: > $R/f3-mutants-py39.txt
for m in r2_f3_no_ro_fallback r2_f3_copy_keeps_sidecars; do
  echo "=== $m: m03_oracle on 3.9.6" >> $R/f3-mutants-py39.txt; $S $O/m03_oracle.py -- $S $M/$m/sqlite_recovery.py 2>&1 | grep -E "^(FAIL|SUMMARY)" | cut -c1-300 >> $R/f3-mutants-py39.txt
  echo "=== $m: builder oracle on 3.9.6" >> $R/f3-mutants-py39.txt; $S $B -- $S $M/$m/sqlite_recovery.py 2>&1 | grep -E "^(FAIL|SUMMARY)" | cut -c1-300 >> $R/f3-mutants-py39.txt
  W=/tmp/m03r2-tc/$m; rm -rf $W; mkdir -p $W; rsync -a --exclude .git $C/ $W/; cp $M/$m/sqlite_recovery.py $W/$T
  (cd $W && $S -m unittest discover -s tests -p test_g03_capability.py > $W.log 2>&1); echo "$m builder tests 3.9.6: rc=$? $(grep -E '^(Ran|OK|FAILED|FAIL:|ERROR:)' $W.log | tr '\n' ' ')" >> $R/f3-mutants-py39.txt; rm -rf $W $W.log
done
: > $R/builder-oracle-no_dataset_flock-repeats.txt
for i in 1 2 3 4 5; do for py in $P $S; do echo "run $i $($py -c 'import sys;print(sys.version.split()[0])'): $($py $B -- $py $M/no_dataset_flock/sqlite_recovery.py 2>&1 | grep -E '^(SUMMARY|FAIL)' | tr '\n' ' ' | cut -c1-300)" >> $R/builder-oracle-no_dataset_flock-repeats.txt; done; done
echo PYV-DONE
