#!/usr/bin/env python3
"""M13 no-op stub: reads the contract, claims a clean reconcile with zero values. Must be rejected."""
import json, sys
a = sys.argv[1:]
c = json.load(open(a[1]))
rep = {"schema": "solaris.csv-reconcile-report/1", "status": "reconciled", "gaps": [],
       "metrics": {m["name"]: {"agg": m["agg"], "column": m["column"], "by": m["by"], "groups": [], "null_values_skipped": 0} for m in c["metrics"]},
       "coverage": {"rows_read": 0, "included": 0, "all_rows_accounted": True, "accounted": 0},
       "execution": "local; no warehouse", "imputation": "none", "naive_comparison": {}}
out = json.dumps(rep, indent=2, sort_keys=True) + "\n"
if "--out" in a:
    open(a[a.index("--out") + 1], "w").write(out)
sys.stdout.write(out)
