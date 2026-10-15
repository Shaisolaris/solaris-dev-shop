#!/usr/bin/env python3
"""Console entry point for `solaris-intake` (see pyproject.toml).

Delegates to control-plane/meta_control_plane.py so the installed command
and the in-tree script always run the same code.
"""
import runpy
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
CONTROL_PLANE = PACKAGE_DIR / "control_plane" / "meta_control_plane.py"
if not CONTROL_PLANE.is_file():
    # A source checkout keeps the public script in control-plane/. Setuptools
    # maps that same directory into control_plane/ in the installed package.
    CONTROL_PLANE = PACKAGE_DIR.parent / "control-plane" / "meta_control_plane.py"


def main() -> int:
    sys.argv = [str(CONTROL_PLANE), *sys.argv[1:]]
    runpy.run_path(str(CONTROL_PLANE), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
