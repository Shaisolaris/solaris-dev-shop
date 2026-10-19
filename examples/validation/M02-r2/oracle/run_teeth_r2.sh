#!/bin/zsh
# M02 r2 teeth (Grok self-validation): my oracle and the builder's G02 tests vs each mutant. Usage: run_teeth_r2.sh O PY MUTDIR EVAL
O=$1; P=$2; MD=$3; E=$4
mkdir -p $O/results/teeth
rm -rf /tmp/m02r2-muttree; rsync -a --exclude .git $E/ /tmp/m02r2-muttree/
A=employees/product-project/project-onboarding/activate.py
for m in $MD/*.py; do n=${m:t:r}
  $P $O/oracle/m02r2_oracle.py -- $P $m > $O/results/teeth/oracle-$n.txt 2>&1; o=$(grep SUMMARY $O/results/teeth/oracle-$n.txt)
  cp $m /tmp/m02r2-muttree/$A
  ( cd /tmp/m02r2-muttree && PYTHONDONTWRITEBYTECODE=1 $P -m unittest discover -s tests -p 'test_g02_capability.py' > $O/results/teeth/builder-$n.txt 2>&1 ); bt=$(tail -1 $O/results/teeth/builder-$n.txt)
  echo "$n | oracle: $o | failing checks: $(grep -o '^FAIL C[0-9]*' $O/results/teeth/oracle-$n.txt | cut -d' ' -f2 | tr '\n' ' ')| builder G02 tests: $bt"
done
cp $E/$A /tmp/m02r2-muttree/$A
( cd /tmp/m02r2-muttree && PYTHONDONTWRITEBYTECODE=1 $P -m unittest discover -s tests -p 'test_g02_capability.py' 2>&1 | tail -1 | sed 's/^/unmutated builder G02 tests: /' )
