#!/usr/bin/env python3
"""No-op control for the G21 oracle: accepts every command, keeps nothing, sends nothing, exits 0."""
import json
import sys

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "status":
        print(json.dumps({"counts": {"pending": 0, "acked": 0, "conflict": 0, "rejected": 0}, "ops": [], "invoices": []}))
    elif cmd == "check":
        print("consistent")
    else:
        print("{}")
    sys.exit(0)
