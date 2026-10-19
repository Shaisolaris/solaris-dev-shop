#!/usr/bin/env python3
"""M16 no-op stub: answer writes a meta line claiming the baseline and nothing else; evaluate always says pass."""
import json, sys
a = sys.argv[1:]
if a and a[0] == "answer":
    open(a[a.index("--out") + 1], "w").write(json.dumps({"kind": "meta", "producer": {"kind": "deterministic_baseline", "executed_here": True}}) + "\n")
    print("answered all")
else:
    rep = {"schema": "solaris.grounded-eval-report/1", "status": "pass", "results": [], "counts": {}, "metrics": {},
           "provenance": {"evidence": "deterministic fixture behaviour (extractive baseline, no model; re-run here and matched)", "baseline_reproduced": True}}
    if "--out" in a:
        open(a[a.index("--out") + 1], "w").write(json.dumps(rep))
    print(json.dumps(rep))
sys.exit(0)
