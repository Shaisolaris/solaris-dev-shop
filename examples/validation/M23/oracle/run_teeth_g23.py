#!/usr/bin/env python3
"""M23 r1 teeth (Grok self-validation). For each mutant: copy the candidate worktree (no .git) to /tmp/m23-mut-<name>,
apply the mutant, then score with (a) M23 r1 probes, (b) M23 prep oracle through the G23 adapter, (c) builder
tests/test_g23_capability.py, (d) builder wp_oracle.py. A kill is any deviation from the unmutated candidate's own
baseline on that instrument. Usage: run_teeth_g23.py PYTHON OUTDIR [names...]"""
import json, os, shutil, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import make_mutants_g23 as MM
PY, OUT = sys.argv[1], sys.argv[2]; only = set(sys.argv[3:])
SRC = "/tmp/m23-eval"; REL = "employees/specialized/wordpress-master/wp_trace_diag.py"
os.makedirs(OUT, exist_ok=True)
env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}


def score(root, tag):
    tool = os.path.join(root, REL); d = os.path.join(OUT, tag); os.makedirs(d, exist_ok=True)
    r = {}
    subprocess.run([PY, os.path.join(here, "m23r1_probes.py"), PY, tool, d + "/probes"], capture_output=True, text=True, timeout=300, env=env)
    try:
        r["probes"] = {x["id"]: x["result"] for x in json.load(open(d + "/probes/probes.json"))}
    except Exception as e:
        r["probes"] = {"_error": str(e)}
    b = json.load(open(os.path.join(here, "binding-g23.json")))
    b["cmd"] = [PY, "{binding_dir}/g23_adapter.py", "{bundle}", PY, tool]
    bp = os.path.join(here, f".binding-teeth-{tag}.json"); json.dump(b, open(bp, "w"))
    subprocess.run([PY, os.path.join(here, "m23_oracle.py"), bp, d + "/prep"], capture_output=True, text=True, timeout=300, env=env)
    os.unlink(bp)
    try:
        r["prep"] = {x["id"]: x["result"] for x in json.load(open(d + "/prep/report.json"))["results"]}
    except Exception as e:
        r["prep"] = {"_error": str(e)}
    cp = subprocess.run([PY, "-m", "unittest", "tests.test_g23_capability"], cwd=root, capture_output=True, text=True, timeout=300, env=env)
    r["builder_tests"] = "OK" if cp.returncode == 0 else "FAIL " + (cp.stderr.strip().splitlines() or ["?"])[-1]
    cp = subprocess.run([PY, os.path.join(root, "examples/capabilities/G23/wp_oracle.py"), "--tool", f"{PY} {tool}"], cwd=root, capture_output=True, text=True, timeout=300, env=env)
    r["builder_oracle"] = (cp.stdout.strip().splitlines() or ["?"])[-1]
    return r


base = score(SRC, "_baseline")
json.dump(base, open(os.path.join(OUT, "baseline.json"), "w"), indent=1)
src = open(os.path.join(SRC, REL)).read()
rows = []
for name, old, new in MM.M:
    if only and name not in only:
        continue
    root = f"/tmp/m23-mut-{name}"
    shutil.rmtree(root, ignore_errors=True)
    shutil.copytree(SRC, root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    open(os.path.join(root, REL), "w").write(MM.apply(src, old, new))
    r = score(root, name)
    k = {
        "probes": sorted(p for p, v in base["probes"].items() if r["probes"].get(p) != v),
        "prep": sorted(p for p, v in base["prep"].items() if r["prep"].get(p) != v),
        "builder_tests": r["builder_tests"] != base["builder_tests"],
        "builder_oracle": r["builder_oracle"] != base["builder_oracle"],
    }
    row = {"mutant": name, "kills": k, "raw": {"builder_tests": r["builder_tests"], "builder_oracle": r["builder_oracle"]}}
    rows.append(row)
    print(json.dumps({"mutant": name, "probes": k["probes"][:6], "prep": k["prep"], "bt": k["builder_tests"], "bo": k["builder_oracle"]}), flush=True)
    shutil.rmtree(root, ignore_errors=True)
json.dump(rows, open(os.path.join(OUT, "teeth.json"), "w"), indent=1)
print("DONE")
