#!/usr/bin/env python3
"""G23 naive stub: flags every query above 50 ms on its own (no grouping, no component check beyond the
first one), reads no config, ignores the error log and bisect runs, and calls any lower mean a speedup
with no check that the measurements match. These are the usual shortcuts; the oracle must fail it."""
import json
import statistics
import sys

args = [x for x in sys.argv[1:] if not x.startswith("--")]
if args and args[0] == "compare":
    a, b = (json.load(open(p)) for p in args[1:3])
    ma = statistics.mean(r["total_ms"] for r in a.get("requests", [])) if a.get("requests") else 0
    mb = statistics.mean(r["total_ms"] for r in b.get("requests", [])) if b.get("requests") else 0
    print(json.dumps({"comparable": True, "speedup_claimed": mb < ma, "urls": [], "not_comparable_because": [],
                      "evidence_scope": "offline; no PHP, WordPress was run; synthetic"}))
    sys.exit(0)
try:
    b = json.load(open(args[1]))
except Exception:
    sys.exit(2)
F = []
for r in b.get("requests", []):
    for q in r.get("queries", []):
        if q.get("ms", 0) > 50:
            F.append({"code": "SLOW_QUERY", "components": [q.get("component", "unknown")], "detail": q["sql"]})
out = {"verdict": "faults_found" if F else "healthy", "findings": F, "notes": [],
       "evidence_scope": "offline; no PHP, WordPress was run; synthetic", "echo": b.get("wp_config", {})}
print(json.dumps(out))
sys.exit(1 if F else 0)
