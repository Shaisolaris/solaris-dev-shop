#!/usr/bin/env python3
"""G13 naive candidate: the usual spreadsheet mistakes, on purpose. The oracle must fail it.

It sums every row it can parse (duplicates, old versions, late and test rows included),
treats a missing amount as 0, counts rows as orders, inner-joins the customer file
(so duplicate customer rows fan out and orphans vanish), ignores the window and the
as-of cutoff, claims every row is accounted for, and writes --out before validating.
"""
import csv
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

args = sys.argv[1:]
cpath = Path(args[1])
out = args[args.index("--out") + 1] if "--out" in args else None
c = json.loads(cpath.read_text())
base = cpath.parent
rows = list(csv.DictReader(open(base / c["facts"]["file"], encoding="utf-8-sig")))
dim = list(csv.DictReader(open(base / c["dimension"]["file"], encoding="utf-8-sig")))
rev, by_region, naive = {}, {}, {}
for r in rows:
    try:
        amt = Decimal((r.get("amount") or "0").replace(",", ""))
    except (InvalidOperation, AttributeError):
        continue
    cur = (r.get("currency") or "").upper()
    rev[cur] = rev.get(cur, Decimal(0)) + amt
    naive[cur] = naive.get(cur, Decimal(0)) + amt
    for d in dim:
        if d["customer_id"] == r.get("customer_id"):
            k = (d["region"], cur)
            by_region[k] = by_region.get(k, Decimal(0)) + amt
rep = {"schema": "solaris.csv-reconcile-report/1", "status": "reconciled", "gaps": [],
       "metrics": {"revenue": {"groups": [{"group": {"currency": k}, "value": str(v)} for k, v in sorted(rev.items())],
                               "null_values_skipped": 0},
                   "orders": {"groups": [{"group": {}, "value": len(rows)}]},
                   "revenue_by_region": {"groups": [{"group": {"region": r, "currency": cu}, "value": str(v)}
                                                    for (r, cu), v in sorted(by_region.items())]}},
       "coverage": {"rows_read": len(rows), "accounted": len(rows), "all_rows_accounted": True, "included": len(rows)},
       "naive_comparison": {"sum_every_parsed_row": {k: str(v) for k, v in naive.items()}},
       "imputation": "missing amounts treated as 0", "execution": "data warehouse"}
if out:
    Path(out).write_text(json.dumps(rep))
print(json.dumps(rep))
sys.exit(0)
