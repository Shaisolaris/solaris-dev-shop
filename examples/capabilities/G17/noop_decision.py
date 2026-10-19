#!/usr/bin/env python3
"""G17 no-op control: approves every option without computing anything. The oracle must reject it."""
import json
import sys

argv = sys.argv[1:]
if len(argv) < 2:
    sys.exit(2)
if argv[0] == "verify":
    print("IDENTICAL")
    sys.exit(0)
p = json.load(open(argv[1]))
print(json.dumps({"status": "feasible_options", "options": [{"id": o["id"], "cases": {}} for o in p.get("options", [])],
                  "feasible_in_downside": [o["id"] for o in p.get("options", [])], "certainty": "", "required_evidence": []}))
sys.exit(0)
