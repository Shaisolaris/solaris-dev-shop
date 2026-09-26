# Install

One command, from anywhere:

```bash
curl -fsSL https://raw.githubusercontent.com/Shaisolaris/solaris-dev-shop/main/install.sh | bash
```

It clones to `~/.solaris-dev-shop`, verifies the tree, runs the control-plane self-test and the routing suite, installs the `solaris-intake` command into `~/.local/bin`, and prints per-agent skill paths. Uninstall any time with `~/.solaris-dev-shop/install.sh --uninstall`.

From a repository checkout, `./install.sh` does the same against the checkout you are in.

It verifies the tree, runs the control-plane self-test and the routing suite, and installs the `solaris-intake` command into `~/.local/bin`.

These files are skills, not a package you pip-install. No PyPI publish in this pass. A `pyproject.toml` ships so the tree can be built as a wheel (`python3 -m pip wheel . --no-deps`); the wheel installs a working `solaris-intake` command backed by the bundled control plane. The repo layout keeps `solaris_intake/` as the entry-point package with `control-plane/` symlinked inside it.

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

## Per-agent install notes

- **Claude Code**: copy the employee folder into `~/.claude/skills/`. It is picked up automatically.
- **Cursor**: copy the employee folder into `.cursor/skills/` in your project, or `~/.cursor/skills/` for global use.
- **Windsurf**: copy the employee folder into `.windsurf/skills/` in your project.
- **Codex CLI**: copy the employee folder into `~/.codex/skills/`.
- **Aider**: copy the employee folder anywhere, then point Aider at the `SKILL.md` with `--read` or add it to your conventions file.

In every case, keep the five files together (`SKILL.md`, `rules.md`, `plugin.json`, `capability.contract.json`, `learnings.md`) and point the agent at `SKILL.md`.
