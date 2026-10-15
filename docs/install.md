# Install

Source archives and wheels are built from the same canonical `control-plane/`
files. The installed wheel places those files under
`solaris_intake/control_plane/`; the source checkout keeps the documented script
path. No repository symlink is required for packaging or source discovery.

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

1. Keep the full checkout available and open the employee there, for example `employees/quality-security/qa-engineer/SKILL.md`. If you copy a folder into your host skill directory, preserve every referenced shared standard as well as its companion files.
2. Point the agent at `SKILL.md` in that directory.
3. If the skill says to load `rules.md` or a reference next to it, copy those files too. Some skills also reference shared department standards outside their own folder. Preserve those relative paths or supply the original checkout as context. Every employee ships `SKILL.md`, `rules.md`, `plugin.json`, `capability.contract.json`, and `learnings.md`.

The chief of staff is `chief-of-staff/SKILL.md`. Routing uses `control-plane/`. Keep those two folders together if you want the intake command to keep working.

Do not copy a personal Desktop path into the skill. Do not commit `.env` files.

## Per-agent install notes

- **Claude Code**: project skills use `.claude/skills/`; personal skills use `~/.claude/skills/`. See [official skill locations](https://code.claude.com/docs/en/skills#choose-where-skills-load).
- **Cursor**: project skills use `.cursor/skills/` or `.agents/skills/`; user skills use their corresponding home directories. Local user skills do not automatically reach cloud sessions. See [official skill directories](https://cursor.com/docs/skills#skill-directories).
- **Windsurf / Devin Desktop**: current workspace skills use `.devin/skills/`; `.windsurf/skills/` remains a legacy location. See [official skill scopes](https://docs.devin.ai/desktop/cascade/skills#skill-scopes).
- **Codex**: project skills use `.agents/skills/`; user skills use `~/.agents/skills/`. Codex supports symlinks to skill folders, which can keep shared references in the original checkout. See [official local discovery guidance](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills).
- **Aider**: load `SKILL.md` as read-only context with `--read`, then include the supporting files the task requires. This is manual context loading, not automatic skill discovery. See [official conventions guidance](https://aider.chat/docs/usage/conventions.html).

Locations above were checked against the linked official documentation on
2026-10-15. A discovery path is not a cross-provider output-quality guarantee.

In every case, keep companion files together and preserve the shared standards referenced by the skill. Opening a skill in the full checkout avoids breaking those relative paths. A copied folder alone is not a complete bundle when it references a department standard.
