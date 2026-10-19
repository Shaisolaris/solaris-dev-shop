#!/bin/zsh
# Usage: zsh run_baseline_r3.sh ORACLE_DIR RAW_DIR TREE PY39 PY311 PY312 PY313
O=$1; R=$2; C=$3; export PYTHONDONTWRITEBYTECODE=1; shift 3
T=employees/infrastructure/database-administrator/sqlite_recovery.py; B=examples/capabilities/G03/recovery_oracle.py; cd $C
: > $R/pyversions-matrix.txt; : > $R/oracle-pyversions.txt
for py in "$@"; do v=$($py -c 'import sys,sqlite3;print(sys.version.split()[0],"sqlite",sqlite3.sqlite_version)')
  $py -m unittest discover -s tests > $R/full-suite-${v%% *}.log 2>&1; echo "$v full suite rc=$? $(grep -E '^(Ran|OK|FAILED)' $R/full-suite-${v%% *}.log | tr '\n' ' ')" >> $R/pyversions-matrix.txt
  echo "=== m03_oracle on $v" >> $R/oracle-pyversions.txt; $py $O/m03_oracle.py -- $py $C/$T >> $R/oracle-pyversions.txt 2>&1; echo "[exit $?]" >> $R/oracle-pyversions.txt
  echo "=== builder oracle on $v" >> $R/oracle-pyversions.txt; $py $B -- $py $C/$T 2>&1 | grep -E "^(PASS|FAIL|SKIP|SUMMARY)" >> $R/oracle-pyversions.txt
done
echo BASELINE-DONE
