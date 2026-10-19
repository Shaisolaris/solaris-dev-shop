#!/bin/zsh
# M39 r2 teeth on 3.13.15 then 3.9.6 (Grok self-validation): builder G39 r2 mutants (60, unchanged copy) scored by m39r2_all.py
N=<D>/grok-output/M39-r2
<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 $N/scripts/m39_teeth.py /tmp/m39r2-eval $N/scripts/builder_mutants_g39r2.py $N/oracle/m39r2_all.py $N/results/teeth-3.13.15 6 > $N/results/teeth-3.13.15.log 2>&1
/usr/bin/python3 $N/scripts/m39_teeth.py /tmp/m39r2-eval $N/scripts/builder_mutants_g39r2.py $N/oracle/m39r2_all.py $N/results/teeth-3.9.6 6 > $N/results/teeth-3.9.6.log 2>&1
