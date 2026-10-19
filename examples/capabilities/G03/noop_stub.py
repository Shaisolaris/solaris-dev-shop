#!/usr/bin/env python3
"""Negative control: echoes its arguments, prints a plausible snapshot id, exits 0, writes nothing.
recovery_oracle.py must reject it."""
import json
import sys

if "--json" in sys.argv:
    print(json.dumps({"status": "ok", "snapshot_id": "noop"}))
else:
    print(" ".join(sys.argv[1:]))
sys.exit(0)
