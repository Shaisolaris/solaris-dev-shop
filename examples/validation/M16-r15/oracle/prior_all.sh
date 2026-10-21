#!/bin/bash
# prior_all.sh ENGINE_DIR PY : M16 r5-r8 instruments (regress_prior.sh) plus the M16 r9-r14 tables and e2e probes
E=$1; P=$2; D=$(cd $(dirname $0) && pwd); T=$(mktemp -d); cd /tmp
bash $D/regress_prior.sh $E $P
for r in 9 10 11 12 13 14; do echo "m16r${r}_table: $($P $D/m16r${r}_table.py $E $T/t$r.json | tail -1)"
  echo "m16r${r}_e2e: $($P $D/m16r${r}_e2e_probes.py $P $E/grounded_eval.py 2>&1 | grep -E '^HOLDS')"; done
rm -rf $T
