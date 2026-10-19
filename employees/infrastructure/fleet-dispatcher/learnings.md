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
