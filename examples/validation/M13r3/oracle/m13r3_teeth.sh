#!/bin/zsh
# M13 r3 teeth (Grok self-validation). Resumable per subject; stops starting new subjects after BUDGET seconds.
# Usage: zsh m13r3_teeth.sh PYTHON CANDIDATE_TREE MUTANT_DIR ORACLE_DIR OLD_TOOL OUT_TSV BUDGET
# Scorers: M13 oracle (15), builder oracle (14, default sizes), builder G13 tests (40), M13 r3 probes (61 checks).
P=$1; C=$2; M=$3; O=$4; OLD=$5; OUT=$6; BUDGET=$7; export PYTHONDONTWRITEBYTECODE=1
T=employees/data/data-engineer/csv_reconcile.py; B=examples/capabilities/G13/reconcile_oracle.py; cd $C; start=$SECONDS
[ -f $OUT ] || printf 'subject\tm13_oracle\tbuilder_oracle\tbuilder_tests\tr3_probes\n' > $OUT
subjects=("candidate:$C/$T" "r2-75a4e2b:$OLD" "stub-noop:$O/m13/stubs/noop_fake_clean.py" "stub-naive:$O/m13/stubs/naive_sum.py"
          "builder-noop_stub:$C/examples/capabilities/G13/noop_stub.py" "builder-naive_stub:$C/examples/capabilities/G13/naive_stub.py")
for d in $M/*(/); do subjects+=("${d:t}:$d/csv_reconcile.py"); done
tag=${OUT:t:r}
for s in $subjects; do n=${s%%:*}; f=${s#*:}
  grep -q "^$n	" $OUT && continue
  (( SECONDS - start > BUDGET )) && { echo "BUDGET-STOP before $n"; exit 3; }
  a=$($P $O/m13/m13_oracle.py -- $P $f 2>&1 | grep -E '^(FAIL|SUMMARY)' | sed -E 's/^FAIL ([A-Za-z0-9_]+).*/\1/; s/^SUMMARY //' | tr '\n' ' ' | cut -c1-220)
  b=$($P $B --tool "$P $f" 2>&1 | grep -E '^(FAIL|[0-9]+/[0-9]+ checks)' | sed -E 's/^FAIL ([a-z0-9_]+).*/\1/' | tr '\n' ' ' | cut -c1-220)
  t=n/a; p=n/a
  case $n in stub-*|builder-*) ;; *)
    W=/tmp/m13r3-tc-$tag/$n; rm -rf $W; mkdir -p $W; rsync -a --exclude .git $C/ $W/; cp $f $W/$T
    (cd $W && $P -m unittest tests.test_g13_capability > $W.log 2>&1); t="rc=$? $(grep -E '^(Ran|OK|FAILED)' $W.log | tr '\n' ' ')"; rm -rf $W $W.log
    p=$($P $O/m13r3_probes.py $P $f 2>&1 | grep -E '^SUMMARY' | cut -c1-200);; esac
  printf '%s\t%s\t%s\t%s\t%s\n' "$n" "$a" "$b" "$t" "$p" >> $OUT; echo "done $n"
done
echo TEETH-DONE
