# Install

One command, from anywhere:

```bash
curl -fsSL https://raw.githubusercontent.com/Shaisolaris/solaris-dev-shop/main/install.sh | bash
```

It clones to `~/.solaris-dev-shop`, verifies the tree, runs the control-plane self-test and the routing suite, installs the `solaris-intake` command into `~/.local/bin`, and prints per-agent skill paths. Uninstall any time with `~/.solaris-dev-shop/install.sh --uninstall`.

Uninstall removes only a command bearing the installer marker. It retains the
checkout and your local files. Older, unmarked commands are left for inspection.
To use a different command directory, pass `--bin-dir /your/chosen/bin` to install
and uninstall. Do not delete a checkout until you have reviewed its local changes.
The installer requires Python 3.10+. If `python3` is older, set `SOLARIS_PYTHON`
to the executable for a supported version before running the installer.

From a repository checkout, `./install.sh` does the same against the checkout you are in.

It verifies the tree, runs the control-plane self-test and the routing suite, and installs the `solaris-intake` command into `~/.local/bin`.

The employee skills are copied into your agent; the optional Python package is
the intake router only. It has not been published to PyPI. You can build a local
wheel with `python -m pip wheel . --no-deps`. The wheel ships the canonical
`control-plane/` files even when Git cannot materialize the checkout's convenience
symlink on Windows. It does not install the 61 employee skill directories into
an agent or execute them.

## Windows (PowerShell, manual install)

Install Python 3.10 or newer and Git, then use a checkout. No Bash is required:

```powershell
git clone https://github.com/Shaisolaris/solaris-dev-shop.git
Set-Location solaris-dev-shop
$requiredFiles = @('control-plane/meta_control_plane.py', 'control-plane/roster.json', 'control-plane/policy.json', 'chief-of-staff/SKILL.md')
foreach ($file in $requiredFiles) { if (!(Test-Path $file)) { throw "Missing required file: $file" } }
python control-plane/meta_control_plane.py self-test
if ($LASTEXITCODE -ne 0) { throw 'Self-test failed' }
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Routing suite failed' }
python control-plane/meta_control_plane.py intake --explain "review this code"
```

This manual route performs the same tree, self-test and routing checks as the
Bash installer and leaves your PATH unchanged. Run the Python script directly
from the checkout. CI exercises the Python commands on Windows, macOS and Linux.
The package is not published to PyPI; do not assume `pip install solaris-dev-shop`
fetches this project. Building a local wheel is a separate optional route.

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
