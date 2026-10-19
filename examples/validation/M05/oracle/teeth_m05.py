#!/usr/bin/env python3
"""M05 teeth (Grok self-validation): the BUILDER's G05 mutants (builder_mutants_g05.py, copied unchanged) scored by MY oracle
m05_oracle.py. Kill = a row whose result differs from the unmutated engine, or whose detail differs (temp paths masked; C10 and
C11 compare result only because their details carry timings). Mutant engines are standalone copies under /tmp/m05-mut-<name>.
Usage: teeth_m05.py PY ENGINE OUT i/n"""
import json, os, re, shutil, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
from builder_mutants_g05 import M
PY, TOOL, OUT, SH = sys.argv[1:5]; os.makedirs(OUT, exist_ok=True); src = open(TOOL).read()
def score(tool, tag):
    o = os.path.join(OUT, tag); subprocess.run([PY, os.path.join(here, "m05_oracle.py"), PY, tool, o], capture_output=True, text=True, timeout=400)
    try: rows = json.load(open(os.path.join(o, "m05-oracle.json")))
    except Exception as e: return {"ERR": (repr(e)[:80], "")}
    shutil.rmtree(o, ignore_errors=True)
    return {r["id"]: (r["result"], "" if r["id"] in ("C10", "C11") else re.sub(r"(/private)?/tmp/m05o-[a-z0-9_]+", "X", json.dumps(r["detail"], sort_keys=True, default=str))) for r in rows}
i, n = map(int, SH.split("/")); base = score(TOOL, f"base-{i}"); json.dump(base, open(os.path.join(OUT, f"base-{i}.json"), "w"), indent=1); rows = []
for name, old, new in M[i::n]:
    if src.count(old) != 1:
        rows.append({"mutant": name, "error": "anchor count %d" % src.count(old)}); print(json.dumps(rows[-1]), flush=True); continue
    d = f"/tmp/m05-mut-{name}"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d); t = os.path.join(d, "quality_os.py"); open(t, "w").write(src.replace(old, new))
    r = score(t, name)
    kr = sorted(k for k in set(base) | set(r) if (base.get(k) or ("",))[0] != (r.get(k) or ("",))[0])
    kd = sorted(k for k in set(base) | set(r) if base.get(k) != r.get(k) and k not in kr)
    rows.append({"mutant": name, "kills_result": kr, "kills_detail_only": kd}); print(json.dumps(rows[-1]), flush=True); shutil.rmtree(d, ignore_errors=True)
json.dump(rows, open(os.path.join(OUT, f"teeth-{i}.json"), "w"), indent=1); print("DONE")
