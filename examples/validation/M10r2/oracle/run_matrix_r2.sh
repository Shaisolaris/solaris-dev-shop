#!/bin/zsh
# M10 r2 cross-interpreter runs. Usage: zsh run_matrix_r2.sh TREE M10_ORACLE_DIR RAW_DIR PY_MAIN PY_OTHER...
# Writes oracle-cross-interpreter.txt (M10 oracle under each), adversarial-candidate.txt (main + --pythons others),
# pyversions-matrix.txt (G10 / original / full suites per interpreter).
C=$1; O=$2; R=$3; PM=$4; shift 4; export PYTHONDONTWRITEBYTECODE=1
T=$C/employees/infrastructure/network-engineer/netdiag.py; cd /tmp
: > $R/oracle-cross-interpreter.txt
for py in $PM "$@"; do echo "== oracle under Python $($py -c 'import platform;print(platform.python_version())')" >> $R/oracle-cross-interpreter.txt
  $py $O/m10_oracle.py -- $py $T 2>&1 | grep -E "^(FAIL|SUMMARY)" >> $R/oracle-cross-interpreter.txt; done
others=${(j:,:)@}
{ echo "# m10_adversarial on $($PM -c 'import platform;print(platform.python_version())') with --pythons $(for p in "$@"; do $p -c 'import platform;print(platform.python_version())'; done | tr '\n' ' ')$(date '+%F %T %Z')"; $PM $O/m10_adversarial.py --pythons $others -- $PM $T 2>&1; } > $R/adversarial-candidate.txt
{ echo "commit $(git -C $C rev-parse HEAD) status-lines $(git -C $C status --porcelain | wc -l | tr -d ' ')"
for py in $PM "$@"; do v=$($py -c 'import platform,sqlite3;print(platform.python_version()+"_sqlite"+sqlite3.sqlite_version)'); line="== $v "
  for pat in g10:test_g10_capability.py 'original:test_[!g]*.py' 'full:test*.py'; do n=${pat%%:*}; p=${pat#*:}
    out=$(cd $C && $py -m unittest discover -s tests -p "$p" 2>&1); rc=$?; line+=" $n rc=$rc $(echo $out | grep -E '^(Ran|OK|FAILED)' | tr '\n' ' ')|"; done
  echo $line; done
echo "after: status-lines $(git -C $C status --porcelain | wc -l | tr -d ' ')"; } > $R/pyversions-matrix.txt
echo MATRIX-DONE
