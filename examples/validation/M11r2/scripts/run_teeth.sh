#!/bin/zsh
# M11 r2 teeth on 3.13.15 then 3.9.6 (Grok self-validation), 4 mutants at a time.
N=<D>/grok-output/M11/r2
<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 $N/scripts/m11r2_teeth.py /tmp/m11r2-eval $N/scripts/builder_mutants_g11.py $N/oracle/m11r2_all.py $N/results/teeth-3.13.15 4 > $N/results/teeth-3.13.15.log 2>&1
/usr/bin/python3 $N/scripts/m11r2_teeth.py /tmp/m11r2-eval $N/scripts/builder_mutants_g11.py $N/oracle/m11r2_all.py $N/results/teeth-3.9.6 4 > $N/results/teeth-3.9.6.log 2>&1
