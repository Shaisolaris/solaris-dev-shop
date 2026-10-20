#!/bin/bash
# pyversions.sh WT ORACLES OUT : prior M39 oracles and probes, G39 tests, drill, drill_oracle, naive and no-op controls per Python
WT=$1; O=$2; OUT=$3; . "$(dirname "$0")/pys.sh"; mkdir -p $OUT; X=$WT/examples/capabilities/G39
for P in $P39 $P311 $P312 $P313; do V=$($P -V | cut -d' ' -f2); export PYTHONDONTWRITEBYTECODE=1
  line="== $V"
  for o in m39r5_probe m39r4_probe m39r3_probe m39r2_contract m39_oracle; do r=$(cd /tmp && $P $O/$o.py $WT $OUT/$o-$V.json 2>&1 | tail -1); line="$line | $o: $r"; done
  t=$(cd $WT && $P -m unittest tests.test_g39_capability 2>&1 | tail -1); line="$line | G39 tests: $t"
  d=$(cd $WT && $P $X/drill.py 2>&1 | tail -1); line="$line | drill: $d"
  for tool in employees/product-project/delivery-lead/delivery_evidence.py examples/capabilities/G39/naive_evidence.py examples/capabilities/G39/noop_evidence.py; do
    r=$(cd $WT && $P $X/drill_oracle.py --tool $WT/$tool 2>&1 | tail -1); line="$line | $(basename $tool): $r"; done
  line="$line | dirty: $(git -C $WT status --porcelain | wc -l | tr -d ' ')"
  echo "$line"; done | tee $OUT/pyversions.txt
