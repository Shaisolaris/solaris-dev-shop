#!/usr/bin/env python3
"""Console entry point for `solaris-intake` (see pyproject.toml).

Delegates to control-plane/meta_control_plane.py so the installed command
and the in-tree script always run the same code.
"""
import runpy
import sys
from pathlib import Path

CONTROL_PLANE = Path(__file__).resolve().parent / "control-plane" / "meta_control_plane.py"


def main() -> int:
    sys.argv = [str(CONTROL_PLANE), *sys.argv[1:]]
    runpy.run_path(str(CONTROL_PLANE), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
