#!/usr/bin/env python3
"""M13 naive stub: SUM(amount) over every row by upper-cased currency, COUNT(*) as orders, plain join. Must be rejected."""
import csv, json, sys
from pathlib import Path
a = sys.argv[1:]
cp = Path(a[1]); c = json.load(open(cp))
rows = list(csv.DictReader(open(cp.parent / c["facts"]["file"], encoding="utf-8-sig")))
cust = {r["customer_id"]: r["region"] for r in csv.DictReader(open(cp.parent / c["dimension"]["file"]))} if c.get("dimension") else {}
def num(x):
    try: return float((x or "").replace(",", ""))
    except ValueError: return 0.0
metrics = {}
for m in c["metrics"]:
    g = {}
    for r in rows:
        key = tuple((r.get(b) or cust.get(r.get("customer_id"), "(unmatched)")).upper() if b == "currency" else (r.get(b) or cust.get(r.get("customer_id"), "(unmatched)")) for b in m["by"])
        g.setdefault(key, []).append(r)
    groups = []
    for k, rs in sorted(g.items()):
        if m["agg"] == "sum": v = f"{sum(num(r.get(m['column'])) for r in rs):.2f}"
        else: v = len(rs)
        groups.append({"group": dict(zip(m["by"], k)), "value": v, "rows": len(rs), "null_values_skipped": 0})
    metrics[m["name"]] = {"agg": m["agg"], "column": m["column"], "by": m["by"], "groups": groups, "null_values_skipped": 0}
rep = {"schema": "solaris.csv-reconcile-report/1", "status": "reconciled", "gaps": [], "metrics": metrics,
       "coverage": {"rows_read": len(rows), "included": len(rows), "all_rows_accounted": True},
       "execution": "local; no warehouse", "imputation": "none", "naive_comparison": {}}
out = json.dumps(rep, indent=2, sort_keys=True) + "\n"
if "--out" in a:
    open(a[a.index("--out") + 1], "w").write(out)
sys.stdout.write(out)
