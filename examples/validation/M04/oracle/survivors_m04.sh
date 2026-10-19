#!/bin/zsh
# M04 survivor non-equivalence (Grok self-validation): apply each mutant my oracle did not kill to a scratch copy (/tmp/m04-surv)
# and run the builder's tests/test_g04_capability.py; a failing test is a distinguishing input. Also re-run my oracle on
# receipt_any_rev_EQUIV and print its C10 row next to the candidate's, to check the builder's equivalence claim.
O=$1; S=/tmp/m04-surv; rm -rf $S; rsync -a --exclude .git /tmp/m04-eval/ $S/
T=employees/infrastructure/fleet-dispatcher/handoff.py; cp $S/$T /tmp/m04-surv-orig.py; cd $S
for n in ${=2}; do
  /usr/bin/python3 - $O $n $S/$T <<'P'
import sys; sys.path.insert(0, sys.argv[1]); from builder_mutants_g04 import M
a, b = [(x[1], x[2]) for x in M if x[0] == sys.argv[2]][0]; s = open(sys.argv[3]).read(); assert s.count(a) == 1; open(sys.argv[3], "w").write(s.replace(a, b))
P
  out=$(env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_g04_capability 2>&1); rc=$?
  failed=$(print -r -- "$out" | grep -E '^(FAIL|ERROR):' | sed -E 's/^(FAIL|ERROR): ([a-zA-Z_0-9]+).*/\2/' | sort -u | tr '\n' ' ')
  echo "$n tests_rc=$rc failing: ${failed:-none}"
  if [ $n = receipt_any_rev_EQUIV ]; then /usr/bin/python3 $O/m04_oracle.py /usr/bin/python3 $S/$T /tmp/m04-surv-o > /tmp/m04-surv-o.txt 2>&1; echo "  oracle on mutant: $(grep '^C10 ' /tmp/m04-surv-o.txt | cut -c1-400)"; rm -rf /tmp/m04-surv-o /tmp/m04-surv-o.txt; fi
  cp /tmp/m04-surv-orig.py $S/$T
done
cmp -s $S/$T /tmp/m04-eval/$T && echo "restored ok"; cd /; rm -rf $S /tmp/m04-surv-orig.py
