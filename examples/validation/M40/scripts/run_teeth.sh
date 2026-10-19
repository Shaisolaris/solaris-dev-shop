#!/bin/zsh
# M40 teeth (Grok self-validation): builder G40 r2 mutants (9, unchanged copy) on 3.13.15, 3.9.6 and 3.11.16 (the only interpreter here with an offline wheel build)
N=<D>/grok-output/M40
for PY in <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 /usr/bin/python3 <UV>/python/cpython-3.11.16-macos-aarch64-none/bin/python3; do V=$($PY -c 'import sys;print(sys.version.split()[0])')
$PY $N/scripts/m40_teeth.py /tmp/m40-eval $N/scripts/builder_mutants_g40r2.py $N/oracle/m40_oracle.py $N/results/teeth-$V 3 > $N/results/teeth-$V.log 2>&1; done
