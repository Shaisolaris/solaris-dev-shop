# M02 validation oracle for G02 (project activation)

Grok self-validation material for candidate `41132041afeb2cce63a68554caf18cf6992a11ae`
(branch `review/grok-g02-activation`, base `02ba9c571b10ad1dba792d2ac5534bcad3171e67`).
This is not independent review. It was written separately from the builder's
`examples/capabilities/G02/activation_oracle.py` and tests, from the G02/M02 acceptance text and
the documented CLI in `project-onboarding/SKILL.md`. Python 3.12 standard library, synthetic data,
disposable temp directories only.

| File | Purpose |
|---|---|
| `m02_oracle.py` | 11 black-box checks (K1 to K11): two activations, owner docs, Git and outside sentinels, unborn repo and linked worktree, failure between writes then resume, SIGKILL at 12 write points (plain and with changed intake), changed intake during interruption, blank/omitted deploy, symlink/temp-alias/`--within`/`.git` link escape, secret refusal, concurrency (normal and slowed disk). Exit 0 only when every check passes; nothing skips. |
| `inject/sitecustomize.py` | Fault injector on `PYTHONPATH`: SIGKILL before the Nth write event under a root, or slow each write event. Patches the standard library only. |
| `stubs/noop_echo.py`, `stubs/naive_writer.py` | Negative controls. The no-op prints a fake `complete` JSON. |
| `make_mutants.py` | Builds 13 deliberately broken copies of `activate.py`; each replacement must apply exactly once. |
| `m02_adversarial.py` | Unseen cases (unicode/long names, read-only dirs, foreign journal, corrupt journal, lock files, submodule, outer repo, deploy edge values, traversal, hard links, FIFO, case collisions). Prints SAFE / FINDING / NOTE. |
| `m02_operational.py` | External SIGKILL at random times with documented recovery, 36 concurrent processes, resume racing activate, 5000-file owner tree. |
| `m02_fresh_caller.sh` | Run under `env -i` with a new HOME; uses only the commands printed in SKILL.md. |
| `m02_finding_repros.sh` | One reproduction per M02 finding. |

Run from the repository root at the candidate commit:

```sh
python3 examples/validation/M02/m02_oracle.py -- python3 employees/product-project/project-onboarding/activate.py
python3 examples/validation/M02/m02_oracle.py -- python3 examples/validation/M02/stubs/noop_echo.py   # must REJECT
python3 examples/validation/M02/make_mutants.py employees/product-project/project-onboarding/activate.py /tmp/m02-mutants
for m in /tmp/m02-mutants/*/; do python3 examples/validation/M02/m02_oracle.py -- python3 "$m/activate.py"; done  # all must REJECT
python3 examples/validation/M02/m02_adversarial.py -- python3 employees/product-project/project-onboarding/activate.py
python3 examples/validation/M02/m02_operational.py --iterations 200 -- python3 employees/product-project/project-onboarding/activate.py
env -i HOME="$(mktemp -d)" PATH="$(dirname "$(command -v python3)"):/usr/bin:/bin" sh examples/validation/M02/m02_fresh_caller.sh
PY=python3 sh examples/validation/M02/m02_finding_repros.sh
```

Known oracle limits: K11 (concurrency) is timing based; against the no-lock mutant it failed in 9 of 9
runs observed, which is strong but not proof. Checks read only the documented CLI and `--json`
`status`; other implementations need the same interface. POSIX only (macOS tested).
