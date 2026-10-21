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
- The M07 self-validation (P4-1 to P4-3) found that loading registry.py from handoff.py wrote `__pycache__` into the source tree on Python 3.11+, that an upper-case copy of a machine id registered as a second machine, and that a SIGKILL during a change could leave a `.reg-*.tmp` file for good. handoff.py now imports both sibling tools with bytecode writing off, ids are compared without case, and leftover temp files are removed under the lock.
