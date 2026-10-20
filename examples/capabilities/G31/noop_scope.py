#!/usr/bin/env python3
"""G31 no-op control: calls every proposal ready and every delivery accepted. Expected REJECTED."""
import json, sys

a = sys.argv[1:]
if a and a[0] == "verify":
    print("IDENTICAL"); sys.exit(0)
rep = {"command": a[0] if a else "check", "status": "accepted" if a and a[0] == "accept" else "ready", "findings": [],
       "estimate": {"hours": {}, "price": {}}, "trace_matrix": [], "escalations": [], "conditions": [], "excluded": [],
       "capacity_finish": None, "requirements": []}
if "--out" in a:
    open(a[a.index("--out") + 1], "w").write(json.dumps(rep))
print(json.dumps(rep))
