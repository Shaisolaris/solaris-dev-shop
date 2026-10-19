#!/usr/bin/env python3
"""Naive control for the G37 oracle (must be REJECTED): inventories only the columns the contracts declare,
answers every request without checking identity, plans to delete everything (no retention holds), uses a flat
30-day clock and reviews no retention dates."""
import csv, datetime as dt, json, sys
from pathlib import Path


def main():
    a = sys.argv[1:]
    pkg = Path(a[1])
    P = json.loads(pkg.read_text())
    base = pkg.parent
    tables = []
    for c in P["contracts"]:
        cp = base / c
        C = json.loads(cp.read_text())
        for part in ("facts", "dimension"):
            if C.get(part):
                rows = list(csv.reader(open(cp.parent / C[part]["file"], encoding="utf-8-sig")))
                tables.append((C[part]["file"], list(C[part]["columns"]), rows[1:]))
    reqs = []
    for line in (base / P["requests"]).read_text().splitlines():
        try:
            r = json.loads(line)
            rec = dt.datetime.fromisoformat(r["received_at"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            continue
        hits = [{"file": f, "line": n} for f, h, rows in tables for n, row in enumerate(rows, 2) if r["subject"] in row]
        reqs.append({"request_id": r["request_id"], "type": r["type"], "due": (rec + dt.timedelta(days=30)).isoformat(),
                     "status": {"access": "access_package_ready_for_review", "deletion": "deletion_plan_ready_for_review"}.get(r["type"], "correction_ready_for_review") if hits else "no_records_found",
                     "records": hits, "delete": hits, "retain_pending_review": []})
    rep = {"status": "complete", "findings": [], "requests": reqs, "retention": [], "qualified_review": [], "obligations": [],
           "inventory_map": [{"table": f, "field": x} for f, h, _ in tables for x in h], "not_legal_advice": ""}
    if "--out" in a:
        o = Path(a[a.index("--out") + 1]); o.mkdir(parents=True, exist_ok=True)
        (o / "report.json").write_text(json.dumps(rep)); (o / "handoff.md").write_text("# handoff\n")
    print(json.dumps(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
