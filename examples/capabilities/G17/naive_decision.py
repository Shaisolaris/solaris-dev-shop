#!/usr/bin/env python3
"""G17 naive control: the spreadsheet shortcut. Base values only, total hours against total capacity by the
deadline, no dependencies, no ranges, no buffer, no evidence checks. The oracle must reject it."""
import json
import sys
from fractions import Fraction


def main(argv):
    if len(argv) < 2 or argv[0] != "evaluate":
        return 2
    p = json.load(open(argv[1]))
    A = {k: Fraction(str(v.get("value", 0))) for k, v in p.get("assumptions", {}).items()}
    val = lambda x: A.get(x, Fraction(0)) if isinstance(x, str) else Fraction(str(x))
    dl = p["milestones"][0]["deadline_week"]
    opts, feas = [], []
    for o in p["options"]:
        need = sum(val(w["hours"]) for w in p["work"] if w["id"] not in o.get("descope", []))
        have = sum(val(c["people"]) * val(c["hours_per_week"]) * val(c["focus"]) * dl for c in p["capacity"])
        ok = need <= have
        low = val(p["cash"]["opening"]) + (val(p["cash"]["monthly_inflow"]) - val(p["cash"]["monthly_outflow"])) * p["calendar"]["weeks"] / Fraction(52, 12)
        opts.append({"id": o["id"], "reversible": o.get("reversible"), "cases": {"downside": {"feasible": ok, "cash": {"lowest": "%.2f" % float(low)}}}})
        if ok:
            feas.append(o["id"])
    rep = {"status": "feasible_options" if feas else "rejected_as_stated", "options": opts, "feasible_in_downside": feas,
           "decision_owner": p["decision"].get("owner"), "certainty": "spreadsheet estimate", "required_evidence": []}
    print(json.dumps(rep))
    return 0 if feas else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
