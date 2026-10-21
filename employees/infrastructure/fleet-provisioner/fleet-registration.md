# Fleet registration (registry.py)

An offline, local registry for synthetic machines. It decides which machine is registered under which alias,
who owns it, and whether a given machine may take work for a given owner. It never contacts, provisions or
controls a real machine, and it stores no secret; provisioning steps in SKILL.md stay manual and evidenced.

## Files (in the fleet root: `--root` or `$SOLARIS_FLEET_ROOT`)

- `registry.json`: machines with alias, machine_id, owner, owner_epoch and status. Replaced atomically.
- `ops.jsonl`: one intent per change, then its commit or abort. Bound to registry.json by hash.
- `FLEET.md`: the roster rendered from registry.json after every change. Do not edit it by hand.

## Rules it enforces

- **Identity, not names.** A machine is its identity file's `machine_id` (synthetic here). One active
  registration per machine_id; an alias belongs to one machine. A second alias for the same machine is refused. Machine ids are compared without regard to case (`MINI-7F3A-0001` is `mini-7f3a-0001`).
- **Retries are safe.** Every change carries `--request-id`. Repeating it returns the recorded result; reusing
  it for a different change is refused. Re-registering the same machine, alias and owner changes nothing.
- **Ownership is compare-and-set.** `transfer` and `retire` name the owner and owner_epoch the caller believes
  are current; any other view is a stale owner and is refused. Every ownership change raises owner_epoch.
- **Claims.** `claim` (and a G04 work order with a `fleet` block) admits work only for the registered machine
  whose identity file matches, while active, for its current owner at its current owner_epoch.
- **Atomic changes.** Intent, replace registry.json, commit. A crash in between is settled by the next command:
  commit if registry.json already holds the change, abort otherwise, so the prior owner stays. A torn last
  line of ops.jsonl is cut and noted; any other unreadable line stops all changes.
- **Outside edits.** If registry.json no longer matches the last committed change, every command refuses.
  Restore the file (or have the owner reconcile it) rather than building on it.

## Commands

```bash
R=employees/infrastructure/fleet-provisioner/registry.py
python3 $R register --root fleet --alias mini1 --identity identity.json --owner ana --request-id reg-1
python3 $R transfer --root fleet --alias mini1 --from-owner ana --expect-epoch 1 --to-owner ben --request-id t-1
python3 $R retire   --root fleet --alias mini1 --from-owner ben --expect-epoch 2 --request-id x-1
python3 $R claim    --root fleet --alias mini1 --identity identity.json --owner ben --epoch 2
python3 $R status   --root fleet
```

Exit codes: 0 done (including a repeated request); 2 refused or invalid, nothing changed; 75 a `--fail-at`
crash drill (`before-replace` or `after-replace`).

## Work orders bound to a machine (G04 handoff.py)

Add `"fleet": {"machine": "mini1", "owner_epoch": 2}` (optionally `"registry"`, a path inside the order's
folder; otherwise `$SOLARIS_FLEET_ROOT`) and run with `--identity` (or `$SOLARIS_MACHINE_IDENTITY`). The
order's `owner` must be the machine's current owner. The check runs before anything is created and again
under the worker lock; a refusal exits 2.

## Not covered

Real machines, SSH, Tailscale, Hermes, credentials. Registries on a network folder (locks are local fcntl
locks). Identity attestation: an identity file is a declaration, so a copied file would pass; it stops
mistakes and stale views, not a determined impostor with the file.

A `.reg-*.tmp` temp file is written only under the registry lock, so one found when the lock is taken was left by a killed change; the next command removes it and says so in its notes.
