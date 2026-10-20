#!/usr/bin/env python3
"""G16 no-op candidate: writes an answers file with no answers and reports every eval as passed. Must fail the oracle."""
import json
import sys

args = sys.argv[1:]
if args and args[0] == "answer":
    out = args[args.index("--out") + 1]
    open(out, "w").write(json.dumps({"kind": "meta", "producer": {"kind": "deterministic_baseline"}}) + "\n")
    print("answered all questions")
else:
    rep = {"schema": "solaris.grounded-eval-report/1", "status": "pass", "counts": {}, "results": [],
           "provenance": {"evidence": "deterministic", "evaluator": "no model"}}
    if "--out" in args:
        open(args[args.index("--out") + 1], "w").write(json.dumps(rep))
    print(json.dumps(rep))
sys.exit(0)
