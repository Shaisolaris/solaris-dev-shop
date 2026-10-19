"""M01 r4 teeth (adds M01 r4 probes; r3 header follows) M01 r3 teeth (Grok self-validation) on G01 r2 1621c82. Usage: PY run_teeth_r3.py PY OUT [i/n]. Per mutant: copy
/tmp/m01r4-eval (no .git) to /tmp/m01r4-mut-<name>, apply, score with the M01 oracle (core, gaps), M01 r2 probes,
M01 r3 probes, builder tests/test_fixture_runner.py and the full builder suite. A kill is any deviation from the
unmutated candidate on that instrument. Includes a no-op control."""
import json, os, re, shutil, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
PY, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
SRC = "/tmp/m01r4-eval"; REL = "employees/quality-security/assurance/quality_os.py"
env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}
run = lambda a, cwd=None: subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=500, env=env)
last = lambda cp: (cp.stdout.strip().splitlines() or ["?"])[-1]
def score(root):
    e = os.path.join(root, REL); r = {}
    r["oracle"] = last(run([PY, os.path.join(here, "m01_oracle.py"), e, "--python", PY]))
    r["probes_r2"] = re.findall(r"^(y\d+) (?:HOLDS|GAP)", run([PY, os.path.join(here, "m01r2_adversarial.py"), PY, e]).stdout, re.M)
    p2 = run([PY, os.path.join(here, "m01r2_adversarial.py"), PY, e]).stdout
    r["probes_r2"] = sorted(re.findall(r"^(y\d+) HOLDS", p2, re.M))
    p3 = run([PY, os.path.join(here, "m01r3_probes.py"), PY, e]).stdout
    r["probes_r3"] = sorted(re.findall(r"^(z\d+) HOLDS", p3, re.M))
    p4 = run([PY, os.path.join(here, "m01r4_probes.py"), PY, e]).stdout
    r["probes_r4"] = [l.strip() for l in p4.splitlines() if l.strip()]
    r["fixture_tests"] = run([PY, "-m", "unittest", "tests/test_fixture_runner.py"], cwd=root).returncode == 0
    r["suite"] = run([PY, "-m", "unittest", "discover", "-s", "tests"], cwd=root).returncode == 0
    return r
base = score(SRC); json.dump(base, open(os.path.join(OUT, "baseline.json"), "w"), indent=1); print(json.dumps({"baseline": base}), flush=True)
names = run([PY, os.path.join(here, "make_mutants_r4.py"), "--list"]).stdout.split()
if len(sys.argv) > 3:
    i, n = map(int, sys.argv[3].split("/")); names = names[i::n]
    if i == 0: names = ["control_noop"] + names
rows = []
for name in names:
    root = f"/tmp/m01r4-mut-{name}"; shutil.rmtree(root, ignore_errors=True)
    shutil.copytree(SRC, root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    t = os.path.join(root, REL)
    if name == "control_noop":
        open(t, "a").write("# control: no-op\n")
    else:
        cp = run([PY, os.path.join(here, "make_mutants_r4.py"), os.path.join(SRC, REL), name, t])
        if cp.returncode:
            rows.append({"mutant": name, "error": cp.stderr[-200:]}); print(json.dumps(rows[-1]), flush=True); shutil.rmtree(root, ignore_errors=True); continue
    s = score(root); k = {key: s[key] != base[key] for key in base}
    rows.append({"mutant": name, "kills": k, "scores": s}); print(json.dumps({"mutant": name, **k}), flush=True)
    shutil.rmtree(root, ignore_errors=True)
json.dump(rows, open(os.path.join(OUT, "teeth.json"), "w"), indent=1); print("DONE", flush=True)
