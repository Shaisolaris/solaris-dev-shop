# G04 restartable work-order handoff

`employees/infrastructure/fleet-dispatcher/handoff.py` runs a three-step work order (activate with G02, render
a brief, deliver to a local outbox ledger) so that a second worker resumes from saved partial state, never
delivers twice and never reuses a receipt whose files changed. See `handoff-work-orders.md` for the contract.

## Try it (fresh copy, nothing outside it is touched)

```bash
cp -R examples/capabilities/G04/fixtures /tmp/g04-demo && cd /tmp/g04-demo
H=<repo>/employees/infrastructure/fleet-dispatcher/handoff.py
python3 $H run order.json --worker ana --fail-at deliver   # exit 75: delivered, receipt never written
python3 $H run order.json --worker ben                     # exit 0: reuses ana's receipts, duplicate suppressed
python3 $H status order.json                               # activate/brief done by ana, deliver done by ben
wc -l outbox/ledger.jsonl                                  # 1
python3 $H run order-rev2.json --worker cy                 # revision 2: new delivery, revision 1 superseded
python3 $H run order.json --worker ana                     # exit 2: revision 1 is older than revision 2
```

## Oracle and controls

```bash
python3 examples/capabilities/G04/handoff_oracle.py                                  # 16/16
python3 examples/capabilities/G04/handoff_oracle.py --tool examples/capabilities/G04/naive_handoff.py  # 9/16
python3 examples/capabilities/G04/handoff_oracle.py --tool examples/capabilities/G04/noop_handoff.py   # 1/16
```

The oracle builds every scenario in a fresh temporary copy of `fixtures/` and derives its expectations from
the contract (one delivery per order revision; reuse only when inputs and outputs still hash the same; the
exit codes), not from the runner's output. `naive_handoff.py` is the real runner with the two common
shortcuts (trust the intake on disk; deliver without checking the ledger). `noop_handoff.py` does nothing; it
passes only the static check s1 (no subprocess or network import), which a do-nothing tool passes trivially.

o14 runs 200 orders with four concurrent worker processes and seeded random crash drills, then a sweep.

Not run: workers on other machines or a network folder (locks are local fcntl locks), a router or scheduler
launching workers, Hermes jobs, and any live delivery.
