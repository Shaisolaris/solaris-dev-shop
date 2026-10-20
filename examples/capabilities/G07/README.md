# G07 fleet registration without duplicate ownership

`employees/infrastructure/fleet-provisioner/registry.py` keeps an offline registry of synthetic machines: one
registration per machine identity, one owner at a time with an owner_epoch, request ids that make retries
safe, and a crash-settled intent/commit log. `fleet-dispatcher/handoff.py` (G04) refuses a fleet-bound work
order on the wrong machine or for a stale owner. See `fleet-registration.md` in fleet-provisioner.

## Try it (fresh folder; nothing outside it is touched)

```bash
mkdir /tmp/g07-demo && cd /tmp/g07-demo && cp -R <repo>/examples/capabilities/G07/fixtures id && mkdir fleet
R=<repo>/employees/infrastructure/fleet-provisioner/registry.py
python3 $R register --root fleet --alias mini1 --identity id/identity-mini1.json --owner ana --request-id reg-1   # exit 0: registered
python3 $R register --root fleet --alias mini1 --identity id/identity-mini1.json --owner ana --request-id reg-1   # exit 0: repeated, no second entry
python3 $R register --root fleet --alias spare --identity id/identity-mini1.json --owner ben --request-id reg-2   # exit 2: machine already registered
python3 $R claim --root fleet --alias mini1 --identity id/identity-impostor.json --owner ana --epoch 1            # exit 2: wrong machine
python3 $R transfer --root fleet --alias mini1 --from-owner ana --expect-epoch 1 --to-owner ben --request-id t-1 --fail-at before-replace   # exit 75: crash drill
python3 $R claim --root fleet --alias mini1 --identity id/identity-mini1.json --owner ana --epoch 1              # exit 0: prior owner kept
python3 $R transfer --root fleet --alias mini1 --from-owner ana --expect-epoch 1 --to-owner ben --request-id t-1  # exit 0: owner ben, epoch 2
python3 $R claim --root fleet --alias mini1 --identity id/identity-mini1.json --owner ana --epoch 1              # exit 2: stale owner
python3 $R status --root fleet                                                                                    # exit 0: one machine, ben, epoch 2
```

A work order (G04) bound to a machine adds `"fleet": {"machine": "mini1", "owner_epoch": 2}` and is run with
`--identity id/identity-mini1.json` and `SOLARIS_FLEET_ROOT=fleet` (or `fleet.registry` inside the order folder).

## Oracle and controls

```bash
python3 examples/capabilities/G07/registry_oracle.py                                               # 17/17
python3 examples/capabilities/G07/registry_oracle.py --tool examples/capabilities/G07/naive_registry.py   # 5/17 (4/17 if o10 race shows)
python3 examples/capabilities/G07/registry_oracle.py --tool examples/capabilities/G07/noop_registry.py    # 1/17
```

Each scenario runs in a fresh temporary folder; expectations come from the contract, not the tool's output.
`naive_registry.py` keys machines by the typed alias, ignores identity and epoch on claims and request ids, and
rewrites the registry in place. `noop_registry.py` does nothing and passes only the static check s1.
o10 races eight owner changes from one view (exactly one wins); o11 registers 60 machines from four concurrent
registrars that retry every request and try a duplicate alias for each machine; o16 runs the G04 runner.

Not run: real machines, SSH, Tailscale, Hermes or any provisioning step; registries on a network folder
(fcntl locks are local); identity attestation (the identity file is a declaration, as a hostname would be).
