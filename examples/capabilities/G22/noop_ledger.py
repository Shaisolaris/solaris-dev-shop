#!/usr/bin/env python3
"""No-op control for the G22 oracle: accepts every command, keeps nothing, exits 0."""
import json
import sys

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "report":
        print(json.dumps({"money": {"captured": "0.00", "refunded": "0.00", "unapplied_captures": "0.00", "unapplied_refunds": "0.00"},
                          "net_cash": "0.00", "stock": [], "orders": [], "open": [], "events": {}}))
    elif cmd == "ingest":
        print(json.dumps({"events": [], "refused": 0, "open_held_or_exceptions": 0}))
    else:
        print("{}")
    sys.exit(0)
