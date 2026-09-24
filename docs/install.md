# Install

These files are skills, not a package you pip-install.

Tested on this export:

```bash
python3 control-plane/meta_control_plane.py self-test
```

That command uses only the Python standard library. It was run from this folder and printed `meta control-plane selftest: OK`.

To use one employee in a coding agent:

1. Copy the employee directory, for example `employees/quality-security/qa-engineer/`, into the place your agent loads project skills.
2. Point the agent at `SKILL.md` in that directory.
3. If the skill says to load `rules.md` or a reference next to it, copy those files too. They sit beside the skill on purpose.

The chief of staff is `chief-of-staff/SKILL.md`. Routing uses `control-plane/`. Keep those two folders together if you want the intake command to keep working.

Do not copy a personal Desktop path into the skill. Do not commit `.env` files.
