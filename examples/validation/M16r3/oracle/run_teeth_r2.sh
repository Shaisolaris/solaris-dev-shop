#!/bin/zsh
# M16 r2 teeth (Grok self-validation). Resumable per subject; stops starting new subjects after BUDGET seconds.
# Usage: zsh run_teeth_r2.sh PYTHON CANDIDATE_TREE MUTANT_DIR ORACLE_DIR OUT_TSV BUDGET
P=$1; C=$2; M=$3; O=$4; OUT=$5; BUDGET=$6; export PYTHONDONTWRITEBYTECODE=1
T=employees/engineering/llm-agent-designer/grounded_eval.py; B=examples/capabilities/G16/grounding_oracle.py
export M16_REAL=$C/$T; cd $C; start=$SECONDS
[ -f $OUT ] || printf 'subject\tm16_oracle_core\tbuilder_oracle\tbuilder_tests\n' > $OUT
subjects=("candidate:$C/$T" "r1-1f2d0b9:/tmp/m16r2-r1tool/grounded_eval.py" "stub-noop:$O/stubs/noop.py" "stub-always_abstain:$O/stubs/always_abstain.py" "stub-copy_question:$O/stubs/copy_question.py"
          "builder-noop_stub:$C/examples/capabilities/G16/noop_stub.py" "builder-naive_stub:$C/examples/capabilities/G16/naive_stub.py")
for d in $M/*(/); do subjects+=("${d:t}:$d/grounded_eval.py"); done
for s in $subjects; do n=${s%%:*}; f=${s#*:}
  grep -q "^$n	" $OUT && continue
  (( SECONDS - start > BUDGET )) && { echo "BUDGET-STOP before $n"; exit 3; }
  a=$($P $O/m16_oracle.py --only K1,K2,K3,K4,K5,K6,K7,K8,K9,K10 --scale-docs 300 -- $P $f 2>&1 | grep -E '^(SUMMARY|FAIL|CORE|RESULT|core)|ACCEPT|REJECT' | sed -E 's/^FAIL ([A-Za-z0-9]+).*/\1/' | tr '\n' ' ' | cut -c1-200)
  b=$($P $B --tool "$P $f" --scale-docs 300 2>&1 | grep -E '^(FAIL|[0-9]+/[0-9]+)' | sed -E 's/^FAIL ([a-z0-9]+).*/\1/' | tr '\n' ' ' | cut -c1-200)
  t=n/a
  case $n in stub-*|builder-*) ;; *)
    W=/tmp/m16r2-tc/$n; rm -rf $W; mkdir -p $W; rsync -a --exclude .git $C/ $W/; cp $f $W/$T
    (cd $W && $P -m unittest discover -s tests -p test_g16_capability.py > $W.log 2>&1); t="rc=$? $(grep -E '^(Ran|OK|FAILED)' $W.log | tr '\n' ' ')"; rm -rf $W $W.log;; esac
  printf '%s\t%s\t%s\t%s\n' "$n" "$a" "$b" "$t" >> $OUT; echo "done $n"
done
echo TEETH-DONE
