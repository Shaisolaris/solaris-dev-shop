#!/bin/zsh
# M13 r3 fresh caller (Grok self-validation): env -i, a new HOME, a python3 shim, the M13 offline guard, the doc's contract JSON verbatim,
# new data (10 rows, r3 spellings) with a hand answer written before running, and only the 2 documented commands.
# Usage: zsh m13r2_fresh_caller.sh PYTHON CANDIDATE_TREE M13_ORACLE_DIR
PY=$1; C=$2; O=$3; F=/tmp/m13r3-fc
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
C1,K1,"2,000.00",usd,paid,2026-09-03 08:00:00+00,2026-09-04 00:00:00+00,2026-09-03 08:00:00+00
C2,K2,40.00,EUR,paid,2026-09-08 10:00:00.1234567 -07:00,2026-09-09T00:00:00.123456789Z,2026-09-08T17:00:00Z
C3,K3,30.00,USD,paid,2026-09-30 23:59:59.9999999-07,2026-10-01 07:00:00+00,2026-09-30T23:00:00Z
C4,K1,12.00,USD,paid,2026-10-01 00:00:00.0000001-0700,2026-10-01T08:00:00Z,2026-10-01T08:00:00Z
C5,K2,5.00,USD,paid,2026-09-15,2026-09-16,2026-09-15
C6,K3,9.00,USD,paid,2026-09-12 12:00:00+05:60,2026-09-13T00:00:00Z,2026-09-12T12:00:00Z
C7,K1,70.00,USD,paid,2026-09-20T12:00:00-0700,2026-10-02 00:00:01+00,2026-09-20T19:00:00Z
C8,K9,3.00,USD,paid,2026-09-21 12:00:00 +00:00,2026-09-22T00:00:00Z,2026-09-21T12:00:00Z
C8,K9,3.00,USD,paid,2026-09-21 12:00:00 +00:00,2026-09-23 00:00:00-07,2026-09-21T12:00:00Z
C9,K2,11.00,USD,test,2026-09-22T12:00:00Z,2026-09-23T00:00:00Z,2026-09-22T12:00:00Z
CSV
printf 'customer_id,region\nK1,West\nK2,East\nK3,West\n' > customers.csv
printf 'file,rows,sum\norders.csv,10,2183.00\n' > control.csv
cat > hand-answer.txt <<'TXT'
Hand answer (written before running; M13 r3): 10 data rows (lines 2-11), r3 spellings throughout.
C1 PostgreSQL +00 -> USD 2,000.00 in. C2 datetimeoffset(7) with space and 7 digits -> EUR 40.00 in; its loaded_at has 9
digits. C3 2026-09-30 23:59:59.9999999-07 is before the window end (2026-10-01 00:00 -07) -> USD 30.00 in.
C4 2026-10-01 00:00:00.0000001-0700 is after the end (truncates to the end) -> outside_window (line 5). C5 date-only
2026-09-15 in Los Angeles -> USD 5.00 in. C6 offset +05:60 -> bad_timestamp, rejected (line 7). C7 loaded 1 s after as_of
-> late_after_as_of (line 8), gap late_rows. C8 orphan K9 -> USD 3.00 in, segment (unmatched); line 10 differs only in
loaded_at -> exact copy, earliest load (line 9) kept. C9 status test -> excluded_status (line 11).
Revenue USD 2038.00, EUR 40.00; orders 5 (C1, C2, C3, C5, C8); exit 1; gaps rejected_rows, late_rows,
unmatched_or_missing_join_key, control_mismatch (a row was rejected).
TXT
cat hand-answer.txt
run() { echo "\$ $1"; env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin PYTHONPATH=$O/inject M13_NET_LOG=$F/net.log PYTHONDONTWRITEBYTECODE=1 \
  /bin/bash -c "cd $F/tree && T=employees/data/data-engineer/csv_reconcile.py && $1"; }
echo "# m13r3 fresh caller $(date '+%F %T %Z'); python3 shim -> $($PY -c 'import platform;print(platform.python_version())'); contract = the doc's JSON block verbatim; offline guard on"
run 'python3 $T reconcile contract.json; echo "exit=$?"'
run 'python3 $T reconcile contract.json --json --out report.json --rejects rejects.csv > /dev/null; echo "exit=$?"; cat rejects.csv'
/usr/bin/python3 - <<'PY'
import json
j = json.load(open("report.json"))
rev = {g["group"]["currency"]: g["value"] for g in j["metrics"]["revenue"]["groups"]}
got = (rev, j["metrics"]["orders"]["groups"][0]["value"], j["status"], sorted(j["gaps"]), j["controls"]["match"])
want = ({"EUR": "40.00", "USD": "2038.00"}, 5, "reconciled_with_gaps",
        sorted(["rejected_rows", "late_rows", "unmatched_or_missing_join_key", "control_mismatch"]), False)
print("report:", got)
print("matches the hand answer:", got == want)
PY
echo "net attempts: $( [ -f $F/net.log ] && wc -l < $F/net.log | tr -d ' ' || echo 0)"
echo "files now: $(ls | grep -v -E '^(employees|examples|tests|docs|scripts|catalog|README.*|LICENSE.*|pyproject.toml|Makefile|AGENTS.md|CLAUDE.md|assurance|programme|\..*)$' | tr '\n' ' ')"
echo "HOME after: $(find $F/home -mindepth 1 | wc -l | tr -d ' ') entries; hidden temp files: $(ls -a | grep -c -E '\.(tmp|keep)$')"
cd /tmp; rm -rf $F
