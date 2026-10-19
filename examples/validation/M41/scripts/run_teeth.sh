#!/bin/zsh
# M41 teeth (Grok self-validation): builder G41 mutants (unchanged copy) on 3.13.15 then 3.9.6
N=<D>/grok-output/M41
for PY in <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 /usr/bin/python3; do V=$($PY -c 'import sys;print(sys.version.split()[0])')
$PY $N/scripts/m41_teeth.py /tmp/m41-eval $N/scripts/builder_mutants_g41.py $N/oracle/m41_oracle.py $N/results/teeth-$V 3 > $N/results/teeth-$V.log 2>&1; done
