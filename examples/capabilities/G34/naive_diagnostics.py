#!/usr/bin/env python3
"""Control for diag_oracle.py: the real checks with four common shortcuts.

1. Reads every file it finds and follows symlinks, even out of the snapshot. 2. Has no size cap.
3. Writes --out in place, not atomically. 4. Ignores the configured redirects, so redirected links count as broken.
The oracle must reject it."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                "employees", "marketing", "seo-aso-specialist"))
import page_diagnostics as pd  # noqa: E402

def write_plain(path, data):
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)


pd.write_atomic = write_plain
_load = pd.load_config


def load_config(path):
    cfg = _load(path)
    cfg["redirects"] = {}
    return cfg


pd.load_config = load_config
_scan = pd.scan
_within = pd.within


def scan(root, cfg, max_bytes):
    # "No size cap": a cap no file can reach. It is the total size of everything reachable (symlinks
    # followed), not a fixed huge number: f.read(n) allocates n bytes up front on Linux, so 1 << 40 raised
    # MemoryError there and the control failed for the wrong reason (found by the CI replay on Linux).
    total, seen = 0, set()
    for d, dirs, files in os.walk(root, followlinks=True):
        real = os.path.realpath(d)
        if real in seen:  # a symlink loop: do not walk the same folder twice
            dirs[:] = []
            continue
        seen.add(real)
        for name in files:
            try:
                total += os.path.getsize(os.path.join(d, name))
            except OSError:
                pass
    pd.within = lambda path, root: True
    try:
        return _scan(root, cfg, total + 1)
    finally:
        pd.within = _within


pd.scan = scan

if __name__ == "__main__":
    sys.exit(pd.main())
