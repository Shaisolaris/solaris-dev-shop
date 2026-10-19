#!/bin/zsh
# M02 r2 runner (Grok self-validation). Usage: run_oracle_r2.sh O EVAL R1
O=$1; E=$2; R1=$3
UV=${UV:-$HOME/.local/share/uv/python}
PY312=${PY312:?set PY312 to the Python 3.12 interpreter}
typeset -A PYS
PYS=(3.9.6 /usr/bin/python3 3.11.16 $UV/cpython-3.11.16-macos-aarch64-none/bin/python3.11 3.12.14 $PY312 3.13.15 $UV/cpython-3.13.15-macos-aarch64-none/bin/python3.13)
A=employees/product-project/project-onboarding/activate.py
OR=$O/oracle/m02r2_oracle.py
for v in 3.9.6 3.11.16 3.12.14 3.13.15; do
  P=$PYS[$v]; f=$O/results/oracle-candidate-$v.txt
  { echo "# $(date '+%F %T %Z') oracle sha256 $(shasum -a 256 $OR | cut -c1-16) candidate bbe682b $($P -V 2>&1)"; cd $E; $P $OR -- $P $A; echo "[exit $?]"; } > $f 2>&1
  grep SUMMARY $f | sed "s/^/$v candidate: /"
done
P=$PY312
for c in noop echo; do f=$O/results/control-$c-stub.txt
  { echo "# $(date '+%F %T %Z') control $c stub, $($P -V)"; $P $OR -- $P $O/oracle/stubs/$c.py; echo "[exit $?]"; } > $f 2>&1
  grep SUMMARY $f | sed "s/^/control $c: /"; done
f=$O/results/control-r1-41132041-3.12.14.txt
{ echo "# $(date '+%F %T %Z') positive control: pre-fix G02 r1 41132041, $($P -V)"; cd $R1; $P $OR -- $P $A; echo "[exit $?]"; } > $f 2>&1
grep SUMMARY $f | sed "s/^/control r1 41132041: /"
