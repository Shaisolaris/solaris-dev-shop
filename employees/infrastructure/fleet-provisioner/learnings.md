# Fleet Provisioner - Learnings

## Sources
- Upstream: none; authored for this library.
- License: MIT.
- Absorbed: machine-bootstrap checklists from standard SRE runbooks.

## Durable lessons
- Preflight is the whole job: most provision failures are missing keys or wrong machine, caught in 30 seconds by a strict preflight.
- A typed alias or hostname is not an identity: the same machine registered twice under two names gets two
  owners. Key registration on the machine identity and change owners by compare-and-set on an epoch, so a
  stale view is refused instead of overwriting (G07, `registry.py`).
- Decommissioning is where secrets leak. The checklist exists because "just wipe it" misses credential stores.
