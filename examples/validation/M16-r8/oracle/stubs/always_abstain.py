#!/usr/bin/env python3
"""M16 always-abstain stub: `answer` abstains on every question (journal and fault plan ignored);
`evaluate` runs the real candidate evaluator named by M16_REAL, so only answering is wrong."""
import json, os, sys
a = sys.argv[1:]
if a and a[0] == "answer":
    qs = [json.loads(l) for l in open(a[a.index("--questions") + 1]) if l.strip()]
    lines = [{"kind": "meta", "schema": "solaris.grounded-answers/1", "producer": {"kind": "always_abstain_stub"}}]
    lines += [{"id": q["id"], "abstain": True, "answer": "", "citations": []} for q in qs]
    open(a[a.index("--out") + 1], "w").write("".join(json.dumps(x, sort_keys=True) + "\n" for x in lines))
    print(f"answered 0, abstained {len(qs)} of {len(qs)}")
    sys.exit(0)
os.execv(sys.executable, [sys.executable, os.environ["M16_REAL"]] + a)
