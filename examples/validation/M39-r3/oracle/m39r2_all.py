#!/usr/bin/env python3
"""M39 r2 combined oracle for teeth (Grok self-validation): runs the unchanged M39 oracle and the M39 r2 contract oracle
with this interpreter and writes their rows together. Usage: PY m39r2_all.py SRC OUT.json [--tool PATH]."""
import json, os, subprocess, sys
h = os.path.dirname(os.path.abspath(__file__)); src, out = sys.argv[1], sys.argv[2]; rows = []
for o in ("m39_oracle.py", "m39r2_contract.py"):
    t = out + "." + o + ".json"; subprocess.run([sys.executable, os.path.join(h, o), src, t] + sys.argv[3:], capture_output=True, timeout=480)
    try: rows += json.load(open(t))["rows"]; os.remove(t)
    except (OSError, ValueError, KeyError): rows.append({"row": o + " crash", "pass": False, "sub": {}})
json.dump({"rows": rows}, open(out, "w"), indent=1, default=str)
print("M39R2 ALL %d/%d rows pass" % (sum(r["pass"] for r in rows), len(rows)))
