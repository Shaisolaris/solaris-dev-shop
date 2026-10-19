#!/bin/zsh
# M22 teeth on 3.13.15 then 3.9.6 (Grok self-validation), 6 mutants at a time.
N=<D>/grok-output/M22
<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 $N/scripts/m22_teeth.py /tmp/m22-eval $N/scripts/builder_mutants_g22.py $N/oracle/m22_oracle.py $N/results/teeth-3.13.15 6 > $N/results/teeth-3.13.15.log 2>&1
/usr/bin/python3 $N/scripts/m22_teeth.py /tmp/m22-eval $N/scripts/builder_mutants_g22.py $N/oracle/m22_oracle.py $N/results/teeth-3.9.6 6 > $N/results/teeth-3.9.6.log 2>&1
