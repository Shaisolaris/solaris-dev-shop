#!/usr/bin/env python3
"""M34 teeth (Grok self-validation): the BUILDER's 40 mutants (builder_make_mutants_g34.py, copied unchanged) scored by
MY oracle m34_oracle.py, which the builder did not see. A kill is any row whose result differs from the unmutated tool.
Usage: teeth_m34.py PY TOOL OUT i/n
v2: v1 crashed at import (builder CLI parsed my argv); log kept in results/teeth-v1-import-crash/.
v3: a kill is any deviation in a row result OR its recorded detail (tool rc, findings, report fields; temp dir names normalised).
    v2 compared row results only; its logs are kept in results/teeth-v2-result-only/."""
import importlib.util, json, os, re, shutil, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
PY, TOOL, OUT, SH = sys.argv[1:5]; os.makedirs(OUT, exist_ok=True)
s = importlib.util.spec_from_file_location("mm", os.path.join(here, "builder_make_mutants_g34.py")); mm = importlib.util.module_from_spec(s)
_argv = sys.argv; sys.argv = ["make_mutants_g34.py", "--list"]  # v2: builder script runs its CLI at import; --list exits after defining M
try: s.loader.exec_module(mm)
except SystemExit: pass
sys.argv = _argv
src = open(TOOL).read()
def score(tool, tag):
    o = os.path.join(OUT, tag); subprocess.run([PY, os.path.join(here, "m34_oracle.py"), PY, tool, o], capture_output=True, text=True, timeout=300)
    try: return {r["id"]: (r["result"], re.sub(r"/tmp/m34o-[a-z0-9_]+", "/tmp/m34o-X", json.dumps(r["detail"], sort_keys=True))) for r in json.load(open(os.path.join(o, "m34-oracle.json")))}
    except Exception as e: return {"ERR": repr(e)[:80]}
i, n = map(int, SH.split("/")); base = score(TOOL, f"base-{i}"); rows = []
for name in sorted(mm.M)[i::n]:
    old, new = mm.M[name]
    d = f"/tmp/m34-mut-{name}"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    if src.count(old) != 1:
        rows.append({"mutant": name, "error": "anchor count %d" % src.count(old)}); print(json.dumps(rows[-1]), flush=True); continue
    t = os.path.join(d, "page_diagnostics.py"); open(t, "w").write(src.replace(old, new))
    r = score(t, name)
    kr = sorted(k for k in set(base) | set(r) if (base.get(k) or ("",))[0] != (r.get(k) or ("",))[0])
    kd = sorted(k for k in set(base) | set(r) if base.get(k) != r.get(k) and k not in kr)
    rows.append({"mutant": name, "kills_result": kr, "kills_detail_only": kd}); print(json.dumps(rows[-1]), flush=True)
    shutil.rmtree(d, ignore_errors=True); shutil.rmtree(os.path.join(OUT, name), ignore_errors=True)
json.dump(rows, open(os.path.join(OUT, f"teeth-{i}.json"), "w"), indent=1); print("DONE")
