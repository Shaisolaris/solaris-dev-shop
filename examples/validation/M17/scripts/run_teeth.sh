#!/bin/zsh
# M17 teeth on 3.13.15 then 3.9.6 (Grok self-validation), 4 mutants at a time.
N=<D>/grok-output/M17
<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 $N/scripts/m17_teeth.py /tmp/m17-eval $N/scripts/builder_mutants_g17.py $N/oracle/m17_oracle.py $N/results/teeth-3.13.15 4 > $N/results/teeth-3.13.15.log 2>&1
/usr/bin/python3 $N/scripts/m17_teeth.py /tmp/m17-eval $N/scripts/builder_mutants_g17.py $N/oracle/m17_oracle.py $N/results/teeth-3.9.6 4 > $N/results/teeth-3.9.6.log 2>&1
