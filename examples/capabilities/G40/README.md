# G40 fresh user installation and host portability

Tool: `employees/quality-security/qa-engineer/host_portability.py` (rules: `host-portability.md`).
Docs: `docs/install.md`, `docs/first-task.md`, `docs/architecture.md` state wheel/installer **3.10+** vs
source capability tools **3.9+**, and that a lone copied skill folder is incomplete.

## Run

```bash
python3 employees/quality-security/qa-engineer/host_portability.py skill-copy . quality-security/qa-engineer   # exit 1 broken
python3 employees/quality-security/qa-engineer/host_portability.py python-bounds .                             # exit 0
python3 employees/quality-security/qa-engineer/host_portability.py wheel-smoke . --outside /tmp/g40-out        # exit 0 on 3.10+
python3 examples/capabilities/G40/portability_oracle.py                                                       # ACCEPTED 8/8
python3 examples/capabilities/G40/portability_oracle.py --tool examples/capabilities/G40/naive_portability.py  # REJECTED
python3 examples/capabilities/G40/portability_oracle.py --tool examples/capabilities/G40/noop_portability.py   # REJECTED
```

## Clean control

Wheel builds, installs outside the checkout, and `solaris-intake` self-test / intake / skills succeed.
`employees/` is not in the wheel. `python-bounds` reports wheel 3.10+ and source tools 3.9+.

## Failure case

Copying only `employees/quality-security/qa-engineer` drops `../QUALITY-SECURITY-STANDARD.md` and
`../assurance/*`. `skill-copy` status is `broken`.

POSIX. Tool itself: Python 3.9+. `wheel-smoke`: Python 3.10+.
