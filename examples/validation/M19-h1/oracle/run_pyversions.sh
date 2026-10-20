#!/bin/zsh
# Full M19 oracle (core + adversarial + probe checks) and the candidate's test suite on each interpreter.
# Usage: zsh run_pyversions.sh CANDIDATE_TREE ORACLE_DIR RAW_DIR PY...
C=$1; O=$2; R=$3; shift 3
export PYTHONDONTWRITEBYTECODE=1
API=$C/employees/engineering/backend-developer/ledger_api.py; PR=$C/employees/quality-security/security-auditor/boundary_probe.py
: > $R/pyversions-matrix.txt
for py in "$@"; do
  v=$($py -c 'import sys;print(sys.version.split()[0])')
  { echo "# m19_oracle v2 on $v $(date '+%F %T %Z')"; cd /tmp; $py $O/m19_oracle.py --tmp $TMP --probe $PR -- $py $API; echo "[exit $?]"; } > $R/oracle-candidate-$v.txt 2>&1
  echo "=== $v" >> $R/pyversions-matrix.txt
  for pat in test_g19_capability.py 'test_[!g]*.py' 'test*.py'; do
    out=$(cd $C && $py -m unittest discover -s tests -p "$pat" 2>&1); rc=$?
    echo "  pattern $pat: rc=$rc $(echo $out | grep -E '^(Ran|OK|FAILED)' | tr '\n' ' ')" >> $R/pyversions-matrix.txt
  done
  echo "  candidate git status lines (worktree): $(git -C $C status --porcelain | wc -l | tr -d ' ')" >> $R/pyversions-matrix.txt
done
rm -rf $TMP/m19-oracle-run-*(N)
echo ALL-DONE
