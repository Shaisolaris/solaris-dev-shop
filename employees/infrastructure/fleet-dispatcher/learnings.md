# Fleet Dispatcher - Learnings

## Sources
- Upstream: none; authored for this library.
- License: MIT.
- Absorbed: work-order discipline and gate-line conventions from standard remote-team runbooks.

## Durable lessons
- The fleet root is the single most common failure point: when it is ambiguous, stop and ask. Everything downstream depends on it.
- Status from artifacts, not from the last chat message. Stale memory about worker state is worse than no memory.
