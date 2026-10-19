#!/bin/zsh
# M21 teeth on 3.13.15 then 3.9.6 (Grok self-validation), 6 mutants at a time.
N=<D>/grok-output/M21
<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 $N/scripts/m21_teeth.py /tmp/m21-eval $N/scripts/builder_mutants_g21.py $N/oracle/m21_oracle.py $N/results/teeth-3.13.15 6 > $N/results/teeth-3.13.15.log 2>&1
/usr/bin/python3 $N/scripts/m21_teeth.py /tmp/m21-eval $N/scripts/builder_mutants_g21.py $N/oracle/m21_oracle.py $N/results/teeth-3.9.6 6 > $N/results/teeth-3.9.6.log 2>&1
