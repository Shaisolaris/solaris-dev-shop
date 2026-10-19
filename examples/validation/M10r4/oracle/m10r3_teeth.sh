#!/bin/zsh
# M10 r3 teeth (Grok self-validation). Resumable per subject; stops starting new subjects after BUDGET seconds.
# Usage: zsh m10r3_teeth.sh PYTHON CANDIDATE_TREE MUTANT_DIR ORACLE_DIR OLD_TOOL OUT_TSV BUDGET
# Scorers: M10 oracle (10), builder oracle (14), builder G10 tests (43), M10 r3 probes (pattern of HOLDS/GAP lines; a
# subject is killed by the probes when its pattern differs from the candidate's).
P=$1; C=$2; M=$3; O=$4; OLD=$5; OUT=$6; BUDGET=$7; export PYTHONDONTWRITEBYTECODE=1
T=employees/infrastructure/network-engineer/netdiag.py; B=examples/capabilities/G10/diagnosis_oracle.py; cd $C; start=$SECONDS
[ -f $OUT ] || printf 'subject\tm10_oracle\tbuilder_oracle\tbuilder_tests\tr3_probes\n' > $OUT
subjects=("candidate:$C/$T" "r3-be36f86:$OLD" "stub-noop:$O/m10/stubs/noop_echo.py" "stub-naive:$O/m10/stubs/naive_first_failure.py"
          "builder-noop_stub:$C/examples/capabilities/G10/noop_stub.py" "builder-naive_stub:$C/examples/capabilities/G10/naive_stub.py")
for d in $M/*(/); do subjects+=("${d:t}:$d/netdiag.py"); done
tag=${OUT:t:r}
for s in $subjects; do n=${s%%:*}; f=${s#*:}
  grep -q "^$n	" $OUT && continue
  (( SECONDS - start > BUDGET )) && { echo "BUDGET-STOP before $n"; exit 3; }
  a=$($P $O/m10/m10_oracle.py -- $P $f 2>&1 | grep -E '^(FAIL|SUMMARY)' | sed -E 's/^FAIL ([A-Za-z0-9_]+).*/\1/; s/^SUMMARY //' | tr '\n' ' ' | cut -c1-220)
  b=$($P $B -- $P $f 2>&1 | grep -E '^(FAIL|SUMMARY)' | sed -E 's/^FAIL ([a-z0-9_]+).*/\1/; s/^SUMMARY //' | tr '\n' ' ' | cut -c1-220)
  t=n/a; p=n/a
  case $n in stub-*|builder-*) ;; *)
    W=/tmp/m10r3-tc-$tag/$n; rm -rf $W; mkdir -p $W; rsync -a --exclude .git $C/ $W/; cp $f $W/$T
    (cd $W && $P -m unittest tests.test_g10_capability > $W.log 2>&1); t="rc=$? $(grep -E '^(Ran|OK|FAILED)' $W.log | tr '\n' ' ')"; rm -rf $W $W.log
    po=$($P $O/m10r3_probes.py $P $f $OLD $O/m10 2>&1); p="$(print -r -- $po | grep -E '^SUMMARY') pattern=$(print -r -- $po | grep -E '^(HOLDS|GAP)' | awk '{print $1}' | tr -d '\n' | shasum | cut -c1-10)";; esac
  printf '%s\t%s\t%s\t%s\t%s\n' "$n" "$a" "$b" "$t" "$p" >> $OUT; echo "done $n"
done
echo TEETH-DONE
