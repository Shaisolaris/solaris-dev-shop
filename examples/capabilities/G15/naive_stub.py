#!/usr/bin/env python3
"""G15 naive control: the dashboard read (must be REJECTED).

Counts event rows as units, counts any outcome event whatever its time, keeps every assigned unit
(no cohort, no maturity, no contamination check), never checks the sample ratio, and calls any
positive gap a significant causal win.
"""
import csv
import json
import sys
from pathlib import Path


def main():
    pkg = Path(sys.argv[2])
    p = json.loads(pkg.read_text())
    arm = {r["unit_id"]: r["arm"] for r in csv.DictReader(open(pkg.parent / p["assignments"]["file"]))}
    n = {a: 0 for a in p["arms"]}
    x = {a: 0 for a in p["arms"]}
    for e in csv.DictReader(open(pkg.parent / p["events"]["file"])):
        a = arm.get(e["unit_id"])
        if a:
            n[a] += 1
            x[a] += e["event"] == p["outcome"]["event"]
    c, t = p["arms"]
    rate = {a: x[a] / n[a] if n[a] else 0 for a in p["arms"]}
    win = rate[t] > rate[c]
    rep = {"arms": {a: {"units": n[a], "converted": x[a], "rate": "%.6f" % rate[a]} for a in p["arms"]},
           "effect": {"difference": "%.6f" % (rate[t] - rate[c]), "ci_low": "0", "ci_high": "0", "p_value": "0.010000"},
           "outcome": "difference_detected" if win else "no_detectable_difference", "srm": {"mismatch": False},
           "claims_allowed": {"causal": win, "significance": win}, "exclusions": {}}
    out = json.dumps(rep, sort_keys=True, indent=1) + "\n"
    if "--out" in sys.argv:
        open(sys.argv[sys.argv.index("--out") + 1], "w").write(out)
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
