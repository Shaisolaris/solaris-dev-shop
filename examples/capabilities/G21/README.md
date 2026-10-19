# G21 offline client synchronization: oracle, controls and demo

- `sync_oracle.py [--tool PATH] [--seed N] [--quick]`: 13 checks, each judged from the server side
  (the G19 ledger's own invoices, `ledger_api.py check`) plus the oracle's own intent model. It brings
  its own synthetic principals (two tenants) and fault plans. Last line `PASSED n/m` or `REJECTED n/m`.
- `naive_sync.py`: the same CLI with four common client habits (a new idempotency key per attempt,
  a 409 marked done, last answer wins whatever its version, no lock). Expected `REJECTED 4/13`.
- `noop_sync.py`: accepts every command and does nothing. Expected `REJECTED 0/13`.

Nothing here touches a simulator or device; this is state-engine evidence (see
`employees/engineering/mobile-developer/offline-sync.md`).

## Demo (run from the repository root; needs only python3)

```bash
set -e
T=$(mktemp -d)
python3 employees/engineering/backend-developer/ledger_api.py serve --db $T/ledger.db --principals examples/capabilities/G19/fixtures/principals.json --ready-file $T/ready.json &
until [ -s $T/ready.json ]; do sleep 0.1; done
URL=http://127.0.0.1:$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["port"])' $T/ready.json)
echo local-demo-northwind-ada-0001 > $T/key.txt
S=employees/engineering/mobile-developer/offline_sync.py
python3 $S init --db $T/phone.db --device phone
python3 $S enqueue --db $T/phone.db create --ref r1 --customer "Blue Fern" --amount 1000 --currency USD
python3 $S enqueue --db $T/phone.db pay --ref r1 --amount 400
python3 $S enqueue --db $T/phone.db pay --ref r1 --amount 600
python3 $S sync --db $T/phone.db --base-url $URL --key-file $T/key.txt --crash-after-send 2 || echo "crash drill exit $?"
python3 $S sync --db $T/phone.db --base-url $URL --key-file $T/key.txt
python3 $S status --db $T/phone.db
python3 $S check --db $T/phone.db
kill %1; wait %1 || true
python3 employees/engineering/backend-developer/ledger_api.py check --db $T/ledger.db
rm -rf $T
```

Expected: the drill run exits 70 after the first payment is accepted but before it is recorded;
the second run replays that payment's key (the server answers `Idempotent-Replayed: true`), sends
the last payment, and the invoice ends paid once at 1000 (`0 pending, 3 acked`). Both checks print
`consistent`.
