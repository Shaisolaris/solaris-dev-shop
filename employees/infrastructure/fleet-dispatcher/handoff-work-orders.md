# Restartable work orders (handoff.py)

A local runner for work that may be stopped by one worker and finished by another. It carries an explicit
owner, a revision number, hashed input references and receipts for each output, so a second worker resumes
from the saved partial state without redoing finished effects and without trusting evidence that changed.

It does not launch, schedule or contact workers, and it does not involve the router. "Worker" is the name the
caller passes with `--worker`; any process that runs `handoff.py run` on the order is a worker. Locks are
local `fcntl` locks, so all workers must share one machine (POSIX); a network folder is not supported.

## The work order

```json
{
  "schema": "solaris.work-order/1",
  "order_id": "WO-HARBOR-1",
  "revision": 1,
  "owner": "delivery-lead: A. Example",
  "inputs": {"intake": {"path": "intake.json", "sha256": "<sha256 of intake.json>"}},
  "project_root": "harbor-kiosk",
  "outbox": "outbox"
}
```

- `owner` is required: the person or role accountable for the order (who is working it is recorded separately). The owner is bound into the activate and brief receipt inputs, so changing the owner at the same revision makes those receipts stale and rewrites the brief; it does not reuse a brief that still names the old owner.
- `revision` is an integer from 1. Change the intake, then issue a new revision with the new hash.
- Every path is relative and stays inside the order's folder. `steps` may be omitted; if given it must be
  exactly `["activate", "brief", "deliver"]`.

## Steps

| Step | Effect | Receipt inputs | Receipt outputs |
|------|--------|----------------|-----------------|
| activate | runs project activation (`project-onboarding/activate.py`, G02) on `project_root` | intake hash, owner | `STATUS.md`, `ROUND-PLAN.md` hashes |
| brief | writes `.handoff/<order>/rev<N>/HANDOFF-BRIEF.md` | intake, `STATUS.md` hashes, owner | brief hash |
| deliver | appends one record to `<outbox>/ledger.jsonl` | brief hash | delivery key |

A receipt is reused only when its inputs and its outputs still hash the same. If an output was edited, or an
input it used changed, the step is reported stale and redone, and so is anything downstream of it, because
each later step's inputs include the earlier outputs' hashes. Activation is G02's own resumable run, so
redoing it on unchanged inputs changes nothing.

Delivery is keyed by `sha256(order_id, revision, brief hash)`. Before appending, the runner reads the ledger
under its lock; if the key is already there (a worker crashed after delivering but before its receipt), it
records the receipt and reports `already delivered; duplicate suppressed`.

## Commands

```bash
python3 handoff.py run ORDER.json --worker NAME [--json] [--state DIR]
python3 handoff.py run ORDER.json --worker NAME --stop-after brief   # clean handoff point
python3 handoff.py run ORDER.json --worker NAME --fail-at deliver    # crash drill
python3 handoff.py status ORDER.json [--json]
```

`status` lists each step of the order's revision as `done by <worker>` or `pending` (a receipt found stale and
not yet redone counts as pending), every delivery of the order across revisions, and whether the last worker
stopped without releasing the order. `run` notes earlier revisions' deliveries as superseded.

## Exit codes

- `0` every step is done (finished now or reused).
- `1` a step failed; the journal records why. Fix the cause and run again.
- `2` invalid order, intake hash mismatch, a revision older than one already worked, a journal belonging to
  another order, or a journal that does not verify. Nothing runs and nothing is written.
- `3` stopped on request after `--stop-after`; another worker can resume.
- `4` another worker holds the order; nothing is written.
- `75` a `--fail-at` crash drill: the process ends abruptly after the step's effect and before its receipt.

## Journal

`.handoff/<order_id>/journal.jsonl` is append-only and hash-chained (each line holds the previous line's
hash). An edited line stops the run with exit 2; do not repair it by hand, start a new order or restore the
file. The chain makes an edit visible; it is not a signature (anyone who can write the file can rebuild the
chain), so keep `.handoff/` writable only by the workers. A torn last line (a crash mid-write) is cut, noted in the journal, and the run continues.

## Limits

- One machine only; locks do not cross machines or network folders.
- The outbox is a local file. A real external effect (mail, deploy, ticket) needs its own idempotency key on
  the receiving side; this runner only guarantees it does not ask twice.
- Not exercised: workers on other machines, a router or scheduler launching workers, Hermes jobs, live delivery.
