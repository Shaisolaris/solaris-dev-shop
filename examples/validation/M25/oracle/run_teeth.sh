#!/bin/zsh
# M25 teeth (Grok self-validation). Scratch worktree /tmp/m25-mut only; restored and hash-checked after each mutant.
# Usage: run_teeth.sh PYTHON OUT_TSV
PY=$1; OUT=$2; O=${0:A:h}; T=/tmp/m25-mut; E=$T/employees/engineering/iot-engineer/device_protocol.py
CORE=K01,K02,K03,K04,K05,K06,K07,K08,K09,K10,K11,K12,K13,K14,K15,K16,K17,K18,K19,K20,K21,K22,K23
export PYTHONDONTWRITEBYTECODE=1
cd $T || exit 2
git -C $T checkout -q -- . ; ORIG=$(shasum -a 256 $E | cut -c1-16)
printf "mutant\tm25_core\tbuilder_g25_tests\tbuilder_oracle\tfull_suite\n" > $OUT
score() {
  local c=$($PY $O/m25_oracle.py $E --python $PY --only $CORE 2>&1 | tail -1 | sed -E 's/core: ([0-9]+) \/ ([0-9]+).*/\1\/\2/')
  local t=$($PY -m unittest tests/test_g25_capability.py 2>&1 | tail -1)
  local b=$(cd $T/examples/capabilities/G25 && $PY protocol_oracle.py --tool "$PY $E" 2>&1 | tail -1 | sed -E 's/ checks passed//')
  local f=$($PY -m unittest discover -s tests 2>&1 | tail -1)
  printf "%s\t%s\t%s\t%s\t%s\n" "$1" "$c" "$t" "$b" "$f" >> $OUT
}
score candidate
cp $E /tmp/m25-mut-ctl.py; print "# control: no-op" >> $E; score control_noop; cp /tmp/m25-mut-ctl.py $E; rm -f /tmp/m25-mut-ctl.py
for m in $($PY $O/make_mutants.py --list); do
  $PY $O/make_mutants.py $E $m $E.mut && mv $E.mut $E || { printf "%s\tANCHOR_FAIL\n" $m >> $OUT; continue; }
  score $m
  git -C $T checkout -q -- .
  [[ $(shasum -a 256 $E | cut -c1-16) == $ORIG ]] || { print -r -- "RESTORE_FAIL after $m" >> $OUT; exit 3; }
done
print -r -- "# done $(date '+%H:%M:%S %Z') restored=$ORIG" >> $OUT
