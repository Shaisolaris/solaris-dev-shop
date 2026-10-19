"""M08 teeth (Grok self-validation). Usage: PY teeth_m08.py SRC OUTDIR [JOBS]. Applies each of the BUILDER's G08 mutants
(builder_mutants_g08.py, copied unchanged; only its M list is imported) to a copy of SRC (no .git) under /tmp/m08-mut-<tag>-<i>,
runs my oracle (m08_oracle.py) with this interpreter, and compares with the unmutated candidate. A kill is a change in any
core row result or in any OBS row detail. For a survivor it also runs the builder's tests.test_g08_capability on the copy."""
import json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
from builder_mutants_g08 import M
SRC, OUT = sys.argv[1], sys.argv[2]; J = int(sys.argv[3]) if len(sys.argv) > 3 else 4; os.makedirs(OUT, exist_ok=True)
PY = sys.executable; tag = "%d%d" % sys.version_info[:2]; env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}
FLAKY = {"D06_sigkill_during_rollback_10x", "D06", "D10_concurrent_deploys_same_target", "D10", "D10_timing"}  # v2: also the guard ids D06/D10 (a harness crash inside a timing row seen once on 3.11 v3)  # timing-dependent OBS rows: not counted as kills
def sig(j): return {r["id"]: (r["result"] if r["kind"] == "core" else json.dumps(r["detail"], sort_keys=True)) for r in json.load(open(j)) if r["id"] not in FLAKY}
def orc(root, name):
    j = os.path.join(OUT, name + ".json"); subprocess.run([PY, os.path.join(here, "m08_oracle.py"), root, j], env=env, capture_output=True, timeout=900); return sig(j)
base = orc(SRC, "baseline")
def one(i):
    n, f, a, b = M[i]; root = "/tmp/m08-mut-%s-%02d" % (tag, i); shutil.rmtree(root, ignore_errors=True)
    subprocess.run(["rsync", "-a", "--exclude", ".git", SRC + "/", root + "/"], check=True)
    p = os.path.join(root, f); s = open(p).read()
    if s.count(a) != 1: shutil.rmtree(root); return {"mutant": n, "anchor": s.count(a)}
    open(p, "w").write(s.replace(a, b)); r = orc(root, "m%02d-%s" % (i, n))
    diff = sorted(k for k in set(base) | set(r) if base.get(k) != r.get(k)); row = {"mutant": n, "killed": bool(diff), "rows": diff}
    if not diff:
        row["builder_tests_rc"] = subprocess.run([PY, "-m", "unittest", "tests.test_g08_capability"], cwd=root, env=env, capture_output=True).returncode
    shutil.rmtree(root, ignore_errors=True); return row
with ThreadPoolExecutor(J) as ex: rows = list(ex.map(one, range(len(M))))
json.dump(rows, open(os.path.join(OUT, "teeth.json"), "w"), indent=1)
for r in rows: print(json.dumps(r))
print("TEETH %s: my oracle kills %d/%d; survivors %s" % (sys.version.split()[0], sum(r.get("killed", False) for r in rows), len(rows), [(r["mutant"], r.get("builder_tests_rc")) for r in rows if not r.get("killed")]))
