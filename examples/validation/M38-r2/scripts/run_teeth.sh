#!/bin/zsh
# M38 r2 teeth on 3.13.15 then 3.9.6 (Grok self-validation), 6 mutants at a time.
N=<D>/grok-output/M38-r2
<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 $N/scripts/m38_teeth.py /tmp/m38r2-eval $N/scripts/builder_mutants_g38r2.py $N/oracle/m38r2_oracle.py $N/results/teeth-3.13.15 6 > $N/results/teeth-3.13.15.log 2>&1
/usr/bin/python3 $N/scripts/m38_teeth.py /tmp/m38r2-eval $N/scripts/builder_mutants_g38r2.py $N/oracle/m38r2_oracle.py $N/results/teeth-3.9.6 6 > $N/results/teeth-3.9.6.log 2>&1
