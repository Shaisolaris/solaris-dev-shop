# Offline client sync (local state engine, synthetic)

`offline_sync.py` is the part of an offline-first client that decides whether a change made without a
network survives: a local SQLite outbox and the rules for handing it to the server. It talks to the
G19 ledger API (`employees/engineering/backend-developer/ledger_api.py`, see
`../backend-developer/duplicate-safe-api.md`) on loopback only. It is a state engine, not an app:
no simulator or device was used to build or prove it, and nothing here is a claim about iOS or
Android behaviour. Port the rules, not the file, into Room, Core Data, SQLDelight or WatermelonDB.

## The rules it proves

1. **Write locally first, with the key fixed at that moment.** `enqueue` stores the change, its
   exact request body and its idempotency key (`<install id>:<seq>`, the install id is the device
   name plus 8 random hex characters) in one transaction. Every retry, restart or concurrent sync
   sends that same key and body, so the server makes the effect once and replays its first answer.
   Local reference uniqueness is checked inside that transaction: concurrent creates for the same
   name have one winner. An explicit retry uses a new key, as described below.
2. **Send in the order of intent.** Pending changes go oldest first. A change to an invoice created
   offline waits until the create is acknowledged and the server id is stored. If a run stops, the
   next run resumes at the first unsent change.
3. **Refusals are explicit, never dropped.** A 409 or 404 becomes `conflict`, any other 4xx becomes
   `rejected`, with the server's answer kept. Later changes to the same invoice are held behind it
   (`waiting` says why). The user resolves it: `discard` (kept as `discarded`; discarding a create
   also discards that invoice's queued changes and names them) or `retry` (a new change with a new
   key at the back of the outbox; the old key's refusal is stored by the server and would only be
   replayed). Creating the retry and superseding the old refusal commit together; concurrent
   resolutions have one winner, and an interrupted transaction leaves the old refusal intact.
4. **Stop, don't skip, when the server is unusable.** 401/403 stops with exit 3, and 5xx, 408, 429,
   dropped connections and timeouts stop with exit 4. In both cases the change stays pending with
   its key. Redirects also stop with exit 4; the client never forwards a bearer key to a redirected
   destination, even on loopback, and ignores environment proxy settings.
5. **Newer server state only.** Pulled invoices (`sync` pages through `GET /api/v1/invoices`; or
   `apply-snapshot` with a saved list answer) replace the local copy only when `version` is
   higher, so a late or out-of-order answer cannot roll the view back.
6. **One sync at a time per outbox.** `sync` takes an exclusive lock on `<db>.lock`; a second one
   exits 5 at once. The lock goes away with the process, so a crash never leaves it held.

## Commands

```bash
python3 employees/engineering/mobile-developer/offline_sync.py init --db phone.db --device phone
python3 employees/engineering/mobile-developer/offline_sync.py enqueue --db phone.db create --ref r1 --customer "Blue Fern" --amount 1000 --currency USD
python3 employees/engineering/mobile-developer/offline_sync.py enqueue --db phone.db pay --ref r1 --amount 400
python3 employees/engineering/mobile-developer/offline_sync.py enqueue --db phone.db void --ref r1 --reason "duplicate order"
python3 employees/engineering/mobile-developer/offline_sync.py sync --db phone.db --base-url http://127.0.0.1:PORT --key-file key.txt
python3 employees/engineering/mobile-developer/offline_sync.py status --db phone.db --json
python3 employees/engineering/mobile-developer/offline_sync.py resolve --db phone.db --op 3 --action discard
python3 employees/engineering/mobile-developer/offline_sync.py apply-snapshot --db phone.db list-answer.json
python3 employees/engineering/mobile-developer/offline_sync.py check --db phone.db
```

`--ref` is a local name for an invoice you create offline; for an invoice pulled from the server
use its server id. `--key-file` holds the caller's bearer key on one line (the G19 fixture keys are
synthetic). `status --json` lists every change with its state, key, attempts, server status,
`replayed`, reason and `waiting`, plus each invoice's server copy and projected balance with
pending changes applied. `check` opens the outbox read-only and names each broken invariant
(an acked change without a 2xx answer, a key that is not this install's, a create not mapped to
its server id, a pending change that already has an answer, duplicate create roots, or a retry
without matching links in both directions). `sync` checks those invariants before making any
request and exits 2 on an inconsistent outbox; it preserves the rows for diagnosis rather than
sending duplicate intent. Do not delete a queued row or invent a retry link to make the check green.

Drill flags for `sync`: `--crash-before-send N` and `--crash-after-send N` exit 70 just before the
N-th request, or after its answer arrives but before the answer is recorded. `--no-pull` skips the pull.

| Exit | Meaning |
|---|---|
| 0 | done: nothing pending, no open conflict |
| 1 | `sync`: conflicts or rejections await the user; `check`: violations |
| 2 | invalid input, nothing recorded |
| 3 | the server refused the key; nothing changed |
| 4 | server unreachable, transient, or redirect refused; changes stay pending |
| 5 | another sync holds this outbox |
| 70 | deliberate crash drill |

## Evidence and limits

`examples/capabilities/G21/sync_oracle.py` judges a sync tool from the server's side (the invoices
and payments the ledger holds, `ledger_api.py check`, and its own intent model) across a clean
batch, client crashes before and after each send, server crashes before and after commit,
transient failures, void-versus-pay and overpay conflicts between devices, out-of-order
snapshots, refused keys, four concurrent syncs, tenant-scoped pulls and a seeded soak. Naive and
no-op controls sit beside it.

Limits: one outbox per device and one user decision per conflict; there is no automatic merge, and
amounts are never adjusted on the user's behalf. A retried change goes to the back of the outbox,
so it can land after later changes to the same invoice. Pull is a full list each time (no delta
cursor), fine for the demo's scale. The lock uses POSIX `fcntl`, so this runs on macOS and Linux.
