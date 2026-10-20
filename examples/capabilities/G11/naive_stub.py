#!/usr/bin/env python3
"""G11 naive control: the spreadsheet approach the SRE prose alone allows (must be REJECTED).

Sums every telemetry row it is given (re-delivered rows count twice, conflicting rows both
count, missing minutes are silently absent), sorts events by time, and recommends a rollback
whenever the error rate after the deploy exceeds the threshold, without asking where the
fault is or whether the data can be restored.
"""
import json
import sys
from fractions import Fraction


def main():
    path = sys.argv[2]
    b = json.load(open(path))
    good = sum(r["good"] for r in b["telemetry"])
    total = sum(r["total"] for r in b["telemetry"])
    o = Fraction(str(b["slo"]["objective"]))
    bad = total - good
    allowed = (1 - o) * total

    def d(f):
        return None if f is None else "%.6f" % float(f)
    slo = {"good": good, "total": total, "bad": bad, "availability": d(Fraction(good, total)),
           "error_budget_requests": d(allowed), "budget_remaining": d(1 - bad / allowed),
           "burn_rate": d(Fraction(bad, total) / (1 - o)), "coverage": "1.000000",
           "status": "met" if Fraction(good, total) >= o else "breached"}
    tl = sorted([{"at": e["at"], "kind": e["kind"], "source": "event", "id": e["id"], "late": False}
                 for e in b.get("events", [])], key=lambda x: x["at"])
    dec = None
    c = b.get("change")
    if c:
        post = [r for r in b["telemetry"] if r["minute"] >= c["deployed_at"][:17] + "00Z"]
        pt = sum(r["total"] for r in post)
        pb = pt - sum(r["good"] for r in post)
        burn = Fraction(pb, pt) / (1 - o) if pt else 0
        w = "%s/%s" % (b["window"]["start"], b["window"]["end"])
        dec = {"decision": "rollback" if burn >= 1 else "do_not_rollback", "service": b["service"], "window": w,
               "reason": "%s %s: error rate after %s (code only)" % (b["service"], w, c["revision"])}
    rep = {"service": b["service"], "slo": slo, "timeline": tl, "decision": dec, "labels": [],
           "missing_telemetry": {"minutes": 0, "ranges": [], "conflicting_minutes": 0, "conflicting_ranges": []},
           "impact": {"start": None, "end": None}, "response": {}, "import": {}, "read_only": "naive"}
    out = json.dumps(rep, sort_keys=True, indent=1) + "\n"
    if "--out" in sys.argv:
        open(sys.argv[sys.argv.index("--out") + 1], "w").write(out)
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
