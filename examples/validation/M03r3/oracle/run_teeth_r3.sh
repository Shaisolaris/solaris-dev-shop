#!/bin/zsh
# M03 r3 teeth (Grok self-validation). Resumable; stops starting new subjects after BUDGET seconds.
# Usage: zsh run_teeth_r3.sh PYTHON TREE MUTANT_DIR R2_TOOL ORACLE_DIR R2_ORACLE_DIR OUT_TSV BUDGET
P=$1; C=$2; M=$3; R2=$4; O=$5; O2=$6; OUT=$7; BUDGET=$8; export PYTHONDONTWRITEBYTECODE=1
T=employees/infrastructure/database-administrator/sqlite_recovery.py; B=examples/capabilities/G03/recovery_oracle.py
cd $C; start=$SECONDS
[ -f $OUT ] || printf 'subject\tm03_oracle\tm03r3_sweep\tbuilder_oracle\tbuilder_tests\n' > $OUT
subjects=("candidate:$C/$T" "r2-9f2fbbc:$R2")
for d in $M/*(/); do subjects+=("${d:t}:$d/sqlite_recovery.py"); done
for s in $subjects; do n=${s%%:*}; f=${s#*:}
  grep -q "^$n	" $OUT && continue
  (( SECONDS - start > BUDGET )) && { echo "BUDGET-STOP before $n"; exit 3; }
  a=$($P $O2/m03_oracle.py -- $P $f 2>&1 | grep -E '^(SUMMARY|FAIL)' | sed -E 's/^FAIL ([a-z0-9]+).*/\1/' | tr '\n' ' ' | cut -c1-160)
  $P $O/m03r3_midswap_sweep.py $P $f 3,5,7 > /tmp/m03r3-sw.txt 2>&1; sw="rc=$? $(grep -c 'WROTE' /tmp/m03r3-sw.txt) wrote; $(tail -1 /tmp/m03r3-sw.txt)"
  b=$($P $B -- $P $f 2>&1 | grep -E '^(SUMMARY|FAIL)' | sed -E 's/^FAIL ([a-z0-9]+)_.*/\1/' | tr '\n' ' ' | cut -c1-160)
  W=/tmp/m03r3-tc/$n; rm -rf $W; mkdir -p $W; rsync -a --exclude .git $C/ $W/; cp $f $W/$T
  (cd $W && $P -m unittest discover -s tests -p test_g03_capability.py > $W.log 2>&1); t="rc=$? $(grep -E '^(Ran|OK|FAILED)' $W.log | tr '\n' ' ')"; rm -rf $W $W.log
  printf '%s\t%s\t%s\t%s\t%s\n' "$n" "$a" "$sw" "$b" "$t" >> $OUT; echo "done $n"
done
echo TEETH-DONE
