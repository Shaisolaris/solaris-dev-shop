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
    pd.within = lambda path, root: True
    try:
        return _scan(root, cfg, 1 << 40)
    finally:
        pd.within = _within


pd.scan = scan

if __name__ == "__main__":
    sys.exit(pd.main())
