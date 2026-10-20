#!/usr/bin/env python3
"""G33 naive control: a weighted scoring spreadsheet. Averages the stated scores per option and dimension,
treats missing evidence as 0, ignores sources, quotes, segment, staleness and ranges, and picks the highest
total. Expected REJECTED by evidence_oracle.py."""
import json, sys
from decimal import Decimal

a = sys.argv[1:]
if a[0] == "verify":
    print("IDENTICAL"); sys.exit(0)
try:
    p = json.load(open(a[1]))
    w = {d["id"]: Decimal(d["weight"]) for d in p["dimensions"]}
except Exception as ex:
    print("INVALID: %s" % ex, file=sys.stderr); sys.exit(2)
tot = {}
for o in p["options"]:
    t = Decimal(0)
    for dk, wt in w.items():
        sc = [Decimal(c.get("score") or "3") for c in p["claims"] if c["option"] == o["id"] and c["dimension"] == dk]
        t += wt * (sum(sc) / len(sc) if sc else 0)
    tot[o["id"]] = t
best = max(tot, key=lambda k: tot[k])
q = lambda v: str(v.quantize(Decimal("0.0001")))
rep = {"status": "preferred", "preferred": best, "totals": {k: {"low": q(v), "high": q(v), "point": q(v), "unknown_dimensions": []} for k, v in tot.items()},
       "excluded": [], "verify_before_use": [], "findings": [], "contrary_evidence": [], "cells": [], "deciding_evidence": [],
       "estimates_made": "none", "claim_confidence": {}}
if "--out" in a:
    open(a[a.index("--out") + 1], "w").write(json.dumps(rep))
print(json.dumps(rep))
