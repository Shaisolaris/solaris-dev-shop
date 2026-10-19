#!/bin/zsh
# M05 survivor non-equivalence (Grok self-validation): apply each mutant my oracle did not kill to a scratch copy (/tmp/m05-surv)
# and run the builder's G05 tests plus the existing assurance tests; a failing test is a distinguishing input.
O=$1; S=/tmp/m05-surv; rm -rf $S; rsync -a --exclude .git /tmp/m05-eval/ $S/
T=employees/quality-security/assurance/quality_os.py; cp $S/$T /tmp/m05-surv-orig.py; cd $S
mods=$(ls tests | grep -E '^test_(g05|assurance).*\.py$' | sed 's/\.py$//;s/^/tests./' | tr '\n' ' ')
echo "test modules: $mods"
for n in ${=2}; do
  /usr/bin/python3 - $O $n $S/$T <<'P'
import sys; sys.path.insert(0, sys.argv[1]); from builder_mutants_g05 import M
a, b = [(x[1], x[2]) for x in M if x[0] == sys.argv[2]][0]; s = open(sys.argv[3]).read(); assert s.count(a) == 1; open(sys.argv[3], "w").write(s.replace(a, b))
P
  out=$(env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest ${=mods} 2>&1); rc=$?
  failed=$(print -r -- "$out" | grep -E '^(FAIL|ERROR):' | sed -E 's/^(FAIL|ERROR): ([a-zA-Z_0-9]+).*/\2/' | sort -u | tr '\n' ' ')
  echo "$n tests_rc=$rc failing: ${failed:-none}"; cp /tmp/m05-surv-orig.py $S/$T
done
cmp -s $S/$T /tmp/m05-eval/$T && echo "restored ok"; cd /; rm -rf $S /tmp/m05-surv-orig.py
