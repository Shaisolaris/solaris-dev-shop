#!/usr/bin/env python3
"""M04 teeth (Grok self-validation): the BUILDER's 34 mutants (builder_mutants_g04.py, copied unchanged) scored by MY oracle
m04_oracle.py. A kill is a row whose result differs from the unmutated tool, or whose detail differs (temp paths masked; C15's
detail is excluded because which concurrent workers get exit 0 versus 4 is timing). Usage: teeth_m04.py PY TOOL OUT i/n"""
import json, os, re, shutil, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
from builder_mutants_g04 import M
PY, TOOL, OUT, SH = sys.argv[1:5]; os.makedirs(OUT, exist_ok=True); src = open(TOOL).read()
def score(tool, tag):
    o = os.path.join(OUT, tag); subprocess.run([PY, os.path.join(here, "m04_oracle.py"), PY, tool, o], capture_output=True, text=True, timeout=400)
    try: rows = json.load(open(os.path.join(o, "m04-oracle.json")))
    except Exception as e: return {"ERR": (repr(e)[:80], "")}
    shutil.rmtree(o, ignore_errors=True)
    return {r["id"]: (r["result"], "" if r["id"] == "C15" else re.sub(r"(/private)?/tmp/m04o-[a-z0-9_]+", "X", json.dumps(r["detail"], sort_keys=True))) for r in rows}
i, n = map(int, SH.split("/")); base = score(TOOL, f"base-{i}"); json.dump(base, open(os.path.join(OUT, f"base-{i}.json"), "w"), indent=1); rows = []
for name, old, new in M[i::n]:
    if src.count(old) != 1:
        rows.append({"mutant": name, "error": "anchor count %d" % src.count(old)}); print(json.dumps(rows[-1]), flush=True); continue
    d = f"/tmp/m04-mut-{name}"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    t = os.path.join(d, "handoff.py"); open(t, "w").write(src.replace(old, new))
    # handoff.py imports G02's activate.py by a path relative to itself, so the mutant sits in a copy of the candidate tree
    rows.append(None)
    shutil.rmtree(d, ignore_errors=True)
    root = f"/tmp/m04-mut-{name}"; subprocess.run(["rsync", "-a", "--exclude", ".git", os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(TOOL)))) + "/", root + "/"], check=True)
    t = os.path.join(root, os.path.relpath(TOOL, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(TOOL)))))); open(t, "w").write(src.replace(old, new))
    r = score(t, name)
    kr = sorted(k for k in set(base) | set(r) if (base.get(k) or ("",))[0] != (r.get(k) or ("",))[0])
    kd = sorted(k for k in set(base) | set(r) if base.get(k) != r.get(k) and k not in kr)
    rows[-1] = {"mutant": name, "kills_result": kr, "kills_detail_only": kd}; print(json.dumps(rows[-1]), flush=True)
    shutil.rmtree(root, ignore_errors=True)
json.dump(rows, open(os.path.join(OUT, f"teeth-{i}.json"), "w"), indent=1); print("DONE")
