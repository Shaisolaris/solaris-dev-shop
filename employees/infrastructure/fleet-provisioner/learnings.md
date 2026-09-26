# Fleet Provisioner - Learnings

## Sources
- Upstream: none; authored for this library.
- License: MIT.
- Absorbed: machine-bootstrap checklists from standard SRE runbooks.

## Durable lessons
- Preflight is the whole job: most provision failures are missing keys or wrong machine, caught in 30 seconds by a strict preflight.
- Decommissioning is where secrets leak. The checklist exists because "just wipe it" misses credential stores.
