# Fleet Dispatcher - Learnings

## Sources
- Upstream: none; authored for this library.
- License: MIT.
- Absorbed: work-order discipline and gate-line conventions from standard remote-team runbooks.

## Durable lessons
- The fleet root is the single most common failure point: when it is ambiguous, stop and ask. Everything downstream depends on it.
- A resumed worker must re-check a receipt against the files as they are now; a receipt alone is stale
  evidence once its output or input changed. Deliveries need a key checked before appending, because a crash
  can land between the effect and its receipt (G04, `handoff.py`).
- Status from artifacts, not from the last chat message. Stale memory about worker state is worse than no memory.
- The 2026-10-19 M04 r2 self-validation found that binding the owner into the receipts (G04 r2) let an owner change on an already delivered revision deliver that revision a second time, also after a crash between the delivery and its receipt. An owner change is now refused with exit 2 once the revision is in the ledger; a new revision is the way to change the owner.
