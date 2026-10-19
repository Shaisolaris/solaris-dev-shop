"""M25 r2 teeth (Grok self-validation). Usage: PY run_teeth_r2.py PY OUT [i/n]. Per mutant: copy /tmp/m25r2-eval (no .git)
to /tmp/m25r2-mut-<name>, apply, score with M25 v2 core (K01-K23), M25 r2 probes (graded rows), builder
tests/test_g25_capability.py (the only test file that references the module) and builder protocol_oracle.py.
A kill is any deviation from the unmutated candidate on that instrument."""
import json, os, re, shutil, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
PY, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
SRC = "/tmp/m25r2-eval"; REL = "employees/engineering/iot-engineer/device_protocol.py"
CORE = ",".join(f"K{i:02d}" for i in range(1, 24))
env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}
run = lambda a, cwd=None: subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=600, env=env)
def score(root, tag):
    t = os.path.join(root, REL); r = {}
    cp = run([PY, os.path.join(here, "m25_oracle.py"), t, "--python", PY, "--only", CORE])
    r["m25_core"] = sorted(re.findall(r"^(K\d+) HOLDS", cp.stdout, re.M)) or [(cp.stdout.strip().splitlines() or ["?"])[-1]]
    d = os.path.join(OUT, "p-" + tag); run([PY, os.path.join(here, "m25r2_probes.py"), PY, t, d])
    try:
        r["probes"] = sorted(x["id"] for x in json.load(open(os.path.join(d, "probes.json"))) if x["result"] == "PASS")
    except Exception as e:
        r["probes"] = [f"_error {e}"]
    shutil.rmtree(d, ignore_errors=True)
    r["builder_tests"] = "OK" if run([PY, "-m", "unittest", "tests.test_g25_capability"], cwd=root).returncode == 0 else "FAIL"
    cp = run([PY, "protocol_oracle.py", "--tool", f"{PY} {t}"], cwd=os.path.join(root, "examples/capabilities/G25"))
    r["builder_oracle"] = (cp.stdout.strip().splitlines() or ["?"])[-1]
    return r
base = score(SRC, "_baseline"); json.dump(base, open(os.path.join(OUT, "baseline.json"), "w"), indent=1)
print(json.dumps({"baseline_core": len(base["m25_core"]), "probes": len(base["probes"]), "bt": base["builder_tests"], "bo": base["builder_oracle"]}), flush=True)
src = open(os.path.join(SRC, REL)).read(); rows = []
names = run([PY, os.path.join(here, "make_mutants_r2.py"), "--list"]).stdout.split()
if len(sys.argv) > 3:  # shard i/n: every n-th mutant from i
    i, n = map(int, sys.argv[3].split("/")); names = names[i::n]
for name in names:
    root = f"/tmp/m25r2-mut-{name}"; shutil.rmtree(root, ignore_errors=True)
    shutil.copytree(SRC, root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    cp = run([PY, os.path.join(here, "make_mutants_r2.py"), os.path.join(SRC, REL), name, os.path.join(root, REL)])
    if cp.returncode:
        rows.append({"mutant": name, "error": cp.stderr[-200:]}); print(json.dumps(rows[-1]), flush=True); continue
    r = score(root, name)
    k = {i: (sorted(set(base[i]) ^ set(r[i])) if isinstance(base[i], list) else r[i] != base[i]) for i in base}
    rows.append({"mutant": name, "kills": k}); print(json.dumps({"mutant": name, **k}), flush=True)
    shutil.rmtree(root, ignore_errors=True)
json.dump(rows, open(os.path.join(OUT, "teeth.json"), "w"), indent=1); print("DONE", flush=True)
