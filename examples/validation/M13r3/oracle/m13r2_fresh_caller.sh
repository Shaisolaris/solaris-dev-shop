#!/bin/zsh
# M13 r2 fresh caller: env -i, a new HOME, a python3 shim, the M13 offline guard, the doc's contract JSON verbatim,
# new data (10 rows) with a hand answer written before running, and only the 2 documented commands.
# Usage: zsh m13r2_fresh_caller.sh PYTHON CANDIDATE_TREE M13_ORACLE_DIR
PY=$1; C=$2; O=$3; F=/tmp/m13r2-fc
rm -rf $F; mkdir -p $F/home $F/bin $F/tree; rsync -a --exclude .git $C/ $F/tree/
printf '#!/bin/sh\nexec %s "$@"\n' "$PY" > $F/bin/python3; chmod +x $F/bin/python3
cd $F/tree
/usr/bin/python3 - <<'PY'
import re
doc = open("employees/data/data-engineer/csv-reconciliation.md").read()
open("contract.json", "w").write(re.search(r"```json\n(.*?)```", doc, re.S).group(1))
PY
cat > orders.csv <<'CSV'
Order ID,customer_id,amount,currency,status,event_time,loaded_at,updated_at
B1,K1,"1,200.00",usd,paid,2026-09-05T10:00:00-07:00,2026-09-06T00:00:00Z,2026-09-05T10:00:00Z
B2,K2,80.00,EUR,paid,2026-09-07 09:00:00,2026-09-08T00:00:00Z,2026-09-07T16:00:00Z
B2,K2,80.00,EUR,paid,2026-09-07 09:00:00,2026-09-09T00:00:00Z,2026-09-07T16:00:00Z
B3,K1,25.00,USD,paid,2026-09-10T12:00:00Z,,2026-09-10T12:00:00Z
B4,K3,60.00,USD,paid,2026-09-12T12:00:00Z,2026-09-13T00:00:00Z,2026-09-12T12:00:00Z
B4,K3,65.00,USD,paid,2026-09-12T12:00:00Z,2026-09-14T00:00:00Z,2026-09-13T12:00:00Z
B5,K9,10.00,USD,paid,2026-09-15T12:00:00Z,2026-09-16T00:00:00Z,2026-09-15T12:00:00Z
B6,K1,99.00,USD,void,2026-09-16T12:00:00Z,2026-09-17T00:00:00Z,2026-09-16T12:00:00Z
B7,K2,7.00,USD,paid,2026-10-01 00:00:00,2026-09-18T00:00:00Z,2026-09-18T00:00:00Z
B8,K2,15.00,USD,paid,2026-09-20T12:00:00+0000,2026-09-21T00:00:00Z,2026-09-20T12:00:00Z
CSV
printf 'customer_id,region\nK1,West\nK2,East\nK3,West\n' > customers.csv
printf 'file,rows,sum\norders.csv,10,1626.00\n' > control.csv
cat > hand-answer.txt <<'TXT'
Hand answer (written before running): 10 data rows (lines 2-11).
B1 USD 1,200.00 in (offset -07:00, inside the window); B2 EUR 80.00 in once: line 4 differs only in loaded_at, so it is an
exact copy and the earliest load (line 3) is kept; B3 blank loaded_at under as_of -> loaded_at_unknown (line 5);
B4 newer updated_at 65.00 in, 60.00 superseded (line 6); B5 orphan K9 -> USD 10.00 in, segment (unmatched);
B6 void -> excluded_status (line 9); B7 2026-10-01 00:00 LA = window end -> outside_window (line 10);
B8 +0000 offset -> bad_timestamp, rejected (line 11).
Revenue USD 1275.00, EUR 80.00; orders 4 (B1, B2, B4, B5); exit 1, gaps rejected_rows, loaded_at_unknown,
unmatched_or_missing_join_key, control_mismatch. Control: rows 10/10, parsed sum 1626.00/1626.00, mismatch because a row
was rejected. Naive-time note: 3 rows (B2 twice, B7).
TXT
cat hand-answer.txt
run() { echo "\$ $1"; env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin PYTHONPATH=$O/inject M13_NET_LOG=$F/net.log PYTHONDONTWRITEBYTECODE=1 \
  /bin/bash -c "cd $F/tree && T=employees/data/data-engineer/csv_reconcile.py && $1"; }
echo "# m13r2 fresh caller $(date '+%F %T %Z'); python3 shim -> $($PY -c 'import platform;print(platform.python_version())'); contract = the doc's JSON block verbatim; offline guard on"
run 'python3 $T reconcile contract.json; echo "exit=$?"'
run 'python3 $T reconcile contract.json --json --out report.json --rejects rejects.csv > /dev/null; echo "exit=$?"; cat rejects.csv'
/usr/bin/python3 - <<'PY'
import json
j = json.load(open("report.json"))
rev = {g["group"]["currency"]: g["value"] for g in j["metrics"]["revenue"]["groups"]}
got = (rev, j["metrics"]["orders"]["groups"][0]["value"], j["status"], j["gaps"], j["controls"]["match"])
want = ({"EUR": "80.00", "USD": "1275.00"}, 4, "reconciled_with_gaps",
        ["rejected_rows", "loaded_at_unknown", "unmatched_or_missing_join_key", "control_mismatch"], False)
print("report:", got)
print("matches the hand answer:", got == want)
PY
echo "net attempts: $( [ -f $F/net.log ] && wc -l < $F/net.log | tr -d ' ' || echo 0)"
echo "files now: $(ls | grep -v -E '^(employees|examples|tests|docs|scripts|catalog|README.*|LICENSE.*|pyproject.toml|Makefile|AGENTS.md|CLAUDE.md|assurance|programme|\..*)$' | tr '\n' ' ')"
echo "HOME after: $(find $F/home -mindepth 1 | wc -l | tr -d ' ') entries; hidden temp files: $(ls -a | grep -c -E '\.(tmp|keep)$')"
cd /tmp; rm -rf $F
