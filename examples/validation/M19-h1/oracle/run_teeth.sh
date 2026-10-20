#!/bin/zsh
# M19 teeth: the M19 oracle (core checks only), the builder oracle and the builder tests against the
# candidate, the M19 stubs, the builder stubs and every mutant.
# Usage: [ONLY_M19=1] zsh run_teeth.sh PY CANDIDATE_TREE MUTANT_DIR ORACLE_DIR RAW_DIR   (ONLY_M19 reruns only the M19 oracle)
PY=$1; TREE=$2; MD=$3; O=$4; R=$5
API=employees/engineering/backend-developer/ledger_api.py
EX=examples/capabilities/G19
export PYTHONDONTWRITEBYTECODE=1 M19_PY=$PY
mkdir -p $TMP
typeset -a names cmds
names+=candidate; cmds+="$PY $TREE/$API"
for s in noop naive vulnerable racy; do names+=stub-$s; cmds+="$O/stubs/$s.sh"; done
for s in noop_stub vulnerable_stub; do names+=builder-$s; cmds+="$PY $TREE/$EX/$s.py"; done
for m in $(ls $MD); do names+=mutant-$m; cmds+="$PY $MD/$m/$API"; done
: > $R/oracle-teeth.txt; [ -n "$ONLY_M19" ] || { : > $R/builder-oracle-vs-teeth.txt; : > $R/builder-tests-vs-mutants.txt; }
hdr="# M19 teeth on $($PY -c 'import sys;print(sys.version.split()[0])') $(date '+%F %T %Z')"; echo "$hdr (m19_oracle v2)" >> $R/oracle-teeth.txt
[ -n "$ONLY_M19" ] || { echo "$hdr" >> $R/builder-oracle-vs-teeth.txt; echo "$hdr" >> $R/builder-tests-vs-mutants.txt; }
for i in {1..${#names}}; do
  n=$names[$i]; c=$cmds[$i]
  { echo "=== $n"; cd /tmp; $PY $O/m19_oracle.py --core-only --tmp $TMP -- ${=c} 2>&1; echo; } >> $R/oracle-teeth.txt
  [ -n "$ONLY_M19" ] || { echo "=== $n"; cd /tmp; $PY $TREE/$EX/boundary_oracle.py --server "$c" 2>&1 | grep -E "^(PASS|FAIL)|checks passed"; echo; } >> $R/builder-oracle-vs-teeth.txt
done
[ -n "$ONLY_M19" ] || for t in candidate $(ls $MD); do
  d=$TREE; [ $t = candidate ] || d=$MD/$t
  out=$(cd $d && $PY -m unittest discover -s tests -p test_g19_capability.py 2>&1); rc=$?
  echo "$( [ $t = candidate ] && echo candidate || echo mutant-$t ): rc=$rc $(echo $out | grep -E '^(Ran|OK|FAILED)' | tr '\n' ' ')" >> $R/builder-tests-vs-mutants.txt
done
rm -rf $TMP/m19-oracle-run-*(N)
echo TEETH-DONE
