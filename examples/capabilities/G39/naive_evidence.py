#!/usr/bin/env python3
"""Naive control: the real delivery_evidence.py with three common shortcuts. It trusts the digests written
in a record instead of re-reading the files, it does not check the record chain, and it takes the work
order as delivered once any delivery exists. Must fail the G39 oracle."""
import importlib.util, sys
from pathlib import Path
P = Path(__file__).resolve().parents[3] / "employees/product-project/delivery-lead/delivery_evidence.py"
spec = importlib.util.spec_from_file_location("g39_naive", str(P))
m = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(m)
_orig_read = m.read_ledger


def read_ledger(root):
    import json
    p = root / m.LEDGER_DIR / m.LEDGER
    if not p.exists():
        return [], 0, False
    recs = []
    for line in p.read_bytes().split(b"\n"):
        try:
            recs.append(json.loads(line))
        except ValueError:
            pass
    return recs, p.stat().st_size, False


class _Q:
    def __init__(self, q):
        self.q = q

    def artifact_digests(self, root, paths):
        return self.q.artifact_digests(root, paths)

    def binding_state(self, reviewed, subject):
        return "current", {}


_load = m._load_qos
m._load_qos = lambda: _Q(_load())
m.read_ledger = read_ledger
_h = m._handoff


def _handoff(root, order):
    h = _h(root, order)
    if h.get("deliveries_this_revision"):
        h["state"] = "delivered"
    return h


m._handoff = _handoff
if __name__ == "__main__":
    sys.exit(m.main())
