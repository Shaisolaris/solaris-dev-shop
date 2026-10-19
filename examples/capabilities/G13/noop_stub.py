#!/usr/bin/env python3
"""G13 no-op candidate: claims success without reading anything. The oracle must fail it."""
import json
import sys

rep = {"schema": "solaris.csv-reconcile-report/1", "status": "reconciled", "metrics": {}, "coverage": {}}
args = sys.argv[1:]
if "--out" in args:
    with open(args[args.index("--out") + 1], "w") as fh:
        json.dump(rep, fh)
print(json.dumps(rep))
sys.exit(0)
