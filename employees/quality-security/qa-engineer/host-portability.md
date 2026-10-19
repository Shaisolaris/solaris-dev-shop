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

`skill-copy` copies only the role folder and lists missing references. It does not invent a host agent API.

## What a pass does not mean

- It does not publish to PyPI or change shared version/catalog metadata.
- It does not prove every host agent (common host agents) discovers skills the same way.
- It authenticates no install path on a stranger's machine beyond the commands run here.
