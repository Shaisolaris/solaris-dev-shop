# Host portability and fresh install (host_portability.py)

Local checks for what a fresh user can actually run after install, without inventing endpoints.

```bash
python3 host_portability.py wheel-smoke REPO [--outside DIR]   # 0 pass, 1 findings, 2 invalid
python3 host_portability.py skill-copy REPO ROLE [--dest DIR]  # ROLE like quality-security/qa-engineer
python3 host_portability.py python-bounds REPO
python3 host_portability.py report REPO [--out FILE]
```

## Boundaries

| Surface | Python | What you get |
|---|---|---|
| Wheel / `install.sh` / `solaris-intake` | 3.10+ | Intake router and bundled control-plane under `solaris_intake/control_plane/` |
| Source checkout `employees/**/*.py` tools | 3.9+ | Capability scripts; need the full checkout (or every referenced shared standard) |
| Lone copied skill folder | any | Often **broken**: relative `../` department standards and preflight targets do not resolve |

`wheel-smoke` mirrors `.github/workflows/ci.yml`: build with `pip wheel --no-deps`, install outside the checkout, run `solaris-intake self-test`, `intake --explain`, and `skills playwright --json`. The wheel must not ship `employees/` or `.pyc` files. The build runs on a private copy of REPO under the work
folder (build/, dist/, *.egg-info, caches and bytecode left out), so the checkout gains nothing and a stale
`build/lib` file in it cannot reach the wheel; a `solaris_intake/` member with no source file is a finding
(`wheel_member_not_in_source`). `--outside` at or under REPO is refused (exit 2).
`--outside` must also be a new or empty folder: an existing file, or a folder that already holds anything, is refused with exit 2 before anything is
created, and wheel-smoke never deletes or overwrites files there. Without `--outside` it uses a fresh temporary
folder. If the build or install fails after the work folder is made, the message names that folder (it holds the
source copy and is left for inspection) instead of saying nothing was written.

The build step is `pip wheel`, which installs the build backend named in pyproject.toml (setuptools>=61) into an
isolated build environment from the package index. Offline, pass `--wheelhouse DIR` (wheel-smoke and report): a folder
holding a setuptools>=61 wheel, for example the one bundled in Python 3.11's `ensurepip/_bundled`. The build then runs
with `--no-index --find-links DIR` and needs no network, and the JSON names it in `build_backend_from`. A
`--wheelhouse` that is not a folder or holds no setuptools>=61 wheel is refused with exit 2 before anything is written.
Without a wheelhouse, an offline host gets exit 2 with `build_backend_unavailable`, the remedy, and pip's own error.

`skill-copy` copies only the role folder and lists missing references. It does not invent a host agent API. Without `--dest` the copy is made in a temp folder that is removed before the command returns (`dest` is null and `temp_copy` says so); pass `--dest DIR` to keep it.

## What a pass does not mean

- It does not publish to PyPI or change shared version/catalog metadata.
- It does not prove every host agent (common host agents) discovers skills the same way.
- It authenticates no install path on a stranger's machine beyond the commands run here.
