#!/usr/bin/env python3
"""Control for handoff_oracle.py: the real runner with two common shortcuts.

1. It trusts the intake on disk: the work order's sha256 is replaced by whatever the file hashes to now.
2. It does not look in the outbox ledger before delivering, so a resumed or repeated run delivers again.
The oracle must reject it."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                "employees", "infrastructure", "fleet-dispatcher"))
import handoff as h  # noqa: E402

_load = h.load_order


def load_order(path):
    o = _load(path)
    o["intake_sha"] = h.sha_file(o["intake"]) or o["intake_sha"]
    return o


h.load_order = load_order
h.ledger_records = lambda outbox: []

if __name__ == "__main__":
    sys.exit(h.main())
