#!/bin/zsh
# M34 survivor non-equivalence (Grok self-validation): for each mutant my oracle did not kill, apply it to a scratch copy of the
# candidate tree and run the builder's tests/test_g34_capability.py. A failing test is a distinguishing input, so the mutant is
# not equivalent and the survivor is a gap in MY oracle. Scratch copy /tmp/m34-surv only; the candidate worktree is not modified.
M=$1; S=/tmp/m34-surv; rm -rf $S; rsync -a --exclude .git /tmp/m34-eval/ $S/
T=employees/marketing/seo-aso-specialist/page_diagnostics.py; cp $S/$T /tmp/m34-surv-orig.py
cd $S
for n in ${=2}; do
  /usr/bin/python3 $M/oracle/builder_make_mutants_g34.py /tmp/m34-eval $n $S || { echo "$n ANCHOR-ERR"; continue; }
  out=$(env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_g34_capability 2>&1)
  rc=$?; failed=$(print -r -- "$out" | grep -E '^(FAIL|ERROR):' | sed -E 's/^(FAIL|ERROR): ([a-z_0-9]+).*/\2/' | sort -u | tr '\n' ' ')
  echo "$n tests_rc=$rc failing: ${failed:-none}"
  cp /tmp/m34-surv-orig.py $S/$T
done
cmp -s $S/$T /tmp/m34-eval/$T && echo "restored ok"; cd /; rm -rf $S /tmp/m34-surv-orig.py
