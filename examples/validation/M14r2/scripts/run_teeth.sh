#!/bin/zsh
# M14 r2 teeth on 3.13.15 then 3.9.6 (Grok self-validation), 3 mutants at a time.
N=<D>/grok-output/M14/r2
<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 $N/scripts/m14r2_teeth.py /tmp/m14r2-eval $N/scripts/builder_mutants_g14.py $N/oracle/m14r2_all.py $N/results/teeth-3.13.15 3 > $N/results/teeth-3.13.15.log 2>&1
/usr/bin/python3 $N/scripts/m14r2_teeth.py /tmp/m14r2-eval $N/scripts/builder_mutants_g14.py $N/oracle/m14r2_all.py $N/results/teeth-3.9.6 3 > $N/results/teeth-3.9.6.log 2>&1
