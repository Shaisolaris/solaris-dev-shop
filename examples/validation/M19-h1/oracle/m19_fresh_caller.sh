#!/bin/zsh
# Fresh caller: a copy of the candidate tree (no .git), env -i with a new HOME, a PATH shim mapping python3
# to the given Python, and only the commands in duplicate-safe-api.md ("Run it", "Restart and retry drill",
# "Check stored state"), with unseen synthetic principals (tenants brackwater and fenmoor).
# Usage: m19_fresh_caller.sh PYTHON CANDIDATE_TREE
P=$1; C=$2
F=$TMP; rm -rf $F; mkdir -p $F/home $F/bin $F/work; rsync -a --exclude .git $C/ $F/repo/; ln -s $P $F/bin/python3
cat > $F/work/principals.json <<'J'
{"schema": "solaris.ledger-principals/1", "principals": [
 {"key": "fresh-brackwater-ivo-7f3a91c2", "tenant": "brackwater", "user": "ivo", "role": "editor"},
 {"key": "fresh-brackwater-jun-0b6e44d8", "tenant": "brackwater", "user": "jun", "role": "viewer"},
 {"key": "fresh-fenmoor-kai-5d21ce07aa", "tenant": "fenmoor", "user": "kai", "role": "editor"}]}
J
cat > $F/caller.sh <<'IN'
set -u
cd "$HOME/../work"
API=../repo/employees/engineering/backend-developer/ledger_api.py
PROBE=../repo/employees/quality-security/security-auditor/boundary_probe.py
ED=fresh-brackwater-ivo-7f3a91c2; OTHER=fresh-fenmoor-kai-5d21ce07aa
echo "python3 = $(python3 -c 'import sys; print(sys.version.split()[0])'); curl = $(command -v curl); env vars: $(env | wc -l | tr -d ' ')"
port() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["port"])' "$1"; }
echo "-- 1 the doc's 'Run it' block, placeholders filled"
python3 $API serve --db ledger.db --principals principals.json --ready-file ready.json &
until [ -s ready.json ]; do sleep 0.1; done
PORT=$(port ready.json)
A=$(curl -s -X POST http://127.0.0.1:$PORT/api/v1/invoices -H "Authorization: Bearer $ED" -H 'Idempotency-Key: fresh-key-1' -d '{"customer": "Harrow Lane Bakery", "amount_cents": 1000, "currency": "USD"}')
B=$(curl -s -X POST http://127.0.0.1:$PORT/api/v1/invoices -H "Authorization: Bearer $ED" -H 'Idempotency-Key: fresh-key-1' -d '{"customer": "Harrow Lane Bakery", "amount_cents": 1000, "currency": "USD"}')
echo "first  $A"; echo "second $B"
[ "$A" = "$B" ] && echo "same invoice returned twice: yes" || echo "same invoice returned twice: NO"
L1=$(curl -s http://127.0.0.1:$PORT/api/v1/invoices -H "Authorization: Bearer $ED")
L2=$(curl -s http://127.0.0.1:$PORT/api/v1/invoices -H "Authorization: Bearer $OTHER")
echo "owner list:  $L1"; echo "other list:  $L2"
python3 $PROBE --base-url http://127.0.0.1:$PORT --principals principals.json > probe.txt; echo "[probe exit $?] $(tail -c 300 probe.txt | tr '\n' ' ')"
kill %1; wait
python3 $API check --db ledger.db; echo "[check exit $?]"
echo "-- 2 drill: crash after commit, restart, retry (doc 'Restart and retry drill')"
echo '{"schema": "solaris.ledger-fault-plan/1", "crash_after_commit": ["drill-after"], "crash_before_commit": ["drill-before"]}' > plan.json
rm -f ready.json; python3 $API serve --db ledger.db --principals principals.json --ready-file ready.json --fault-plan plan.json &
SP=$!; until [ -s ready.json ]; do sleep 0.1; done; PORT=$(port ready.json)
curl -s -X POST http://127.0.0.1:$PORT/api/v1/invoices -H "Authorization: Bearer $ED" -H 'Idempotency-Key: drill-after' -d '{"customer": "Drill After", "amount_cents": 250, "currency": "GBP"}'; echo "[curl exit $?]"
wait $SP; echo "[server exit $?]"
rm -f ready.json; python3 $API serve --db ledger.db --principals principals.json --ready-file ready.json &
until [ -s ready.json ]; do sleep 0.1; done; PORT=$(port ready.json)
curl -s -i -X POST http://127.0.0.1:$PORT/api/v1/invoices -H "Authorization: Bearer $ED" -H 'Idempotency-Key: drill-after' -d '{"customer": "Drill After", "amount_cents": 250, "currency": "GBP"}' | tr -d '\r' | grep -E '^HTTP|^Idempotent-Replayed'
kill %1; wait
echo "-- 3 drill: crash before commit, restart, retry"
rm -f ready.json; python3 $API serve --db ledger.db --principals principals.json --ready-file ready.json --fault-plan plan.json &
SP=$!; until [ -s ready.json ]; do sleep 0.1; done; PORT=$(port ready.json)
curl -s -X POST http://127.0.0.1:$PORT/api/v1/invoices -H "Authorization: Bearer $ED" -H 'Idempotency-Key: drill-before' -d '{"customer": "Drill Before", "amount_cents": 75, "currency": "EUR"}'; echo "[curl exit $?]"
wait $SP; echo "[server exit $?]"
rm -f ready.json; python3 $API serve --db ledger.db --principals principals.json --ready-file ready.json &
until [ -s ready.json ]; do sleep 0.1; done; PORT=$(port ready.json)
curl -s -i -X POST http://127.0.0.1:$PORT/api/v1/invoices -H "Authorization: Bearer $ED" -H 'Idempotency-Key: drill-before' -d '{"customer": "Drill Before", "amount_cents": 75, "currency": "EUR"}' | tr -d '\r' | grep -E '^HTTP|^Idempotent-Replayed'
curl -s "http://127.0.0.1:$PORT/api/v1/invoices?limit=100" -H "Authorization: Bearer $ED" | python3 -c 'import json,sys; d=[x["customer"] for x in json.load(sys.stdin)["data"]]; print("brackwater: Harrow Lane Bakery x%d, Drill After x%d, Drill Before x%d, %d invoices in all (the probe adds its own)" % (d.count("Harrow Lane Bakery"), d.count("Drill After"), d.count("Drill Before"), len(d)))'
kill %1; wait
echo "-- 4 check --json (doc 'Check stored state')"
python3 $API check --db ledger.db --json | python3 -c 'import json,sys; r=json.load(sys.stdin); print("ok", r["ok"], "violations", r["violations"], "tenants", r["tenants"])'; echo "[check exit $?]"
IN
env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin bash $F/caller.sh 2>&1
