#!/usr/bin/env python3
"""G31 naive control: the checklist a proposal template allows. Sums the in-scope hour estimates, checks that
each commitment lists something and that every delivery result says pass. It does not check sources,
dependencies, ambiguity, demo evidence, price arithmetic, fixed-price support or the delivery date.
Expected to be REJECTED by scope_oracle.py."""
import json, sys
from decimal import Decimal


def check(path):
    p = json.load(open(path))
    reqs = {r["id"]: r for r in p["requirements"]}
    tot = {b: str(sum(Decimal(reqs[k]["estimate_hours"][b]) for k in p["proposal"]["scope"])) for b in ("low", "likely", "high")}
    F = [{"code": "invented_commitment", "ref": c["id"], "detail": "no refs"} for c in p["proposal"]["commitments"] if not c.get("refs")]
    return {"command": "check", "status": "blocked" if F else "ready", "findings": F, "estimate": {"hours": tot, "price": {}},
            "trace_matrix": [], "escalations": [], "conditions": [], "excluded": [], "capacity_finish": None}, (1 if F else 0)


def accept(path, dl):
    d = json.load(open(dl))
    F = [{"code": "criterion_failed", "ref": x["criterion"], "detail": ""} for x in d["results"] if x["outcome"] != "pass"]
    return {"command": "accept", "status": "not_accepted" if F else "accepted", "findings": F, "requirements": []}, (1 if F else 0)


def main(a):
    try:
        if a[0] == "verify":
            stored = json.load(open(a[1])); rep, _ = check(a[2]) if len(a) < 4 else accept(a[2], a[3])
            print("IDENTICAL" if stored.get("status") == rep["status"] else "DIFFERENT"); return 0 if stored.get("status") == rep["status"] else 1
        rep, code = check(a[1]) if a[0] == "check" else accept(a[1], a[2])
    except Exception as ex:
        print("INVALID: %s" % ex, file=sys.stderr); return 2
    if "--out" in a:
        open(a[a.index("--out") + 1], "w").write(json.dumps(rep))
    print(json.dumps(rep)); return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
