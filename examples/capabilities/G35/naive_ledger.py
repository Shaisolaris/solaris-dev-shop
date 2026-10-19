#!/usr/bin/env python3
"""Naive control for the G35 oracle (must be REJECTED): the shortcuts a quick spreadsheet takes.
Sums every spend row (copies and old restatements included), counts every conversion event, values them with
the pixel-reported value, credits the first touch of the user with no window, and passes every creative."""
import csv, json, sys
from decimal import Decimal
from pathlib import Path


def main():
    a = sys.argv[1:]
    pkg = Path(a[1])
    P = json.loads(pkg.read_text())
    base = pkg.parent
    spend = {}
    with open(base / "spend.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.reader(f):
            if r and r[0] not in ("campaign_id", "Campaign"):
                spend[r[0]] = spend.get(r[0], Decimal(0)) + Decimal(r[2])
    first = {}
    for line in (base / P["touches"]).read_text().splitlines():
        try:
            t = json.loads(line)
        except ValueError:
            continue
        if t["user"] not in first or t["at"] < first[t["user"]][0]:
            first[t["user"]] = (t["at"], t["campaign_id"])
    got = {}
    for line in (base / P["conversions"]).read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        c = first.get(e["user"], (None, None))[1]
        if c:
            g = got.setdefault(c, [0, Decimal(0)])
            g[0] += 1
            g[1] += Decimal(e.get("value") or "0")
    camps = []
    for c in P["campaigns"]:
        s, (n, v) = spend.get(c["id"], Decimal(0)), got.get(c["id"], [0, Decimal(0)])
        camps.append({"id": c["id"], "currency": c["currency"], "spend": str(s.quantize(Decimal("0.01"))), "conversions": n,
                      "attributed_revenue": str(v.quantize(Decimal("0.01"))), "budget_remaining": str(Decimal(c["budget_total"]) - s),
                      "cpa": str((s / n).quantize(Decimal("0.01"))) if n else None,
                      "roas": str((v / s).quantize(Decimal("0.0001"))) if s else None})
    cr = []
    if P.get("creatives"):
        cr = [{"id": c["id"], "status": "ready_for_human_review"} for c in json.loads((base / P["creatives"]).read_text())["creatives"]]
    rep = {"status": "reconciled", "campaigns": camps, "findings": [], "unattributed": {}, "creatives": cr, "checks": {}}
    if "--out" in a:
        o = Path(a[a.index("--out") + 1])
        o.mkdir(parents=True, exist_ok=True)
        (o / "report.json").write_text(json.dumps(rep))
        (o / "campaign-brief.md").write_text("# Campaign ledger\n")
    print(json.dumps(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
