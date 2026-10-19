#!/bin/zsh
# M13 r3 cross-interpreter runs. Usage: zsh run_matrix_r2.sh TREE M13_ORACLE_DIR RAW_DIR PY_MAIN PY39 PY_OTHER...
# finding-repros.txt; oracle-cross-interpreter.txt (M13 oracle under each); adversarial-candidate.txt (main +
# --pythons others); pyversions-matrix.txt (G13 / original / full suites per interpreter).
C=$1; O=$2; R=$3; PM=$4; P39=$5; shift 5; export PYTHONDONTWRITEBYTECODE=1
T=$C/employees/data/data-engineer/csv_reconcile.py; cd /tmp
{ echo "# M13 finding repros on r3 $(date '+%F %T %Z')"; $PM $O/m13_finding_repros.py $PM $P39 $T 2>&1; } > $R/finding-repros.txt
: > $R/oracle-cross-interpreter.txt
for py in $PM $P39 "$@"; do echo "== oracle with candidate under Python $($py -c 'import platform;print(platform.python_version())')" >> $R/oracle-cross-interpreter.txt
  $py $O/m13_oracle.py -- $py $T 2>&1 | grep -E "^(FAIL|SUMMARY)" >> $R/oracle-cross-interpreter.txt; done
others=$P39; for p in "$@"; do others+=",$p"; done
{ echo "# m13_adversarial on $($PM -c 'import platform;print(platform.python_version())') with --pythons $others $(date '+%F %T %Z')"; $PM $O/m13_adversarial.py --pythons $others -- $PM $T 2>&1; } > $R/adversarial-candidate.txt
{ echo "commit $(git -C $C rev-parse HEAD) status-lines $(git -C $C status --porcelain | wc -l | tr -d ' ')"
for py in $PM $P39 "$@"; do v=$($py -c 'import platform,sqlite3;print(platform.python_version()+"_sqlite"+sqlite3.sqlite_version)'); line="== $v "
  for pat in g13:test_g13_capability.py 'original:test_[!g]*.py' 'full:test*.py'; do n=${pat%%:*}; p=${pat#*:}
    out=$(cd $C && $py -m unittest discover -s tests -p "$p" 2>&1); rc=$?; line+=" $n rc=$rc $(echo $out | grep -E '^(Ran|OK|FAILED)' | tr '\n' ' ')|"; done
  echo $line; done
echo "after: status-lines $(git -C $C status --porcelain | wc -l | tr -d ' ')"; } > $R/pyversions-matrix.txt
echo MATRIX-DONE
