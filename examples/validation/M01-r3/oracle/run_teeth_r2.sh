#!/bin/zsh
# M01 r2 teeth (Grok self-validation). Scratch worktree /tmp/m01r2-mut only; restored after each mutant.
# Usage: run_teeth_r2.sh PYTHON OUT_TSV
PY=$1; OUT=$2; O=${0:A:h}; T=/tmp/m01r2-mut; E=$T/employees/quality-security/assurance/quality_os.py
export PYTHONDONTWRITEBYTECODE=1
cd $T || exit 2
git -C $T checkout -q -- . ; ORIG=$(shasum -a 256 $E | cut -c1-16)
print -r -- "mutant\toracle_core\tgaps_open\tfixture_runner_tests\tfull_suite" > $OUT
score() {
  local o=$($PY $O/m01_oracle.py $E --python $PY 2>&1 | tail -1)
  local c=$(print -r -- "$o" | sed -E 's/core: ([0-9]+) \/ 12.*/\1/'); local g=$(print -r -- "$o" | sed -E 's/.*gaps open: ([0-9]+) \/ 14.*/\1/')
  local ft=$($PY -m unittest tests/test_fixture_runner.py 2>&1 | tail -1); local fs=$($PY -m unittest discover -s tests 2>&1 | tail -1)
  print -r -- "$1\t$c/12\t$g/14\t$ft\t$fs" >> $OUT
}
score candidate
cp $E /tmp/m01r2-mut-ctl.py; print "# control: no-op" >> $E; score control_noop; cp /tmp/m01r2-mut-ctl.py $E; rm -f /tmp/m01r2-mut-ctl.py
for m in $($PY $O/make_mutants_r2.py --list); do
  $PY $O/make_mutants_r2.py $E $m $E.mut && mv $E.mut $E || { print -r -- "$m\tANCHOR_FAIL" >> $OUT; continue; }
  score $m
  git -C $T checkout -q -- .
  [[ $(shasum -a 256 $E | cut -c1-16) == $ORIG ]] || { print -r -- "RESTORE_FAIL after $m" >> $OUT; exit 3; }
done
print -r -- "# done $(date '+%H:%M:%S %Z') restored=$ORIG" >> $OUT
