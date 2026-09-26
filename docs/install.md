# Install

One command, from the repository root:

```bash
./install.sh
```

It verifies the tree, runs the control-plane self-test and the routing suite, and installs the `solaris-intake` command into `~/.local/bin`.

These files are skills, not a package you pip-install. No PyPI publish in this pass.

Manual check, same thing the installer runs:

```bash
python3 control-plane/meta_control_plane.py self-test
```

That command uses only the Python standard library. It was run from this folder and printed `meta control-plane selftest: OK`.

To use one employee in a coding agent:

1. Copy the employee directory, for example `employees/quality-security/qa-engineer/`, into the place your agent loads project skills.
2. Point the agent at `SKILL.md` in that directory.
3. If the skill says to load `rules.md` or a reference next to it, copy those files too. They sit beside the skill on purpose. Every employee ships `SKILL.md`, `rules.md`, `plugin.json`, `capability.contract.json`, and `learnings.md`.

The chief of staff is `chief-of-staff/SKILL.md`. Routing uses `control-plane/`. Keep those two folders together if you want the intake command to keep working.

Do not copy a personal Desktop path into the skill. Do not commit `.env` files.
