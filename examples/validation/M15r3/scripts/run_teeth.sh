#!/bin/zsh
# M15 r3 teeth on 3.13.15 then 3.9.6 (Grok self-validation), 4 mutants at a time.
N=<D>/grok-output/M15/r3
<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 $N/scripts/m15r3_teeth.py /tmp/m15r3-eval $N/scripts/builder_mutants_g15r3.py $N/oracle/m15r3_all.py $N/results/teeth-3.13.15 4 > $N/results/teeth-3.13.15.log 2>&1
/usr/bin/python3 $N/scripts/m15r3_teeth.py /tmp/m15r3-eval $N/scripts/builder_mutants_g15r3.py $N/oracle/m15r3_all.py $N/results/teeth-3.9.6 4 > $N/results/teeth-3.9.6.log 2>&1
