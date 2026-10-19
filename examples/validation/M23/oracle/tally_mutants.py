"""Tally mutant runs against stubs/mutants/plan.json: killed iff every expected killer FAILs. Grok self-validation."""
import json, os, sys
root = sys.argv[1]; plan = json.load(open(os.path.join(root, "stubs/mutants/plan.json")))
for m in plan:
    rp = os.path.join(root, "raw", f"mut-{m['mutant']}", "report.json")
    if not os.path.exists(rp):
        print(f"{m['mutant']:24s} NOT RUN"); continue
    r = json.load(open(rp)); res = {x["id"]: x["result"] for x in r.get("results", r.get("interaction_proof", []))}
    failing = sorted(k for k, v in res.items() if v == "FAIL")
    if m["expected_killers"]:
        st = "KILLED" if all(res.get(k) == "FAIL" for k in m["expected_killers"]) else "SURVIVED"
    else:
        st = "SURVIVED (control, expected)" if not failing else "KILLED (control, unexpected)"
    print(f"{m['mutant']:24s} {st:28s} expected={','.join(m['expected_killers']) or '-':38s} failing={','.join(failing)}")
