# Install

Source archives and wheels are built from the same canonical `control-plane/`
files. The installed wheel places those files under
`solaris_intake/control_plane/`; the source checkout keeps the documented script
path. No repository symlink is required for packaging or source discovery.

Select a published revision, inspect its source, and install from that checkout:

```bash
git clone https://github.com/Shaisolaris/solaris-dev-shop.git
cd solaris-dev-shop
# Check out the exact commit identified by the release you reviewed.
./install.sh
```

The installer verifies the local tree, runs the control-plane self-test and the routing suite,
installs the `solaris-intake` command into `~/.local/bin`, and prints per-agent skill paths.
It does not clone, pull, download dependencies, start Docker, or register a background updater.
Run it from the checkout root; running it elsewhere refuses without fetching anything.
Uninstall from the retained checkout with `./install.sh --uninstall`.
Updates are a separate owner-authorized operation: review the new exact revision before
changing the checkout and rerunning the installer. A host application's own update policy
is separate from this package and must be configured in that host.

Uninstall removes only a command bearing the installer marker. It retains the
checkout and your local files. Older, unmarked commands are left for inspection.
To use a different command directory, pass `--bin-dir /your/chosen/bin` to install
and uninstall. Do not delete a checkout until you have reviewed its local changes.
The installer requires Python 3.10+. If `python3` is older, set `SOLARIS_PYTHON`
to the executable for a supported version before running the installer.

Python version bounds (keep these distinct):

- **Wheel, `install.sh`, and the installed `solaris-intake` command:** Python **3.10+**
  (`requires-python = ">=3.10"` in `pyproject.toml`). Build and smoke the wheel the same way CI does
  (`python -m pip wheel . --no-deps`, install outside the checkout, run `solaris-intake self-test`).
  The wheel build fetches its backend (setuptools==84.2.1) from the package index. Offline, run
  `host_portability.py wheel-smoke . --outside "$(mktemp -d)" --wheelhouse DIR` with a folder holding a setuptools==84.2.1 wheel.
- **Source checkout capability tools** under `employees/` (stdlib scripts such as delivery evidence or
  host portability): Python **3.9+**. They are not installed by the wheel.

The optional wheel is the intake router only. It does not install the employee skill directories.
Capability tools that load companions by relative path need the **full checkout** (or every referenced
shared standard). Copying a single skill folder into a host skill directory breaks those references;
`employees/quality-security/qa-engineer/host_portability.py skill-copy` reports the missing paths.


From a repository checkout, `./install.sh` does the same against the checkout you are in.

It verifies the tree, runs the control-plane self-test and the routing suite, and installs the `solaris-intake` command into `~/.local/bin`.

Employee skills can be opened from the checkout or copied into your agent only as a complete
bundle (companions and shared standards); the optional Python package is the intake router only. It has not been published to PyPI. You can build a local
wheel with `python -m pip wheel . --no-deps`. The wheel ships the canonical
`control-plane/` files as `solaris_intake/control_plane/`. It does not install
the 61 employee skill directories into an agent or execute them.

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

## Executable capability platform scope
The router, catalog and core assurance/discovery distribution are checked on Linux,
macOS and Windows. The full local executable-capability suite currently runs on Linux
and macOS: several recovery, concurrency and journal examples require POSIX locking.
Do not infer universal Windows execution from portable skill text. A host must inspect
each workflow's runtime/tool requirements before running it. Unsupported lock-dependent
execution must refuse safely; the grounded-answer journal/resume path has an explicit
no-lock-backend refusal test in the Windows lane. Non-journal grounded-source context
checks also run there. Unverified workflows are not certified for Windows by this CI lane.
