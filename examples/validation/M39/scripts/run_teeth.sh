#!/bin/zsh
# M39 teeth on 3.13.15 then 3.9.6 (Grok self-validation), 6 mutants at a time.
N=<D>/grok-output/M39
<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 $N/scripts/m39_teeth.py /tmp/m39-eval $N/scripts/builder_mutants_g39.py $N/oracle/m39_oracle.py $N/results/teeth-3.13.15 6 > $N/results/teeth-3.13.15.log 2>&1
/usr/bin/python3 $N/scripts/m39_teeth.py /tmp/m39-eval $N/scripts/builder_mutants_g39.py $N/oracle/m39_oracle.py $N/results/teeth-3.9.6 6 > $N/results/teeth-3.9.6.log 2>&1
