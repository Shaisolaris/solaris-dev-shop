#!/bin/bash
# regress.sh ENGINE_DIR PY : M16 r6-r8 tables and probes (from M16 r8 oracle) against ENGINE_DIR
O=/tmp/mv/m16r8/examples/validation/M16-r8/oracle; E=$1; P=${2:-python3}; export PYTHONDONTWRITEBYTECODE=1; T=$(mktemp -d)
for t in m16r6_table m16r7_greetings m16r8_wide; do echo "$t: $($P $O/$t.py $E $T/$t.json | tail -1)"; done
for t in m16r6_probes m16r5_probes m16r7_greeting_probes m16r8_e2e_probes; do echo "$t: $($P $O/$t.py $P $E/grounded_eval.py 2>&1 | tail -1)"; done
echo "overfilter: $($P $O/m16r7_fix_overfilter.py $E 2>&1 | tail -1)"
rm -rf $T
