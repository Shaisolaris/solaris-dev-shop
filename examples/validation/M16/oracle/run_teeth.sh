#!/bin/zsh
# Usage: zsh run_teeth.sh PYTHON CANDIDATE_TREE MUTANT_DIR ORACLE_DIR RAW_DIR
# m16_oracle core checks (--scale-docs 300), the builder oracle (grounding_oracle.py --scale-docs 300) and the
# builder tests (test_g16_capability.py) against the candidate, 3 M16 stubs, 2 builder stubs and the mutants.
P=$1; C=$2; M=$3; O=$4; R=$5; export PYTHONDONTWRITEBYTECODE=1
T=employees/engineering/llm-agent-designer/grounded_eval.py; B=examples/capabilities/G16/grounding_oracle.py
export M16_REAL=$C/$T
cd $C
subjects=("candidate:$C/$T" "stub-noop:$O/stubs/noop.py" "stub-always_abstain:$O/stubs/always_abstain.py" "stub-copy_question:$O/stubs/copy_question.py"
          "builder-noop_stub:$C/examples/capabilities/G16/noop_stub.py" "builder-naive_stub:$C/examples/capabilities/G16/naive_stub.py")
for d in $M/*(/); do subjects+=("mutant-${d:t}:$d/grounded_eval.py"); done
: > $R/oracle-teeth.txt; : > $R/builder-oracle-vs-teeth.txt; : > $R/builder-tests-vs-mutants.txt
for s in $subjects; do n=${s%%:*}; f=${s#*:}
  { echo "=== $n"; $P $O/m16_oracle.py --only K1,K2,K3,K4,K5,K6,K7,K8,K9,K10 --scale-docs 300 -- $P $f 2>&1 | cut -c1-400; echo; } >> $R/oracle-teeth.txt
  { echo "=== $n"; $P $B --tool "$P $f" --scale-docs 300 2>&1 | grep -E "^(PASS|FAIL|[0-9]+/[0-9]+)" | cut -c1-300; echo; } >> $R/builder-oracle-vs-teeth.txt
  case $n in stub-*|builder-*) continue;; esac
  W=/tmp/m16-tc/$n; rm -rf $W; mkdir -p $W; rsync -a --exclude .git $C/ $W/; cp $f $W/$T
  (cd $W && $P -m unittest discover -s tests -p test_g16_capability.py > $W.log 2>&1); rc=$?
  echo "$n: rc=$rc $(grep -E '^(Ran|OK|FAILED)' $W.log | tr '\n' ' ')" >> $R/builder-tests-vs-mutants.txt; rm -rf $W $W.log
done
rm -rf /tmp/m16-tc
echo TEETH-DONE
