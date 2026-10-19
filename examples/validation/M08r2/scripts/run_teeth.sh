#!/bin/zsh
# M08 r2 teeth on 3.13.15 then 3.9.6 (Grok self-validation), 5 mutants at a time.
N=<D>/grok-output/M08/r2
<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3 $N/oracle/teeth_m08r2.py /tmp/m08r2-eval $N/results/teeth-3.13.15 5 > $N/results/teeth-3.13.15.log 2>&1
/usr/bin/python3 $N/oracle/teeth_m08r2.py /tmp/m08r2-eval $N/results/teeth-3.9.6 5 > $N/results/teeth-3.9.6.log 2>&1
