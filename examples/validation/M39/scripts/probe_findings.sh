#!/bin/zsh
# M39 probes for P2-1 and P2-2 on the builder's own drill folder (Grok self-validation). Copies only; candidate untouched.
SRC=/tmp/m39-eval; PY=/usr/bin/python3; T=$SRC/employees/product-project/delivery-lead/delivery_evidence.py
K=$(mktemp -d /tmp/m39pr-XXXXXX); export PYTHONDONTWRITEBYTECODE=1
$PY $SRC/examples/capabilities/G39/drill.py --keep $K/drill | tail -1
v(){ $PY $T verify . --claims claims.json | head -5 | tr '\n' ' '; echo; }
echo "== drill folder after the drill:"; (cd $K/drill && v)
cp -Rp $K/drill $K/p21; cd $K/p21
echo "X999,C1,5000.00,USD,paid,2026-09-15T10:00:00-07:00,2026-09-15T11:00:00-07:00,2026-09-15T11:00:00-07:00" >> data/orders.csv
echo "== P2-1 after one order row appended to data/orders.csv:"; v
$PY $SRC/employees/data/data-engineer/csv_reconcile.py reconcile data/contract.json --out $K/rerun.json > $K/rerun.txt 2>&1; echo "re-run of the recorded command: exit $? ($(grep -o 'reconciled[a-z_]*' $K/rerun.txt | head -1)); report $(cmp -s $K/rerun.json reports/metrics.json && echo same || echo differs) from the recorded output"
cp -Rp $K/drill $K/p22; cd $K/p22; rm snapshots/s1/ledger.db
echo "== P2-2 after snapshots/s1/ledger.db is deleted (remaining: $(ls snapshots/s1 | tr '\n' ' ')):"; v
cd /tmp; rm -rf $K; unset PYTHONDONTWRITEBYTECODE
