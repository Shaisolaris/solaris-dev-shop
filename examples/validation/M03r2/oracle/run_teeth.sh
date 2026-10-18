#!/bin/zsh
# Usage: run_teeth.sh PYTHON CANDIDATE_TREE MUTANT_DIR FIXED_FILE ORACLE_DIR
# Runs m03_oracle.py against the candidate, a positive control (proposed fix), two stubs and every mutant.
P=$1; C=$2; M=$3; FX=$4; O=$5; export PYTHONDONTWRITEBYTECODE=1
cd $C
run() { echo "=== $1"; shift; $P $O/m03_oracle.py -- "$@" 2>&1 | cut -c1-400; echo; }
run candidate $P employees/infrastructure/database-administrator/sqlite_recovery.py
run positive-control-proposed-fix $P $FX
run stub-noop $P $O/stubs/noop_echo.py
run stub-naive $P $O/stubs/naive_copier.py
for d in $M/*(/); do run mutant-${d:t} $P $d/sqlite_recovery.py; done
